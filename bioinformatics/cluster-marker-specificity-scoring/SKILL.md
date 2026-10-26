---
name: cluster-marker-specificity-scoring
description: scRNA-seq annotation missing types hidden by DEG ranking.
tags: [bioinformatics, scrnaseq, annotation, marker-specificity, deg-ranking]
version: "1.0"
author: hermes
license: MIT
metadata:
  hermes:
    tags: [bioinformatics, scrnaseq, annotation, marker-specificity, deg-ranking]
---

# Cross-Cluster Marker Specificity Scoring

## When to Use

- scRNA-seq cell type annotation pipeline **misses a known cell type** that you
  can verify is present by inspecting the data manually (e.g. Oocyte markers
  clearly expressed in a cluster but DEG list is dominated by proliferation genes)
- DEG ranking hides tissue-specific markers because high-variance non-tissue
  genes (proliferation, cell cycle, stress response) outscore them
- Current Step 2.5 / mixed-identity checks all look at top-N DEGs and miss the
  same signal for the same reason
- You need to add a **tie-breaker** that surfaces diagnostic markers without
  overriding correct LLM calls

## Core Concept

For each (cell_type, gene) pair, compute:

```
specificity = cluster_mean_expression / max(other_cluster_means)
```

A marker with `specificity >> 1` means THIS cluster is the top expresser —
even if absolute expression is low in log-normalized space. Cross-cluster
comparison is essential; absolute mean expression alone is uninformative
because a 0.17 mean in one cluster is high if all others are near zero.

## Three Integration Points (in increasing impact)

## Integration Point 1 — LLM prompt injection (strongest impact)

Inject top-5 most-specific markers for the target cluster as a
**PRIMARY EVIDENCE** section at the TOP of the annotation prompt (BEFORE
DEGs). The LLM sees:

```
## PRIMARY EVIDENCE: Top specific markers for THIS cluster
These markers are UNIQUELY enriched in this cluster vs all others.
Use these as your MAIN basis for cell type identification.
specificity = this cluster's mean / max mean in other clusters.
Higher specificity = more diagnostic. >=2.0x = strong evidence.

  - Oocyte | DDX4: mean=0.165 (other_max=0.005), specificity=33.0x, 2.1% cells express
  - Oocyte | FIGLA: mean=0.230 (other_max=0.010), specificity=23.0x, 2.7% cells express

## SECONDARY EVIDENCE: Top 50 DEGs (ranked by Wilcoxon score)
NOTE: DEGs are ranked by statistical significance, NOT by cell-type specificity.
Many top DEGs are generic genes (cell cycle, stress, ECM) expressed across
multiple cell types. Use DEGs only to complement the specificity markers above.
```

**CRITICAL**: The specificity table must be positioned BEFORE the DEG list.
If placed after DEGs as a "tie-breaker", the LLM ignores it when DEGs are
overwhelmingly dominated by generic markers (50 cell cycle genes vs 0 oocyte
genes in DEGs → LLM picks Proliferating_Cell instead of Oocyte).

**Prompt structure (verified working, 2026-09-18)**:
1. Cluster info (cells, genes, counts, MT%)
2. PRIMARY: Specificity table (top specific markers)
3. SECONDARY: Top 50 DEGs
4. Other clusters + Tissue cell types
5. Task + Rules (with "SPECIFICITY FIRST" rule)

**Validation**: macaque ovaries Cluster 18 (Oocyte, 437 cells):
- Old prompt (DEGs first, specificity as tie-breaker): → Proliferating_Cell
- New prompt (specificity first): → Oocyte (high confidence)

### 2. Mixed-identity / confidence downgrade

Add a `specificity-missed` flag to the existing mixed-identity check:

```
is_specificity_missed = (
    predicted_cell_type has 0 markers with specificity >= 2.0 AND pct_pos > 1%
    AND some other cell_type has >= 2 such markers
)
```

If true, downgrade confidence high→medium. This catches cases where the LLM
chose a plausible-but-wrong cell type despite tissue-specific markers pointing
elsewhere.

### 3. Step 2.5 refinement scoring

Replace or augment top-50 DEG overlap with:

