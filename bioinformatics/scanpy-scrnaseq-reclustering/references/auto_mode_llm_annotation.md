# Auto Mode: LLM-Based Iterative Annotation

## Overview

`scRNAseq.py --mode auto` runs a fully autonomous pipeline: cluster → AI annotate → QC → filter → re-cluster. It iterates until no problematic clusters remain or `max_iterations` (default 5) is reached.

## Pipeline Architecture (scanpy.smk)

Rules: `qc → merge(+gene_type) → auto → advanced → de → result`
- **merge** handles gene_type annotation via `--te-bed`/`--gene-tsv` CLI args
- **cluster/annotate rules removed** — auto mode replaces them
- **node.py controls DAG**: if LLM config exists (`llm_method` non-empty), requests `*_advanced.h5ad`; otherwise requests `*_merged.h5ad`
- Rules have static inputs/outputs. No conditional logic in .smk files.

## Gene Type Annotation (in merge step)

Gene type annotation runs inside `mode_merge()` when `--te-bed` and `--gene-tsv` are provided:
```bash
scRNAseq.py --mode merge --input file1.h5ad file2.h5ad --output merged.h5ad \
  --te-bed rmsk_TE.bed --gene-tsv geneIDAnnotation.csv
```
Config: `te_bed` and `gene_tsv` passed from genome references in scRNAseq.json → node.py → scanpy_config.

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--mode auto` | required | Runs iterative auto pipeline |
| `--input` | required | Input h5ad (merged, with QC metrics) |
| `--output` | required | Output annotated h5ad |
| `--input-path` | `""` | Original input path for run.sh generation |
| `--llm-method` | required | `openai` or `ollama` |
| `--llm-model` | required | Model identifier (e.g., `mimo-v2.5-pro`) |
| `--llm-api-key` | `""` | API key for OpenAI-compatible backend |
| `--llm-base-url` | `""` | Base URL for LLM API |
| `--tissue` | `""` | Tissue context for LLM prompts |
| `--resolution` | `0.8` | Leiden resolution |
| `--n-neighbors` | `50` | k-NN neighbors |
| `--n-pcs` | `50` | PCA components |
| `--n-top-genes` | `3000` | HVGs |
| `--max-iterations` | `5` | Max QC refinement iterations |
| `--min-genes` | `800` | Min genes/cell for QC |
| `--min-counts` | `3000` | Min UMI/cell for QC |
| `--max-pct-mt` | `20.0` | Max MT% for QC |
| `--skip-te` | False | Exclude TE genes before HVG |
| `--batch-method` | `harmony` | Batch correction (`harmony`/`bbknn`/`""`) |
| `--batch-key` | `""` | Batch column in obs |
| `--auto-n-pcs` | False | Auto-detect n_pcs from PCA variance |
| `--plot-dir` | `""` | Directory for output plots |
| `--debug` | False | Save per-iteration UMAP/annotation plots |

## What Each Iteration Does

0. **Step 0: Tissue knowledge query** (runs ONCE before iterations) — queries LLM for known cell types in the tissue. Returns cell_type→canonical_markers mapping. Injected into annotation prompts so LLM uses tissue-specific names. See `references/tissue_knowledge_query.md`
1. **Normalize + HVG + PCA + Harmony + UMAP + Leiden** — standard clustering
2. **AI annotate each cluster** — sends top 50 DEGs per cluster to LLM with PubMed lookup
   - LLM outputs: cell_type, key_markers, **canonical_markers**, reasoning, confidence, quality_flag
   - canonical_markers = standard markers from literature (NOT limited to top50 DEGs)
3. **Step 2.5: Specificity-weighted scoring refinement** — collects canonical_markers from all clusters, builds temporary marker dict, re-scores each cluster using specificity × rank weighting algorithm from annotate_all.py. Overwrites LLM labels with refined labels. Preserves original in `llm_label` column. See `references/specificity_weighted_scoring.md`
4. **Quality analysis** — flags clusters with low_counts, te_dominated, or other issues
4. **Step 3.25: Check should_merge flags** — LLM identifies clusters that should be merged
5. **Step 3.5: Cell type separation check** — marker-based misannotation detection (see below)
6. **Filter flagged clusters** — removes low-quality cells (NOT entire clusters)
7. **Save raw counts for filtered cells** — prepares for re-clustering
8. **Repeat** until clean or max_iterations reached

### Exit Conditions

- `if not flagged` → all clusters clean → **immediate exit**
- `if n_removed == 0` → filtering had no effect → **immediate exit**
- `if iteration >= max_iterations` → **filters then saves** (last iteration also executes filtering)

## Marker-Based Misannotation Detection (Step 3.5)

When same cell_type appears in clusters far apart in UMAP (distance > 5.0):

1. Compare `key_markers` between the clusters using **Jaccard similarity**
2. **Jaccard > 0.3** → genuine over-clustering → suggest lower resolution
3. **Jaccard ≤ 0.3** → annotation error (LLM mislabeled) → flag smallest cluster

**Priority**: Misannotated clusters are flagged FIRST (added to quality_reports), then resolution adjustment for over-clustering.

**Example output**:
```
Endothelial: 2 clusters, max dist=6.59, marker Jaccard=0.176
→ FLAG cluster 1 (221 cells, low quality)
Misannotation detected: cluster 1 labeled 'Endothelial' but markers diverge
```

## Evidence-Based Annotation (CRITICAL)

**All cell type annotations must have PubMed PMID evidence.** The LLM prompt requires:
- Every cell type assignment must cite PMIDs in reasoning
- If no public evidence exists → set cell_type to "Unverified"
- TE-dominated clusters: LLM must search PubMed. If published evidence supports TE-high as real biology (with PMID), annotate accordingly (e.g., "Alu_high"). If no evidence → "Unverified_TE"

## LLM-Generated Audit Reports

After all iterations, `_generate_audit_report()` calls the LLM with the full iteration context to produce:
- `audit_report.md` — **Chinese** audit report with per-iteration summaries, PMID references, decision rationale
- `decision_log.sh` — LLM decision log (NOT a CLI replay script): each decision as a comment with reasoning

Context collected per iteration: cluster sizes, annotations (with reasoning/confidence/markers), QC flags, filter decisions, resolution changes, misannotated clusters, outcome.

## HVG Batch Key Fallback

After filtering, some batches may have too few cells, causing `sc.pp.highly_variable_genes(batch_key=...)` to fail with NaN bin edges. The code handles this with try/except:
```python
try:
    sc.pp.highly_variable_genes(adata, batch_key=resolved_batch_key, ...)
