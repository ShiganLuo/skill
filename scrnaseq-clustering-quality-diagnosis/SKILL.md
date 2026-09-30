---
name: scrnaseq-clustering-quality-diagnosis
description: Use when scRNA-seq Leiden clustering looks wrong.
tags: [bioinformatics, scrnaseq, clustering, leiden, umap, orchestrator]
version: "1.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [bioinformatics, scrnaseq, clustering, leiden, umap, orchestrator]
    related_skills: [scrnaseq-auto-annotation, snakemake-module-config]
---

# scRNA-seq Clustering Quality Diagnosis

## When to Use

Trigger this skill when the user shows you a Leiden UMAP and says any of:
- "聚类效果很差" / "clustering looks bad" / "clusters are wrong"
- "UMAP looks scattered" / "孤立点太多" / "too many small clusters"
- "orchestrator changed resolution" / "why is resolution 0.3 when I passed 0.8?"
- "cell_type X is missing from the annotation"
- "Granulosa subtypes collapsed into one cluster"
- "real subtypes were merged" / "over-clustering merged real biology"

Do NOT use this skill for: QC issues (use scrnaseq-qc), batch effect only,
differential expression, or trajectory/velocity analysis.

## Diagnostic Decision Tree

```
User complains about UMAP/clustering
    │
    ├─► Step 1: Load .h5ad and inspect leiden resolution
    │   adata.uns['leiden']['params']['resolution']
    │   Compare to user-requested --resolution
    │
    ├─► Step 2: If resolution was lowered without consent → orchestrator bug
    │   (See "Orchestrator over-correction" section below)
    │
    ├─► Step 3: Check cluster x cell_type crosstab
    │   Are cell types missing? Are real subtypes merged?
    │   Look at QC medians per cluster to distinguish:
    │     - low counts/genes → artifact, merge is OK
    │     - high counts/genes → real subtype, merge is WRONG
    │
    ├─► Step 4: Check cell_type x leiden crosstab for the dominant cell type
    │   If e.g. Granulosa_cell appears in 3+ clusters:
    │     - all_high_qc → REAL subpopulations (mural, cumulus, oocyte)
    │     - mixed_qc → genuine over-clustering, merge OK
    │
    ├─► Step 5: Check sample_id distribution per cluster
    │   All samples mixed → batch OK (harmony worked)
    │   One sample dominates → batch effect, re-run with stronger correction
    │
    └─► Step 6: Check QC across clusters for genuine low-quality clusters
        median total_counts < global_median/2 → low-quality
        median pct_counts_mt > 5x → dying cells
```

## Orchestrator Over-correction — The Most Common Failure Mode

The scRNAseq.py `mode_auto()` orchestrator implements a separation check that
can drop `--resolution` from the user's value (e.g. 0.8) down to 0.25 or 0.3
based on the ratio of separated cell types. **This is wrong biology.**

### Why it's wrong

Memory rule (carried across sessions):
> Over-clustering (Jaccard > 0.3) = annotation error, NOT resolution error.
> When same cell_type appears in multiple distant clusters with high marker
> overlap, they were mislabeled as the same type. Fix = correct_annotations,
> NOT adjust_resolution. Clustering is fine; annotation is wrong.

Concretely: Granulosa_cell in 3 clusters at distances 3.35, 3.72, 6.98 is
**expected** — ovaries have mural granulosa, cumulus granulosa, and oocyte
that share lineage markers (FOXL2, AMH, CYP19A1, etc.) but are biologically
distinct populations. Forcing them into one cluster destroys information.

### Symptom signature in log

```
Clustering done: 12 clusters   ← Too few for tissue with 8+ cell types
Cell type separation check: 1 over-clustering, 0 misannotated
Cell type separation detected. Adjusting resolution: 0.80 -> 0.25
No quality issues. Re-clustering with lower resolution...
```

### Verification before fixing

Before any code change, verify the diagnosis with a direct function call
(skip the full pipeline):