```python
combined_score = legacy_de_overlap + 1.5 * spec_count
# spec_count = number of markers (NOT sum) with:
#   - cluster is top expresser (specificity >= 2.0)
#   - > 1% of cells in cluster express the marker
```

**Use COUNT, not SUM.** One marker with specificity ~4M (CD14 in Monocyte) can
otherwise dominate and produce false reassignments (Monocyte eating Macrophage,
T_Cell eating NK_Cell when one shared marker has extreme specificity).

**Always include a MIN-SPECIFICITY-MARKERS GATE** (e.g. `MIN_SPEC = 2`):
refinement is only allowed when candidate has >= 2 qualifying markers. Without
the gate, ties and zero-score cases produce random reassignments.

## Per-Cluster vs Global Mode

- `cluster_id=None` (global): `this_mean` = global mean across all cells;
  `other_max` = max cluster mean. **The filter `other_max <= this_mean`
  ALWAYS fails** because max cluster mean >= global mean. Only useful for
  per-marker global stats (e.g. ranking which markers are rare overall).
- `cluster_id=str(N)` (per-cluster): `this_mean` = cluster N's mean;
  `other_max` = max of OTHER clusters' means. Correctly identifies whether
  THIS cluster is the top expresser. **This is the mode that fixes the bug.**

## Performance: Bulk vs Per-Gene Extraction

Per-gene `adata[mask, gene].X.toarray()` is **1500x slower** than bulk
extraction. ~9 minutes vs ~0.4 seconds for typical 18 clusters x 23 cell types
workload.

Always use **vectorized bulk extraction**:

```python
all_genes_needed = sorted({g for markers in tissue_cell_types.values()
                          for g in markers if g in adata.var_names})
gene_idx = [adata.var_names.get_loc(g) for g in all_genes_needed]
bulk = np.asarray(adata.X[:, gene_idx].toarray(), dtype=np.float64)
# bulk shape: (n_obs, n_genes_needed)

# Per-cluster vectorized stats
cluster_gene_means = {}
for cl in clusters:
    sub_bulk = bulk[cluster_labels == cl]  # (n_cells_in_cl, n_genes_needed)
    means = sub_bulk.mean(axis=0)
    pctpos = (sub_bulk > 0).mean(axis=0) * 100
    for i, g in enumerate(all_genes_needed):
        cluster_gene_means[(cl, g)] = float(means[i])
```

Always include a per-gene fallback for rare failure modes (e.g. weird X formats).

## When NOT to Use

- The cell type IS detected by top-N DEG overlap -> no fix needed
- Marker expression is uniform across clusters -> no specificity signal possible
- The dataset has only 2-3 clusters -> cross-cluster specificity is degenerate

## Integration Point 4 — Data-driven generic DEG detection (most robust)

When top DEGs have low average specificity (< 1.5x), they're generic genes
that don't define cell types. Detect this BEFORE building the prompt and
expand the specificity table + add WARNING. This operates at the data level
and doesn't depend on LLM compliance.

See `references/data-driven-deg-detection.md` for implementation.

## Quick Diagnostic: Is This Technique Needed?

```python
import scanpy as sc
# For each tissue marker, find its top-expressing cluster
for marker in tissue_markers:
    if marker not in adata.var_names:
        continue
    means_by_cluster = adata.obs['leiden'].groupby(
        adata.obs['leiden']
    ).apply(lambda g: adata[g.index, marker].X.mean())
    top_cluster = means_by_cluster.idxmax()
    top_mean = means_by_cluster.max()
    second_mean = means_by_cluster.nlargest(2).iloc[-1]
    if top_mean > 2 * second_mean and top_mean > 0.05:
        print(f"  {marker}: top cluster={top_cluster}, "
              f"specificity={top_mean/second_mean:.1f}x, "
              f"abs={top_mean:.3f}")
```

If output shows >= 3 markers with specificity > 4x for ONE specific cluster but
the LLM is labeling that cluster as something else, this technique will help.

## Validation Pattern

Before integrating into production, dry-run on an existing annotated h5ad:

```python
import sys, json
sys.path.insert(0, "/path/to/scanpy/bin")
from <module> import _compute_marker_specificity

adata = sc.read_h5ad("annotated.h5ad")
ctx = json.load(open("reports/audit_report.json"))
tissue_cell_types = ctx["tissue_cell_types"]

# Per-cluster specificity
all_spec = {str(c): _compute_marker_specificity(adata, tissue_cell_types,
                                                 cluster_id=str(c))
            for c in adata.obs['leiden'].unique()}

# Check known-missed cluster
target_cluster = '17'
target_cell_type = 'Oocyte'
hits = [(g, m) for (ct, g), m in all_spec[target_cluster].items()
        if ct == target_cell_type
        and m['specificity'] >= 2.0 and m['pct_pos'] > 1.0]
print(f"Cluster {target_cluster} {target_cell_type} markers: {len(hits)}")
```

If the known-missed cluster shows >= 2 qualifying hits, the technique works and
is safe to integrate.

## Known Limitations

- Tissue markers must be present in the dataset (filtered by HVG selection or
  gene panel). The diagnostic won't help if DDX4 is not in `adata.var_names`.
- Specificity is a **single-cluster signal**, not a multi-cluster co-expression
  signal. Two markers being co-cluster-specific does not imply the same cell
  type — confirm with biology, not just scoring.
- Inter-cluster contamination (ambient RNA) can produce false specificity —
  e.g. ambient Hepatocyte transcripts in a Macrophage cluster could give
  Hepatocyte markers "specificity > 2x" in Macrophage. Pair with QC flags
  (mean_genes, mean_counts, pct_mt) to filter.

## Pitfall: Generic markers dominating annotation

Even with specificity table present, LLM can still be misled when generic
markers dominate the DEG list:

| Cluster | Top DEGs (all generic) | Specificity markers (correct) | LLM picked |
|---------|----------------------|-------------------------------|------------|
| Oocyte (437 cells) | MKI67, TOP2A, CENPF, CDK1 | DDX4 (4.7x), NLRP5 (367130x) | Proliferating_Cell ❌ |
| Stromal+ECM (406 cells) | MYH11, ACTA2, TAGLN | IGFBP5 (1st), SFRP1 (1st) | Smooth_Muscle_Cell ❌ |

**Root cause**: "tie-breaker" framing. LLM sees 50 cell cycle genes in DEGs
and 0 oocyte genes → "not a tie" → ignores specificity table.

**Fix**: Reposition specificity as PRIMARY EVIDENCE (see Integration Point 1).
Also add "SPECIFICITY FIRST" rule and "Generic marker warning" in Rules section.

**Validation (2026-09-18 macaque ovaries)**:
- Marker specificity check showed most cell types had ALL markers with
  specificity < 2.0x (e.g. Fibroblast 16/16, Granulosa 21/21)
- Only NK_Cell had all 10 markers with specificity >= 2.0x
- This means most annotations were based on non-specific DEGs, not
  genuinely diagnostic markers

**v10 result (2026-09-18, specificity-first prompt)**:
- Oocyte correctly annotated (high confidence) — was Proliferating_Cell before
- Myofibroblast detected (was Smooth_Muscle_Cell before)
- Cell types queried: 50 (was 40 before improved Step 0 prompt)
- 19 clusters, 15 unique cell types, 112 unique markers

## Marker Specificity Diagnostic Script

To check ALL cell types' marker specificity at once:

```python
# For each cell type, count markers with specificity < 2.0
for ct, cluster_ids in ct_to_clusters.items():
    low_spec = []
    for gene in all_markers:
        target_mean = mean_in_target_clusters
        other_max = max_mean_in_other_clusters
        spec = target_mean / other_max if other_max > 0 else float('inf')
        if spec < 2.0:
            low_spec.append((gene, spec))
    if low_spec:
        print(f"{ct}: {len(low_spec)}/{len(all_markers)} markers NOT specific")
```

**Typical results** (macaque ovaries v10):
- NK_Cell: 0/10 NOT specific ✅
- Proliferating_Cell: 1/10 NOT specific ✅
- Macrophage: 4/10 NOT specific (partially)
- Fibroblast: 16/16 NOT specific ❌
- Granulosa_Cell: 21/21 NOT specific ❌
- Oocyte: 2 markers (NLRP5 8.3x, LHX8 7.4x) — high specificity but very low expression (2-4% cells)

## Oocyte-Specific Pitfall: Very Low Marker Expression