except ValueError:
    logging.warning("HVG with batch_key failed. Retrying without batch_key.")
    sc.pp.highly_variable_genes(adata, ...)
```

## Output Files

```
output_dir/
  ovaries_auto.h5ad                    # Final annotated h5ad
  ovaries_auto_reports/
    annotation_report.tsv              # Per-cluster: cell_type, confidence, markers, flags, reasoning
    references.tsv                     # PubMed references cited by LLM
    audit_report.md                    # LLM-generated Chinese audit report
    decision.log                       # LLM-generated decision log
  plots/auto/
    annotate_umap_cell_type.png        # UMAP with right-margin legend (refined labels)
    annotate_umap_llm_label.png        # UMAP with original LLM labels (before scoring refinement)
    annotate_deg_dotplot.png           # DEG dotplot
    annotate_rank_genes_groups.png     # Rank genes overview
    cluster_umap_leiden.png            # Leiden clusters
    cluster_umap_sample_id.png         # Sample distribution
```

## Orchestrator Checkpoint (Post v3 Refactoring)

After annotation, a SINGLE orchestrator LLM call sees the full state and decides: accept / correct_annotations / filter_and_recluster / adjust_resolution_and_recluster.

**Key design principles**:
- Orchestrator sees per-cluster: cell_type, top_markers(10), trust, alternative, should_drop, lq_pct, score, n_matched, QC metrics
- Structural signals (over_clustering, misannotated) are passed as DATA, not instructions
- Current resolution is in the prompt header
- Prompt must be MINIMAL — see `references/orchestrator_prompt_patterns.md` for tested templates
- Resolution enforcement: if LLM sets same value, code forces -0.2 decrease
- Use Jaccard/max_distance for structural decisions, NOT cluster counts (same cell type in multiple clusters is biologically normal)

## Pitfalls

### Pitfall A1: gene_type not in var when using --skip-te
**Symptom**: `_filter_te()` logs warning "gene_type not in var, skipping TE filter"
**Cause**: h5ad doesn't have `gene_type` column — run merge with `--te-bed`/`--gene-tsv` first

### Pitfall A2: Auto mode runs very long
**Cause**: Each iteration: 12-22 clusters × ~1 min/cluster = ~12-22 min/iteration × 5 iterations
**Fix**: Run in background. Reduce `--max-iterations` if needed.

### Pitfall A3: Last iteration doesn't filter
**Old behavior** (max_iterations=3): iteration >= max_iterations → break without filtering
**New behavior** (max_iterations=5): iteration >= max_iterations → filter → break (filtered data used for final output)

### Pitfall A4: Resolution keeps dropping
**Symptom**: Resolution goes 0.8 → 0.25 → 0.2 across iterations, clusters merge too aggressively
**Cause**: Every iteration with separated types triggers resolution reduction
**Fix**: Resolution only drops when separation is detected AND markers overlap (Jaccard > 0.3). Misannotated clusters are filtered instead of lowering resolution.

## Context-Aware Filtering

`_filter_flagged_cells()` uses a 4-level strategy based on annotation quality:
- TE-dominated → per-cell TE fraction filtering (TE > 0.5 = noise)
- High confidence + PMID → skip filtering (biological low QC)
- Medium confidence → relaxed thresholds (0.5× min_genes/counts)
- Low confidence → strict thresholds (original values)

See `references/auto_mode_context_aware_filtering.md` for full details and TE fraction data.

## Rare Cell Type Preservation (Step 2.5)

`_preserve_lost_cell_types()` detects rare cell types lost after re-clustering and restores their labels. Requires adding new categories to the categorical column before assignment.

## Debug Mode (`--debug`)

`--debug` saves per-iteration UMAP and annotation plots in `plots/auto/iter_N/`. Default OFF.

```bash
--resolution 0.8        # Start high, auto-adjusts down
--n-neighbors 50        # Standard
--max-iterations 5      # Default, allows convergence
--batch-method harmony  # Default, works well
--tissue ovary          # Context for LLM prompts
--plot-dir plots/       # Generate all annotation plots
```