```python
import anndata
import scRNAseq as S
adata = anndata.read_h5ad("path/to/auto_bed1b16_v2.h5ad")

# Build mock annotations (cell_type is already in adata.obs)
annotations = {c: {"cell_type": adata.obs.loc[adata.obs['leiden']==c,
                                              'cell_type'].iloc[0],
                   "key_markers": []}
                for c in adata.obs['leiden'].unique()}

needs, diag = S._check_cell_type_separation(
    adata, cell_type_key="cell_type", cluster_key="leiden",
    distance_threshold=5.0, annotations=annotations,
)
print(f"needs_reclustering: {needs}")
print(f"suggested_resolution: {diag.get('suggested_resolution')}")
print(f"n_real_subpopulations: {diag.get('n_real_subpopulations')}")
for sp in diag.get('real_subpopulations', []):
    print(f"  {sp}")
```

If `n_real_subpopulations` lists your high-QC clusters, the QC-guard fix
should be applied.

## QC-Guard Pattern (Reference Fix)

When modifying `_check_cell_type_separation`, add this QC-evidence filter
inside the Jaccard>0.3 branch:

```python
# Compute global medians once before the loop
global_total_counts_med = float(obs["total_counts"].median())
global_n_genes_med = float(obs["n_genes_by_counts"].median())

def _qc_high(mask):
    sub = obs.loc[mask]
    return (sub["total_counts"].median() >= global_total_counts_med
            and sub["n_genes_by_counts"].median() >= global_n_genes_med)

# In the Jaccard>0.3 branch:
all_high_qc = all(_qc_high(obs[cluster_key] == ci["cluster"])
                  for ci in clusters_info)
if all_high_qc:
    # Skip over-clustering classification. Already recorded in
    # real_subpopulations for downstream visibility.
    continue
else:
    separated_types.append({...})  # Genuine over-clustering
```

Also add this in `mode_auto()` to respect the user's initial resolution:

```python
if iteration == 1:
    # Don't adjust on iteration 1 — let QC filter clean up first.
    logging.info("Respecting user-requested resolution=%.2f", resolution)
elif suggested_res < resolution:
    resolution = suggested_res
```

## LLM Annotation Failure: Missing Cell Types in Step 0

The Step 0 tissue query asks the LLM to "List ALL known cell types" for a tissue.
But LLMs often miss transitional/activated/mixed-phenotype types. In v8, 40 cell
types were queried for macaque ovaries but **Myofibroblast** was missing. Cluster 4
had clear dual phenotype (SMC markers MYH11/ACTA2 + stromal markers IGFBP5/SFRP1/DCN)
but was annotated as pure Smooth_Muscle_Cell because Myofibroblast wasn't an option.

### How to detect
Check if a cluster's top DEGs include markers from TWO different canonical lineages:
```python
# Cluster 4: SMC markers + stromal markers
# MYH11, ACTA2 (SMC) AND IGFBP5, SFRP1, DCN, FN1 (stromal)
# SFRP1 in C4: 91.4% expressing, mean=2.57 vs C12: 10.7%, mean=0.11
```
If a cluster has high-specificity markers from two lineages (not ambient RNA),
the annotation is likely wrong and the cell type is missing from Step 0.

### Verification: not ambient RNA
Compare expression in the suspect cluster vs adjacent clusters:
- SFRP1 in C4: 91.4%, mean=2.57 → genuine high expression
- SFRP1 in C12 (same SMC type): 10.7%, mean=0.11 → NOT ambient RNA
If the marker is only expressed in the suspect cluster at high levels, it's real.

### Fix: improve Step 0 prompt
Add explicit rule to include transitional/mixed-phenotype types:
```
- IMPORTANT: Include transitional, activated, and mixed-phenotype cell types
  (e.g. Myofibroblast, Activated_Stromal_Cell, Cancer-Associated_Fibroblast,
  Tip_Endothelial_Cell, Proliferating_cell). These are commonly found in
  scRNA-seq data but often missed. They express markers from TWO or more
  canonical lineages simultaneously.
```