Oocyte markers (DDX4, NLRP5, FIGLA) have:
- HIGH specificity (3-8x) because other clusters don't express them
- VERY LOW expression (mean=0.02-0.08, only 2-4% of oocyte cells)
- LLM may return only 2 key_markers (NLRP5, LHX8) instead of 5-10
  because the evidence is weak from the LLM's perspective

This is a **biological limitation**, not a technical bug. Oocytes are rare
(~2% of cells) and oocyte-specific genes are expressed in only a fraction
of them. The markers ARE specific (other clusters don't express them at all)
but the absolute signal is too weak for confident visual verification on UMAP.

## LLM Returning Fewer Than 5 Key Markers

When the LLM returns only 2-3 key_markers instead of the requested 5-10,
it usually means the evidence is weak. The plot_markers function plots ALL
returned key_markers (no limit), so a cell type with only 2 markers will
get a plot with 2 panels + 1 UMAP reference panel.

This is correct behavior — the LLM is being appropriately conservative.
Do NOT pad with non-specific markers to fill 5-10 slots.

## Provider-Specific Quirks (LLM backend variance)

Different LLM backends return different `tissue_cell_types` from Step 0 —
this is non-deterministic and the missing-type detection downstream cannot
recover from it.

### Minimax (anthropic API)

Empirically observed on macaque ovaries (2026-09-18):
- Run 1 (v6, minimax): `tissue_cell_types` had 35 entries including
  `Lymphatic_Endothelial_Cell: [LYVE1, PROX1, CCL21, FLT4, NRP2, ...]`
  → cluster 1 (LYVE1+/PROX1+/CCL21+) correctly labeled Lymphatic_EC
- Run 2 (v7, minimax, rerun): `tissue_cell_types` had 23 entries, **LOST**
  `Lymphatic_Endothelial_Cell` entirely → cluster 1 (same expression profile,
  same 267 cells, same high LYVE1/PROX1/CCL21) mislabeled Endothelial_cell

Same LLM, same prompt, same backend, different tissue_cell_types keys.
The cluster's expression signature is identical, but the LLM has no option
to pick Lymphatic_EC so it picks Endothelial_cell (its closest parent type).

**Mitigations** (in order of preference):

1. **Rerun and hope** — minimax non-determinism means rerun often returns the
   missing type. Cheap but unreliable.
2. **Strengthen Step 0 prompt** — explicitly require "ALL endothelial subtypes
   including lymphatic vs blood vascular" and validate against a small whitelist.
3. **Post-hoc override in Step 2.5** — after LLM annotation, if a cluster has
   strong lymphatic signature (LYVE1+/PROX1+/CCL21+) but LLM picked a generic
   endothelial type, check against a tissue-specific marker whitelist and
   force-relabel. This is the most robust but breaks the "no hardcoding" rule
   (whitelist is tissue-specific).
4. **Manual fix** — edit `annotation_report.tsv` post-hoc. Acceptable when
   the issue is one missing type in one run; not scalable.

### Xiaomi mimo (openai API)

Less variance than minimax in the observed samples, but Step 0 still produces
14-25 entries across runs of the same prompt. Decision log generation
(`_call_llm_for_decision_log`) intermittently fails with
`Expecting value: line 1 column 1 (char 0)` — empty response from API.
Independent of specificity fix; unrelated.

## Reference: Empirical Cluster Fixes (macaque ovaries, v6 → v7)

With this technique applied:
- v6: cluster 17 mislabeled Granulosa_Cell (439 cells, top DEGs all proliferation)
- v7: cluster 18 mislabeled Granulosa_Cell (439 cells, same data, but with
  specificity fix, LLM prompt included DDX4/FIGLA/NOBOX/GDF9 specificity table
  → LLM correctly switched annotation to Oocyte)

Same physical cluster (proliferating-oocyte), same expression data, different
annotation outcome. The fix worked end-to-end via prompt injection.

Other v6 → v7 changes (some unrelated to this technique):
- Mural_granulosa_cell (1707 cells): NEW cell type detected
- Pericyte (1695 cells): NEW cell type detected
- Theca_cell (947 cells): NEW cell type detected (specificity > 1,000,000x
  for LHCGR and CYP17A1, decisive evidence)
- Stromal_fibroblast → Stromal_cell: name normalization