### Pitfall: LLM dominated by top DEGs
LLM annotation focuses on the top-ranked DEGs (MYH11, ACTA2 for Cluster 4).
Stromal markers ranked lower (IGFBP5 #3, SFRP1 #7) get overlooked. The
specificity scoring in Step 2.5 also only compares against the 40 cell types
from Step 0, so it can't assign a type that wasn't queried.

## Marker Visualization Pattern (plot_markers)

### Wrong: plot by cluster with top 3 markers
```python
# Old: one figure per cluster, only top 3 markers
for cid in annotations:
    markers = annotations[cid]["key_markers"][:3]  # WRONG: truncates
```

### Correct: plot by cell type with ALL markers
```python
# New: one figure per cell type, ALL markers, all clusters labeled
ct_to_clusters = {}
for cid, ann in annotations.items():
    ct_to_clusters.setdefault(ann["cell_type"], []).append(cid)

for ct, cluster_ids in ct_to_clusters.items():
    # Collect ALL unique markers from all clusters of this cell type
    markers = []
    seen = set()
    for cid in cluster_ids:
        for g in annotations[cid]["key_markers"]:
            if g not in seen:
                markers.append(g)
                seen.add(g)
    # Plot all markers, label all cluster centroids
```

Key rules:
- Group by cell type, NOT cluster
- Plot ALL markers (5-10 per cluster), not just top 3
- Highlight ALL clusters belonging to the cell type (red bold centroids)
- Title: `{CellType}  [C4, C12, C14]`
- Output filename: `{CellType}.png` (sanitized)

## LLM Annotation Failure Mode (separate from clustering)

If clusters look right but all `cell_type` values are "Unknown":

```python
# In run.log, look for:
WARNING - Unknown LLM method '' for cluster 0
WARNING - Unknown LLM method '' for cluster 1
...
WARNING - OpenAI API call failed: ...
```

### Root cause: env fallback was removed in commit a01b702

The 2026-09-15 commit `a01b702` (resolution/auto_n_pcs defaults fix) **unintentionally
deleted two pieces of code that bridged LLM env vars to argparse**:

1. The `os.environ.get(...)` defaults on `--llm-method`/`--llm-model`/`--llm-api-key`/`--llm-base-url`
2. A post-parse safety-net loop that re-filled any empty `args.llm_*` from env

When called from Snakemake (which sets these in `.bashrc` at lines 169-172),
the env vars used to flow through transparently. After a01b702, scripts
running outside Snakemake see empty `args.llm_method=""` and never call
the LLM.

### Real fix: restore the env fallback in `main()`

In `scRNAseq.py` `main()`, restore the deleted blocks:

```python
# 1. argparse defaults that read from env
parser.add_argument("--llm-method", default=os.environ.get("LLM_METHOD", ""), ...)
parser.add_argument("--llm-model", default=os.environ.get("LLM_MODEL", ""), ...)
parser.add_argument("--llm-api-key", default=os.environ.get("LLM_API_KEY", ""), ...)
parser.add_argument("--llm-base-url", default=os.environ.get("LLM_BASE_URL", ""), ...)

# 2. Post-parse fill (safety net for Snakemake passing --llm-method "")
args = parser.parse_args()
for arg_name in ("llm_method", "llm_model", "llm_api_key", "llm_base_url"):
    if not getattr(args, arg_name):
        env_val = os.environ.get(arg_name.upper(), "")
        if env_val:
            logging.info("LLM config %s filled from env %s", arg_name, arg_name.upper())
            setattr(args, arg_name, env_val)
```

With this restored, scripts can use a plain `#!/bin/bash -lic` shebang
(which sources `.bashrc`) and pass **NO** `--llm-*` args. The env vars
flow through automatically.

### Workaround when the real fix is not yet applied

If the user has not yet restored the env fallback, scripts must pass
all four `--llm-*` flags explicitly:

```bash
#!/bin/bash -lic        # -l sources .bashrc so env vars are inherited
python scRNAseq.py --mode auto \
    --llm-method "${LLM_METHOD:-openai}" \
    --llm-model "${LLM_MODEL:-mimo-v2.5-pro}" \
    --llm-api-key "${LLM_API_KEY:-}" \
    --llm-base-url "${LLM_BASE_URL:-}" \
    [other params...]
```

### Pitfall: hermes sandbox has no LLM env vars

`execute_code` runs in a clean sandbox shell that does NOT source `.bashrc`.
If a user is running a test script through hermes, even with the real fix,
the env vars will be empty unless one of:
- The script uses `#!/bin/bash -lic` shebang (then bash itself sources .bashrc)
- The script `export`s the env vars explicitly (memory rule says "never set
  manually", so this is a violation)

If the user reports "LLM calls returning Unknown" and the script already
has the env fallback fix, suspect that the shell sandbox is the cause.

### User preference: "Env vars pre-configured, never set manually"

Memory rule: when LLM env is already set in `.bashrc` (the user's actual
interactive shell), do NOT re-export them in scripts and do NOT pass
`--llm-*` flags manually. The agent should trust the env and let the
script's env fallback (when restored) pull them automatically.

A user said during diagnosis: "LLM配置指导在哪吗" — pointing out that
hard-coding the env vars in a script violates the memory rule. When the
real env-fallback fix is restored, scripts become minimal again and this
preference is honored.

## Spatial Discontinuity Detection (fixed 2026-09-18)

### Bug: continuity check bypassed by early exit
`_check_cluster_continuity` was positioned AFTER the early exit in mode_auto:
```python
if not flagged:
    break  # ← exits before continuity check runs
# Step 3.6: continuity check ← NEVER REACHED
```
Cluster 18 (Oocyte, 437 cells) had max_gap=4.254 (67+370 disconnected fragments)
but was never detected. Fix: moved continuity check BEFORE early exit.

### Bug: outlier cells trigger false positives
`max_gap > 2.0` alone detects clusters with 1-7 outlier cells as discontinuous:
- Cluster 5: 1849+1, Cluster 9: 2221+3, Cluster 7: 1027+2

Fix: added `min_side_pct=0.05` — both sides must have ≥5% of cluster cells.
After fix: only Cluster 11 (44+510) and Cluster 18 (67+370) flagged vs 10 before.

### Pitfall: Don't jump to parameter conclusions
When user says "clustering looks bad", do NOT immediately blame n_pcs, resolution,
or n_neighbors. Check spatial continuity FIRST. The v8 case: n_pcs=15 was actually
reasonable (PCA variance flat after PC15), but the agent kept suggesting parameter
changes. User corrected: "你确定是分散的问题吗，能不能好好查查".

**Sequence**: spatial discontinuity → marker expression verification → THEN parameters.

### Diagnostic: check discontinuity before declaring "clustering looks bad"
```python
from scipy.sparse import csgraph
import numpy as np

for cluster in sorted(adata.obs["leiden"].unique(), key=int):
    mask = adata.obs["leiden"] == cluster
    n = int(mask.sum())
    if n < 50: continue
    coords = adata.obsm["X_umap"][mask.values]
    for dim in range(2):
        sorted_c = np.sort(coords[:, dim])
        gaps = np.diff(sorted_c)
        max_gap = float(gaps.max())
        if max_gap > 2.0:
            idx = int(gaps.argmax())
            mid = (sorted_c[idx] + sorted_c[idx+1]) / 2
            left = int((coords[:, dim] < mid).sum())
            right = n - left
            if min(left, right) >= 0.05 * n:
                print(f"Cluster {cluster}: DISCONTINUOUS gap={max_gap:.2f} {left}+{right}")
```

### Neighbor graph connectivity vs UMAP discontinuity
A cluster can be 1 connected component in the neighbor graph but appear
disconnected in UMAP. This happens when n_neighbors=50 creates short-range
bridges between distant cell groups. The UMAP projection then separates
them visually even though the graph says they're connected.

**Diagnosis**: check BOTH neighbor graph connectivity AND UMAP gaps.
If graph=connected but UMAP=disconnected → the neighbor graph is too
permissive (n_neighbors too high for that cluster's density).

## What "Looks Bad" Often Isn't

UMAP "scattered" with many small isolated clusters is **normal** for tissues
with 8+ cell types (ovaries, brain, immune organs). The clusters being far
apart in UMAP reflects real biological distinctness, not a parameter failure.

Before declaring something broken, verify with `cell_type` UMAP (color by
cell_type instead of leiden). If each color forms a compact contiguous
island, the clustering is correct — the "scattered" perception comes from
rare cell types being far from the dominant cluster (e.g. T cells next to
granulosa cells).

## Diagnostic Checklist (Save Before Fixing)

Before modifying any code, capture:

1. `adata.uns['leiden']['params']['resolution']` — was it user-requested?
2. `adata.obs.groupby(['leiden','cell_type']).size().unstack(fill_value=0)`
   — full crosstab
3. Per-cluster QC: median total_counts, n_genes, pct_mt, pct_ribo
4. Per-cluster UMAP centroid pairwise distances
5. Same-type cluster distances (key for separation_diag)
6. Sample distribution per cluster (harmony check)

Save to `backup_pre_fix/` directory with h5ad + reports + plots. Never
overwrite user artifacts without backup.

## Output Files Pattern

After diagnosis, place artifacts at:
- `/home/<USER>/Data/genomeStability/output/<project>/<tissue>/`
- `backup_pre_fix/` — pre-fix h5ad, reports, plots
- `plots/<tool>/<version>/` — versioned plots (e.g. auto_bed1b16_v3)
- `scanpy_<mode>_<tool>_<tissue>_<timestamp>.sh` — versioned run scripts

Scripts and results belong in the SAME directory (per project convention).

## Reference Files

- `references/case-ovaries-2026-09-16.md` — full ovaries case study: 12→21 cluster recovery, log transcripts, before/after
- `references/case-ovaries-v8-discontinuity-fix.md` — spatial discontinuity detection: early exit bug, min_side_pct fix
- `references/case-ovaries-v9-v10-marker-priority.md` — Oocyte loss, stress gene misannotation, marker priority rule, plot_markers rewrite

## Generic Markers Hiding Tissue-Specific Annotations

When a cluster's top 50 DEGs are ALL generic markers (cell cycle, stress, ECM),
the LLM annotation ignores low-frequency tissue-specific markers in the
specificity table. This is the most insidious annotation failure because
the clustering is actually correct — only the annotation is wrong.

### Case: Oocyte → Proliferating_Cell (v9)

Cluster 18 (437 cells, v8=Oocyte, v9=Proliferating_Cell):
- Top DEGs: MKI67, TOP2A, CENPF, CDK1, BIRC5, PCNA, CCNB2 (ALL cell cycle)
- Oocyte markers: DDX4 (2.1%), NLRP5 (4.2%), FIGLA (2.3%) — NOT in top 50 DEGs
- Specificity table DID have DDX4/NLRP5, but LLM was overwhelmed by 50 cell cycle genes
- Adding Proliferating_Cell to Step 0 cell types made LLM choose it over Oocyte

### Detection

```python
# Check if a cluster has generic-dominated DEGs but tissue-specific in specificity
import json
report = json.load(open("audit_report.json"))
ann = report["iterations"][-1]["annotations"]["18"]
markers = ann["key_markers"]  # MKI67, TOP2A, ... (all generic)
# Check specificity table for this cluster — does it show tissue-specific markers?
```

In run.log, look for:
```
Cluster 18: annotating...
    -> Proliferating_Cell (confidence: medium, ...)
```
When you'd expect Oocyte/Theca/Granulosa — the LLM was misled by generic DEGs.

### Fix: Marker priority rule in annotation prompt

Added to `_build_auto_annotation_prompt` Rules section:
```
- **Marker priority**: Tissue-specific markers take PRIORITY over generic markers.
  Generic markers like cell cycle genes (MKI67, TOP2A, CENPF, CDK1, CCNB2, PCNA),
  stress response genes (FOS, JUN, EGR1, HSP), and ECM genes (COL1A1, COL1A2, DCN)
  are NOT sufficient alone to define a cell type. When a cluster has BOTH generic
  dominant DEGs AND tissue-specific markers (even at low frequency in the DEG list
  or specificity table), annotate based on the tissue-specific markers.
  Example: top DEGs = MKI67, TOP2A, CDK1 but specificity showing DDX4/NLRP5
  enriched → Oocyte, NOT Proliferating_Cell.
```

**Limitation**: This is a prompt-level fix — LLM may still not comply when
50 generic DEGs overwhelm the specificity table. Stronger intervention needed:
force LLM to check specificity table FIRST when generic markers dominate top DEGs.

### Pitfall: Adding Proliferating_Cell to Step 0 has side effects

Adding generic cell types (Proliferating_Cell, Activated_Stromal_Cell) to Step 0
gives the LLM more options but also more chances to misannotate. Oocyte markers
are inherently low-frequency (2-4% expressing) because oocytes are rare and
their markers are diluted by cell cycle activity during meiosis.

**Trade-off**: Keep Proliferating_Cell in Step 0 (useful for real proliferating
populations) but enforce marker priority rule in the annotation prompt.

## Stress Gene Misannotation (FOS/JUN → Activated_Stromal_Cell)

When FOS, JUN, FOSB, EGR1 dominate a cluster's DEGs, LLM may annotate it as
"Activated_Stromal_Cell" or "Proliferating_Cell". These are stress response
genes induced by tissue dissociation — NOT cell type markers.

### Case: Cluster 10 (v9) → Activated_Stromal_Cell

Markers: IGFBP5, FOSB, EGR1, FOS, JUN, NR4A1, DCN, APOE, ALDH1A1, RARRES2
- FOS/JUN/FOSB/EGR1 = stress genes, expressed across ALL clusters
- IGFBP5/DCN/APOE/RARRES2 = stromal markers, shared with other stromal clusters
- NONE are specific to Cluster 10

### Detection

Check marker expression on UMAP — if every marker is expressed across multiple
clusters with no specificity to the target cluster, the annotation is wrong.

### Fix

Same marker priority rule handles this: stress genes (FOS, JUN, EGR1) are
generic and should not define cell types.

## Rules

- **Verify before fixing.** Call `_check_cell_type_separation` directly on the
  existing h5ad before any code change. Trust data, not assumptions.
- **Backup before modifying.** h5ad + reports + plots → backup_pre_fix/.
- **Never remove parameters without asking.** If orchestrator added a
  constraint, that's a feature, not a bug — fix the upstream heuristic.
- **Trust high-QC clusters.** If a small cluster has counts/genes ≥ global
  median, treat it as a real subpopulation until proven otherwise.
- **Jaccard > 0.3 with shared lineage markers = biology, not bug.**
- **Investigate before blaming parameters.** When user says "clustering looks bad",
  check spatial continuity and marker specificity FIRST, not n_pcs/resolution.
  User correction: "你确定是分散的问题吗，能不能好好查查" — never jump to
  parameter conclusions without evidence.
- **Verify hypotheses with data, don't guess.** If you suspect something (e.g.
  "Cluster 4 might be Myofibroblast"), check the actual marker expression
  across clusters. User: "如果你怀疑什么,就检查验证,不要猜测".