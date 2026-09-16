---
name: scanpy-scrnaseq-reclustering
description: "Re-cluster scRNA-seq h5ad with Harmony and annotation."
tags: [scanpy, scrnaseq, clustering, annotation, harmony, single-cell]
---

# Scanpy scRNA-seq Re-clustering & Annotation

Nature-standard pipeline for re-clustering merged h5ad files with proper batch correction and cell type annotation.

## Reference Files

- `references/recluster_annotate_pipeline.py` — Original pipeline script
- `references/recluster_annotate_v3.py` — Nature-standard v3 with all reviewer fixes (colorblind palette, rare cell types, doublet verification, legend, merged clusters)
- `references/macaque_ovary_analysis.md` — Macaque ovary marker analysis results and validated configuration
- `references/rhesus_macaque_hystera_markers.md` — Rhesus macaque uterus markers (validated)
- `references/rhesus_macaque_reproductive_markers.md` — Reproductive tissue markers
- `references/nature-figure-standards.md` — Nature publication figure standards (fonts, sizes, colors, required plots)
- `references/qc-filtering-strategies.md` — QC filtering strategies: hard filters vs MAD, order matters, tissue-specific thresholds
- `references/elbow-detection-auto-params.md` — PCA auto-detection: 4 methods (cumvar/plateau/curvature/sliding_window), two-subplot PCA variance plot, full-stack param addition pattern
- `references/scte-annotation-markers.md` — scTE-specific cell types (ERVK_high, rRNA_enriched), macaque ovary/hystera marker dictionaries, batch annotation pattern
- `references/pseudobulk_deg_pydeseq2.md` — Pseudobulk DEG with PyDESeq2: pseudo-replicate workaround for no-replicate designs, TE gene identification (proper regex to avoid false positives), cell type composition analysis, scanpy sif environment notes
- `references/te_filtering_gene_annotation.md` — TE filtering: BED+CSV annotation format, skip-te workflow, ERVK_high vs Alu_high comparison
- `references/auto_mode_llm_annotation.md` — Auto mode: LLM-based iterative annotation (cluster→AI→QC→filter→re-cluster), two-step workflow, CLI args
- `references/tissue_knowledge_query.md` — Two-stage LLM pattern: query tissue cell types first (Step 0), inject into annotation prompts. Tested on macaque ovary.
- `references/scte_vs_cellranger_comparison.md` — scTE vs Cell Ranger: quantitative differences, cell type correspondence, root cause analysis
- `references/auto_mode_context_aware_filtering.md` — Context-aware filtering (TE fraction, high-confidence preservation), rare cell type preservation, debug mode
- `references/orchestrator_prompt_patterns.md` — Orchestrator prompt design: minimal templates, resolution enforcement, PubMed XML NoneType fix, Jaccard-based structural decisions

## Auto Mode (LLM-Based Iterative Annotation)

`scRNAseq.py --mode auto` runs: cluster → LLM annotate → QC → filter → re-cluster (iterative).

### Pipeline Architecture (scanpy.smk)

Rules: `qc → merge(+gene_type) → auto → advanced → de → result`
- **merge** handles gene_type annotation via `--te-bed`/`--gene-tsv` CLI args (added to mode_merge)
- **cluster/annotate rules removed** — auto mode replaces them
- **node.py controls DAG**: if LLM config exists (`llm_method` non-empty), requests `*_advanced.h5ad`; otherwise requests `*_merged.h5ad`
- Config flow: `scRNAseq.json` → `node.py::runscRNAseq()` → `scanpy_config` dict → `scanpy.smk`

### Gene Type Annotation (in merge step)

Gene type annotation runs inside `mode_merge()` when `--te-bed` and `--gene-tsv` are provided. No separate step needed:
```bash
scRNAseq.py --mode merge --input file1.h5ad file2.h5ad --output merged.h5ad \
  --te-bed rmsk_TE.bed --gene-tsv geneIDAnnotation.csv
```
Config: `te_bed` and `gene_tsv` passed from genome references in scRNAseq.json → node.py → scanpy_config.

### Key Features

- LLM sees other clusters' annotations + UMAP distances → detects subclusters and merge candidates
- **Context-aware filtering** (4 levels): TE-dominated→TE fraction, high-confidence→skip, medium→relaxed, low→strict
- **Rare cell type preservation** (`_preserve_lost_cell_types`): detects cell types lost after re-clustering, restores labels
- Cell type separation check (Step 3.5) → **marker-based misannotation detection** via Jaccard similarity
- `plot_annotate()` called automatically when `--plot-dir` set → generates UMAP cell_type, dotplot, etc.
- **Step 0: Tissue knowledge query** (NEW): Before clustering, queries LLM for known cell types in the tissue (`_query_tissue_cell_types()`). Returns cell_type→canonical_markers mapping. Injected into every cluster's annotation prompt so LLM uses tissue-specific nomenclature (e.g., "Luteal", "Cumulus", "Theca") instead of generic names. See `references/tissue_knowledge_query.md`
- **Step 0.5: Tissue marker verification** (NEW): After Step 0, samples 3 markers per cell type and verifies against PubMed. Catches obvious LLM hallucinations (fabricated markers). Uses `{gene} AND {cell_type}` query (no tissue context — too specific). Results logged as warnings, not blocking.
- **Specificity-weighted scoring refinement (Step 2.5)**: After LLM annotation, collects `canonical_markers` from all clusters into a temporary marker dict, then applies the same specificity-weighted scoring algorithm from `annotate_all.py` to refine labels. LLM provides domain knowledge (what markers each cell type should have), scoring provides precision. See `references/specificity_weighted_scoring.md`
- **Orchestrator checkpoint**: After annotation, a SINGLE LLM call sees full state (per-cluster trust, QC, structural signals from separation_diag) and decides: accept / correct_annotations / filter_and_recluster / adjust_resolution_and_recluster. Key: use Jaccard/max_distance for structural decisions, NOT cluster counts. See `references/orchestrator_prompt_patterns.md`
- **`--debug` flag**: saves per-iteration UMAP and annotation plots for debugging
- **`--skip-te` only affects clustering (HVG), NOT DEG analysis**
- **max_iterations default = 5** (changed from 3). Last iteration also executes filtering before saving
- **HVG batch_key fallback**: if HVG with batch_key fails after filtering (too few cells per batch), retries without batch_key

### LLM-Generated Audit Reports

After all iterations, `_generate_audit_report()` calls the LLM with the full iteration context to produce:
- `audit_report.md` — Chinese audit report with per-iteration summaries, PMID references, decision rationale
- `decision_log.sh` — LLM decision log (NOT a CLI replay script): each decision as a comment with reasoning

Context collected per iteration: cluster sizes, annotations (with reasoning/confidence/markers), QC flags, filter decisions, resolution changes, outcome.

### Evidence-Based Annotation (CRITICAL)

**All cell type annotations must have PubMed PMID evidence.** The LLM prompt requires:
- Every cell type assignment must cite PMIDs in reasoning
- If no public evidence exists → set cell_type to "Unverified"
- TE-dominated clusters: LLM must search PubMed. If published evidence supports TE-high as real biology (with PMID), annotate accordingly (e.g., "Alu_high"). If no evidence → "Unverified_TE"

### Usage
```bash
# Auto mode (gene_type annotation happens in merge step automatically)
# LLM config must be passed explicitly — NOT read from env vars
scRNAseq.py --mode auto --input merged_with_genetype.h5ad --output output.h5ad \
  --llm-method openai --llm-model <model> --llm-api-key "$LLM_API_KEY" --llm-base-url "$LLM_BASE_URL" \
  --tissue ovary --species Mmul_10 --skip-te --plot-dir plots/
```

### Automation Design Principle (CRITICAL)

**User correction**: "首先我们这是自动化注释,你上面方案肯定不行.组织来源是多样" — Pre-defined marker dictionaries don't work for automation because tissue sources are diverse.

**Wrong approach**: Hard-code OVARY_MARKERS or per-tissue marker files into the pipeline.
**Correct approach**: Let LLM provide tissue knowledge dynamically via Step 0 query.

**Why**: There are hundreds of tissue types. Maintaining marker dictionaries for each is impossible. The LLM already "knows" these markers from training data — we just need to ask it.

**Implementation**: `_query_tissue_cell_types()` queries LLM once at the start, returns cell_type→markers mapping. This is injected into every cluster's annotation prompt. Combined with specificity-weighted scoring, this achieves near-manual-annotation precision without any pre-defined markers.

## Pseudobulk DEG Analysis (Post-Annotation)

After annotation, run per-cell-type differential expression using pseudobulk aggregation + PyDESeq2.

**Workflow**: For each cell type, aggregate raw counts by sample → split into pseudo-replicates → PyDESeq2 → per-gene statistics (log2FC, padj). See `references/pseudobulk_deg_pydeseq2.md` for full implementation.

**Key points**:
- PyDESeq2 in scanpy sif (`apptainer exec scanpy.sif python3`), NOT in host venv
- No-replicate designs (1-vs-1 sample comparisons): split each sample into 2 pseudo-replicates
- TE gene identification: use prefix-based matching (Alu/HERV/LTR/MER/MacERV etc.), NOT naive regex
- Cell Ranger data: 0 TE genes (expected). scTE data: 40-80+ TE genes in HVG set
- Output: per-cell-type TSV (with `is_TE` column) + volcano plots (TE highlighted)

## Script Placement (CRITICAL)

Analysis scripts MUST go in the **output directory** (e.g., `<project>/output/<run>/`), NEVER in the workflow source repo (`workflow/Omics/`). The source repo is version-controlled pipeline code; analysis scripts are run-specific artifacts.

```
✓ output/luancao/scRNAseq/cluster_annotate.py    ← standalone analysis script
✗ workflow/Omics/modules/scanpy/bin/cluster_annotate.py  ← pollutes source repo
```

User expects **actual execution with real outputs** (plots, h5ad files), not just script creation. Always run the script after writing it. User explicitly complained: "我让你自主进行降维聚类注释,你一张图片没产出是为什么" (I asked you to do clustering/annotation yourself, why didn't you produce any images?).

## User Communication (CRITICAL)

When user asks for file paths or results:
- **Just give the paths** — no explanations, no context, no descriptions
- User explicitly complained: "我让你给路径,你听不懂人话是吧" (I asked for paths, can't you understand?)
- If user asks "图在哪" (where are the figures), respond with bare file paths only
- Do NOT describe what the figures show unless asked
- Do NOT explain the analysis pipeline unless asked
- Do NOT add context like "Figure1是4面板主图" — just the path

When user says clustering quality is bad:
- They mean the UMAP looks messy — clusters overlap, central mixing exists
- Do NOT pivot to annotation — "注释也是徒劳" (annotation is useless if clustering is bad)
- Focus on clustering parameters first: resolution, n_neighbors, batch correction method
- Check if the issue is biological continuity (e.g., differentiation trajectory) vs technical failure
- "重新聚类" / "re-cluster" / "redo clustering"
- "注释效果不好" / "annotation not good"
- "细胞群颜色不纯净" / "impure clusters"
- "批次效应" / "batch effect"
- "还是overlap" / "still overlap" → try min_dist=0.05, spread=0.5
- "聚类效果很差" / "clustering quality is bad" → check if biological continuity or parameter issue

When user says "污染了我的源码仓库" (polluted my source repo):
- Analysis scripts must NEVER go in workflow/Omics/ — always in output directory
- User is very protective of their source repo's cleanliness

## Pipeline Order (CRITICAL)

**Correct order**: qc → merge → **batch → cluster** → annotate → advanced → de

Batch correction MUST come BEFORE clustering. Clustering on uncorrected data mixes batch effects into clusters.

**Wrong**: merge → cluster → batch (clusters contain batch effects)
**Correct**: merge → batch → cluster (clusters are batch-corrected)

## QC Filtering Strategy

**Default: hard filters only** (no MAD). MAD-based outlier detection is optional.

```python
# Hard filters (always applied)
adata = adata[
    (adata.obs["n_genes_by_counts"] >= min_genes)
    & (adata.obs["n_genes_by_counts"] <= max_genes)
    & (adata.obs["pct_counts_mt"] <= max_pct_mt)
].copy()
```

**MAD optional** (more permissive when enabled):
- When `use_mad=True`: MAD first → hard filter (MAD on full data, more permissive)
- When `use_mad=False`: hard filter only (default)

**Why MAD first is more permissive**: MAD calculated on full data (with extremes) has larger variance → larger threshold → keeps more cells. Hard filter first removes extremes → MAD on clean data → smaller threshold → removes more cells.

**Nature paper thresholds** (tissue-dependent):
- Normal tissue: max_genes=6000, mt% < 20%
- Cancer/metabolically active: mt% may need 15-25%
- Cardiomyocytes/neurons: max_genes may need 8000-10000

## Pipeline Steps

### 1. QC Filtering
```python
# MUST use np.array() — pandas BooleanArray breaks scipy sparse indexing
adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-") | adata.var_names.str.startswith("mt"))
adata.var["ribo"] = np.array(adata.var_names.str.startswith(("RPS", "RPL")))
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo"], inplace=True)

# Standard thresholds (hard filters only, no MAD by default)
adata = adata[adata.obs.n_genes_by_counts >= 200].copy()
adata = adata[adata.obs.n_genes_by_counts <= 6000].copy()
adata = adata[adata.obs.pct_counts_mt <= 20].copy()
```

### 2. Normalize + HVG Selection (CRITICAL ORDER)
```python
# 1. Normalize + log-transform
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 2. Save full-gene snapshot for downstream DEG / annotation
adata.raw = adata.copy()  # ALL genes, normalized + log1p

# 3. Detect HVGs (BEFORE scaling)
sc.pp.highly_variable_genes(
    adata, n_top_genes=3000,
    batch_key="sample_id" if "sample_id" in adata.obs else None,
    flavor="seurat",
    subset=True,  # Subset to HVGs only
)

# 4. Scale HVGs only (AFTER HVG selection)
sc.pp.scale(adata, max_value=10)
```

**Why adata.raw**: When you subset to HVGs, non-HVG genes are lost. `adata.raw` preserves all genes for downstream DEG (`use_raw=True`).

### 3. Batch Correction (BEFORE clustering)
```python
# Harmony batch correction — use direct harmonypy to avoid .T bug (see Pitfall 3)
import harmonypy as hm
ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key)
Z = np.asarray(ho.Z_corr)
if Z.shape[0] != adata.n_obs:
    Z = Z.T
adata.obsm["X_pca_harmony"] = Z
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)

# OR BBKNN (builds its own graph, no need for neighbors first)
sc.external.pp.bbknn(adata, batch_key=batch_key)
```

### 4. Clustering (AFTER batch correction)
```python
sc.tl.umap(adata, min_dist=0.1, spread=0.8)
sc.tl.leiden(adata, resolution=resolution, key_added="leiden",
             flavor="igraph", n_iterations=2, directed=False)

# DEG uses adata.raw for full gene coverage
sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon", use_raw=True)
```

### 5. Cell Type Annotation (DEG-based Primary)

**DEG-based annotation is the preferred method** — match each cluster's top DEGs against known tissue-specific markers. This is more robust than CellTypist for non-immune tissues.

**WARNING: CellTypist Immune_All_High is WRONG for non-immune tissues.** It classifies ovarian stromal cells as "ILC", "T cells", etc. Only use CellTypist for immune-dominant tissues (blood, PBMC, lymph node). For solid tissues (ovary, uterus, brain, liver), use DEG-based annotation.

```python
def annotate(adata, marker_dict, groupby="leiden"):
    """Annotate clusters by matching top DEGs against known markers."""
    result = adata.uns["rank_genes_groups"]
    cluster_markers = {}
    for g in result["names"].dtype.names:
        top_genes = list(result["names"][g][:50])  # top50 DEGs
        cluster_markers[g] = top_genes

    all_genes = set(adata.raw.var.index) if adata.raw is not None else set(adata.var.index)
    valid_markers = {}
    for ct, genes in marker_dict.items():
        found = [g for g in genes if g in all_genes]
        if found:
            valid_markers[ct] = set(found)

    cluster_to_ct = {}
    for clust, top_genes in cluster_markers.items():
        top_set = set(top_genes)
        best_ct = "Unknown"
        best_overlap = 0
        for ct, markers in valid_markers.items():
            overlap = len(top_set & markers)
            if overlap > best_overlap:
                best_overlap = overlap
                best_ct = ct
        cluster_to_ct[clust] = best_ct

    adata.obs["cell_type"] = adata.obs[groupby].map(cluster_to_ct).astype("category")

    # Also score markers for visualization (dotplot, violin)
    for ct, genes in marker_dict.items():
        found = [g for g in genes if g in all_genes]
        if found:
            sc.tl.score_genes(adata, gene_list=found, score_name=f"score_{ct}", use_raw=True)
    return adata
```

**Why DEG-based > CellTypist for solid tissues**:
- CellTypist Immune_All_High forces immune labels on non-immune cells (e.g., ovarian stromal → "ILC")
- DEG-based uses the actual cluster DEGs, which are tissue-specific
- Each cluster gets exactly one label based on its best marker overlap

**CellTypist (immune tissues only)**:
- Use `Immune_All_High` model for blood/PBMC/lymph node
- Use local `.pkl` path to skip downloading all61 models:
```python
model_path = os.path.expanduser("~/.celltypist/data/models/Immune_All_High.pkl")
predictions = celltypist.annotate(adata_ct, model=model_path, majority_voting=True)
```
- **Never** use for solid tissues (ovary, uterus, brain, liver) — will produce wrong labels

### 5b. Score-based Annotation (Visualization Only)

Use ONLY for computing marker scores for dotplot/violin visualization. Do NOT use for assigning cell type labels — DEG-based annotation is more robust.

```python
# Compute scores for visualization (dotplot, violin) — NOT for label assignment
for ct, genes in marker_dict.items():
    sc.tl.score_genes(adata, gene_list=genes, score_name=f"score_{ct}", use_raw=True)
```

score_cols = [c for c in adata.obs.columns if c.startswith("score_")]
adata.obs["cell_type"] = (
    adata.obs[score_cols].idxmax(axis=1).str.replace("score_", "").astype("category")
)
# Cluster-level majority vote
cluster_labels = adata.obs.groupby(groupby, observed=True)["cell_type"].agg(
    lambda x: x.value_counts().idxmax()
)
adata.obs["cell_type"] = adata.obs[groupby].map(cluster_labels).astype("category")
```

### 6. Plotting
```python
# Save scanpy plotter objects (DotPlot, MatrixPlot, etc.)
def save_fig(fig_or_plotter, path, dpi=300):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if hasattr(fig_or_plotter, "savefig"):
        fig_or_plotter.savefig(path, dpi=dpi, bbox_inches="tight")
    elif hasattr(fig_or_plotter, "fig"):
        fig_or_plotter.fig.savefig(path, dpi=dpi, bbox_inches="tight")
    else:
        plt.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close("all")

# pca_variance_ratio does NOT accept ax parameter
sc.pl.pca_variance_ratio(adata, n_pcs=50, show=False)
plt.savefig(path, dpi=300, bbox_inches="tight")
plt.close("all")
```

### Pitfall 24: HVG subset before plotting makes the HVG plot useless
**Symptom**: `cluster_highly_variable_genes.png` shows ALL genes as HVG (all blue, no grey), or the plot shows only HVG genes with no context. The plot is meaningless for choosing `n_top_genes`.
**Cause**: `sc.pp.highly_variable_genes(subset=True)` removes non-HVG genes from `adata`. When `sc.pl.highly_variable_genes(adata)` is called later, only HVG genes remain — so they all appear as "highly variable". The user cannot see the full gene distribution or where the cutoff falls.
**Fix**: Use `subset=False`, plot with all genes visible, THEN subset:
```python
# CORRECT: plot first, subset after
sc.pp.highly_variable_genes(adata, n_top_genes=3000, flavor="seurat", subset=False)
# Now adata.var has 'highly_variable', 'means', 'dispersions', 'dispersions_norm' for ALL genes
# Custom plot showing all genes (grey=non-HVG, blue=HVG):
hvg_mask = adata.var["highly_variable"].values
plt.scatter(adata.var["means"][~hvg_mask], adata.var["dispersions_norm"][~hvg_mask],
            c="lightgrey", s=2, alpha=0.3, label="Non-HVG")
plt.scatter(adata.var["means"][hvg_mask], adata.var["dispersions_norm"][hvg_mask],
            c="steelblue", s=4, alpha=0.7, label="HVG")
# NOW subset
adata = adata[:, adata.var.highly_variable].copy()
sc.pp.scale(adata, max_value=10)
```
**Wrong**: `subset=True` → plot → all genes shown as HVG
**Correct**: `subset=False` → plot (all genes visible) → manual subset

### Pitfall 25b: Plot method separation (plot_hvg / plot_pca_variance / plot_cluster)

**Pattern**: Separate diagnostic plots into three methods called at different pipeline stages:
- `plot_hvg(adata, n_top_genes)` — called BEFORE HVG subsetting (needs all genes as background)
- `plot_pca_variance(adata, n_pcs, auto_n_pcs, detect_diag)` — called after PCA
- `plot_cluster(adata)` — UMAP only, called after clustering

**Why**: Each plot needs data from a specific pipeline stage. HVG plot needs all genes (before subset). PCA variance needs the full variance_ratio array (before neighbor graph). Cluster needs UMAP. Combining them in one method forces calling at the wrong time.

**Key rule**: `detect_n_pcs()` must return `(n_pcs, diagnostics_dict)` — never just the number. The dict contains `delta`, `threshold`, `elbow_pc` for the two-subplot PCA visualization.

### Pitfall 25: Split plotting for diagnostic visibility
**Symptom**: Diagnostic plots (PCA variance, HVG dispersion) don't show the full data range because the data was already transformed/subsetted before plotting.
**Cause**: Operations like HVG subsetting or PCA with limited `n_comps` destroy information needed for diagnostic plots. If you plot after the operation, you can't see the full picture.
**Fix**: Split plotting into two phases:
1. **Pre-operation plot**: Call BEFORE the destructive operation (e.g., HVG plot before subsetting, PCA variance before limiting PCs)
2. **Post-operation plot**: Call AFTER the operation (e.g., UMAP after clustering)
```python
# Phase 1: HVG diagnostics (before subsetting)
sc.pp.highly_variable_genes(adata, subset=False)
plotter.plot_hvg(adata)  # shows all genes, HVG highlighted
adata = adata[:, adata.var.highly_variable].copy()

# Phase 2: PCA diagnostics (run PCA with more components for elbow visibility)
sc.tl.pca(adata, n_comps=max(n_pcs, 100))  # extra components for the plot
plotter.plot_pca_variance(adata)  # shows full variance curve

# Phase 3: Clustering results (after everything)
plotter.plot_cluster(adata)  # UMAP only
```
**Key insight**: When using `--auto-n-pcs`, run PCA with `max(n_pcs, 100)` components to give the elbow detection enough data points, then use the detected value for `sc.pp.neighbors(n_pcs=detected)`.

### Pitfall 12: Scaling before HVG selection
**Symptom**: HVG detection on scaled data gives wrong gene selection
**Cause**: `sc.pp.scale()` before `sc.pp.highly_variable_genes()` — HVG should be detected on log-normalized data, not scaled
**Fix**: normalize → log1p → adata.raw → HVG → subset → scale → PCA (HVG BEFORE scale)
**Wrong order**: normalize → log1p → scale → HVG → PCA

### Pitfall 13: Missing adata.raw before subsetting to HVGs
**Symptom**: DEG only reports genes in HVG subset, missing important markers
**Cause**: Subsetting to HVGs removes non-HVG genes from adata.X
**Fix**: Save `adata.raw = adata.copy()` after normalize+log1p, before HVG subset. Use `use_raw=True` in rank_genes_groups.

### Pitfall 14: Batch correction after clustering
**Symptom**: Clusters contain batch effects, samples don't mix in UMAP
**Cause**: Running cluster mode before batch mode — clusters are formed on uncorrected data
**Fix**: Pipeline order must be batch → cluster (not cluster → batch)

### Pitfall 15: Duplicate argparse arguments when merging modes
**Symptom**: `argparse.ArgumentError: argument --batch-key: conflicting option string: --batch-key`
**Cause**: When merging batch correction into cluster mode, the `--batch-key` argument was defined twice — once in QC params and once in Batch params
**Fix**: When consolidating modes, carefully check for duplicate CLI arguments. Remove arguments from the old location before adding to the new one
**Prevention**: After merging modes, run `python script.py --help` to verify no conflicts

### Pitfall 16: Config update completeness
**Symptom**: Parameters not taking effect after code changes
**Cause**: When changing pipeline structure (e.g., merging batch into cluster), forgot to update all config files
**Fix**: When changing parameter structure, update ALL THREE config locations:
1. Module config: `modules/<module>/<module>.json`
2. Workflow config: `config/<workflow>.json` (may have multiple counter sections like scTE/cellranger)
3. Schema: `config/<workflow>.schema.json` (may have multiple definitions for different sections)

**Pitfall 16b: Multiple counter sections in scRNAseq.json**
The scanpy module uses wildcard `{counter}` in rules, so `config/scRNAseq.json` has MULTIPLE counter sections (e.g., scTE, cellranger) each with their own `cluster` block. When adding a parameter, ALL counter sections must be updated. Same for the schema — there are 3 separate `cluster` definitions in `scRNAseq.schema.json`. Use `search_files` to find all occurrences before editing.

### Pitfall 16c: User must remind about skills
**Symptom**: User says "参数修改的skill" (parameter modification skill) — they had to remind you to check the skill before making changes.
**Cause**: Jumped to implementation without loading the relevant skill first.
**Fix**: ALWAYS load `snakemake-config-modification` and `snakemake-module-config` skills BEFORE any parameter addition/removal. The user expects this workflow discipline.

### Pitfall 17: Redundant mode functions
**Symptom**: Duplicate preprocessing code in multiple modes
**Cause**: Separate batch and cluster modes both doing normalize/HVG/scale/PCA
**Fix**: Consolidate related operations into one mode. Batch correction is part of clustering, not a separate step. The cluster mode should handle: preprocess → batch correct → cluster

### Pitfall 22: Rushing to annotation before clustering is perfect
**Symptom**: User says "聚类效果一般,你没有把聚类调整到完美层次,就急着注释了" (clustering is mediocre, you rushed to annotation)
**Cause**: Agent jumps to annotation/CellTypist/DEG before verifying clustering quality
**Fix**: 
1. Always check QC metrics FIRST (see QC-First Workflow section)
2. Run clustering and verify UMAP quality (dense? holes? scattered? overlapping?)
3. If clustering is bad → fix QC or parameters, don't annotate
4. Only when clustering is good → proceed to annotation
5. User will tell you "聚类效果很差" (clustering is bad) if you skip this step

**Rule**: Annotation is USELESS if clustering is bad. Perfect clustering first, then annotate.

### Pitfall 23: Holes in UMAP caused by poor QC, not just UMAP parameters
**Symptom**: User says "为什么会有这么多空洞" (why so many holes), clusters have internal gaps
**Cause**: Low-quality cells (low UMI, high MT%, doublets) are scattered throughout UMAP space, creating holes within clusters
**Common mistake**: Agent tries to fix with min_dist/spread parameters, but the real issue is QC
**Diagnostic**: Check QC metrics distribution — if there are cells with UMI<1000 or MT%>10%, these are likely causing holes
**Fix**: Apply strict QC filters first, then re-cluster. If holes persist, then adjust min_dist.
**Validation**: Compare UMAP before and after strict QC — if holes disappear, QC was the issue.

### Pitfall 19: bbknn can be worse than Harmony for some tissues
**Symptom**: Clusters are more overlapping and less compact with bbknn than Harmony
**Cause**: bbknn builds a batch-balanced k-NN graph which can blur biological boundaries in tissues with continuous differentiation trajectories (e.g., ovaries with granulosa/theca transitions)
**Observation**: For macaque ovaries, Harmony gave cleaner, more separated clusters than bbknn. bbknn merged biologically distinct populations into overlapping blobs.
**Fix**: Use Harmony as default. Try bbknn only if Harmony fails to separate batches. Always compare UMAP quality between methods.
**Rule**: Harmony is safer default for reproductive tissues with continuous cell states.

### Pitfall 21: Scattered outlier points make UMAP look messy
**Symptom**: User says "杂点" (scattered points), "细胞群太稀疏" (populations too sparse), UMAP has isolated dots between clusters
**Cause**: Cells that don't fit well into any cluster appear as scattered points in UMAP space. These are often transitional states, low-quality cells, or doublets.
**Fix**: Filter outlier cells by distance to cluster centroid in UMAP space:
```python
umap_coords = adata.obsm["X_umap"]
leiden_labels = adata.obs["leiden"].values
centroids = {}
for clust in np.unique(leiden_labels):
    mask = leiden_labels == clust
    centroids[clust] = umap_coords[mask].mean(axis=0)
distances = np.zeros(adata.n_obs)
for clust, centroid in centroids.items():
    mask = leiden_labels == clust
    distances[mask] = np.linalg.norm(umap_coords[mask] - centroid, axis=1)
threshold = np.mean(distances) + 1.5 * np.std(distances)  # 1.5σ for cleaner UMAP (user found 2σ not aggressive enough)
outlier_mask = distances > threshold
n_outliers = outlier_mask.sum()
if n_outliers > 0:
    adata = adata[~outlier_mask].copy()
    # MUST re-embed after filtering
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, use_rep="X_pca_harmony")
    sc.tl.umap(adata, min_dist=0.05, spread=0.5, random_state=42)
    sc.tl.leiden(adata, resolution=resolution, flavor="igraph", n_iterations=2, directed=False)
```
**Key**: After filtering, MUST re-run neighbors → UMAP → Leiden. The filtered data needs a fresh embedding.
**Typical removal**: ~2-5% of cells. User prefers aggressive filtering for cleaner UMAP.
**When to use**: When user complains about scattered points, messy UMAP, or sparse clusters. Apply AFTER initial clustering, BEFORE annotation.
**Threshold**: 98th percentile (2%) is optimal — removes scattered points without making clusters too small. User found95th percentile (5%) too aggressive: "分散的太开了,导致cluster看上去很小" (clusters look too small because they're spread out).

### Pitfall 20: CellTypist Immune_All_High misclassifies solid tissue cells
**Symptom**: Ovarian stromal cells labeled as "ILC" (Innate Lymphoid Cells), epithelial cells labeled as "T cells". Cross-tabulation shows mixed labels within single Leiden clusters.
**Cause**: Immune_All_High model is trained on immune data only. When applied to solid tissue, it forces immune labels on non-immune cells because those are the only labels it knows.
**Detection**: Check crosstab `pd.crosstab(adata.obs['leiden'], adata.obs['celltypist_label'])` — if a cluster has>30% cells labeled as immune types but the tissue is not immune-dominant, the model is wrong.
**Fix**: Use DEG-based annotation (match top DEGs against tissue-specific markers) instead of CellTypist for solid tissues. Reserve CellTypist for immune-dominant tissues (blood, PBMC, lymph node).
**Rule**: CellTypist Immune_All_High = immune tissues only. Solid tissues = DEG-based annotation.

### 5c. scTE-Specific Annotation (Transposable Elements + rRNA)

**scTE data** quantifies both gene expression AND transposable elements (TEs) / rRNA. This creates cell types that ONLY appear in scTE data, never in Cell Ranger:

- **ERVK_high** (ovary, ~20%): High ERV-K endogenous retrovirus expression. Markers: `MacERVK2_LTR1c`, `MacNERVK2-int`, etc. 94-100% of cells in cluster express ERVK. NOT contamination.
- **rRNA_enriched** (hystera, ~7.5%): Dominant LSU/SSU rRNA. NOT erythroid (check HBE1/ALAS2=0-4%).

**Rule**: When annotating scTE data, always include TE and rRNA marker categories. Without them, you get large "Unknown" clusters. See `references/scte-annotation-markers.md` for full marker dictionaries.

## Pitfalls

### Pitfall 1: BooleanArray crash
**Symptom**: `AttributeError: 'BooleanArray' object has no attribute 'nonzero'`
**Cause**: Pandas string methods return nullable BooleanArray, scipy sparse indexing needs numpy bool
**Fix**: Wrap in `np.array()`: `np.array(adata.var_names.str.startswith("MT-"))`

### Pitfall 2: harmonypy 2.0 API change
**Symptom**: `TypeError: run_harmony() missing 1 required positional argument: 'vars_use'`
**Cause**: harmonypy 2.0 changed `run_harmony(data, labels)` to `run_harmony(data, meta_data, vars_use=[...])`
**Fix**: Pass DataFrame with batch column, use `vars_use=[batch_key]`

### Pitfall 3: Harmony Z_corr shape (scanpy/harmonypy version mismatch)
**Symptom**: `ValueError: Value passed for key 'X_pca_harmony' is of incorrect shape. Values of obsm must match dimensions ('obs',) of parent. Value had shape (50,) while it should have had (17255,).`
**Cause**: `harmonypy >= 0.1.0` returns `Z_corr` as `(n_cells, n_components)` (already correct), but `sc.external.pp.harmony_integrate` in older scanpy still does `.T`, producing wrong shape. See [scanpy#3940](https://github.com/scverse/scanpy/issues/3940) (fixed in scanpy PR #3953).
**Version matrix**:
  - `harmonypy < 0.1.0`: `Z_corr` shape = `(n_components, n_cells)` → `.T` needed ✓
  - `harmonypy >= 0.1.0`: `Z_corr` shape = `(n_cells, n_components)` → `.T` breaks it ✗
**Detection**: The error always shows a1D-like shape `(n_pcs,)` instead of `(n_cells, n_pcs)`.
**Fix**: Replace `sc.external.pp.harmony_integrate()` with direct `harmonypy` calls:
```python
import harmonypy as hm
import numpy as np

# Replace: sc.external.pp.harmony_integrate(adata, key=batch_key)
ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key)
Z = np.asarray(ho.Z_corr)
if Z.ndim == 1:
    raise ValueError(f"harmonypy Z_corr is 1D shape={Z.shape}, expected 2D")
# Ensure (n_cells, n_components) orientation
if Z.shape[0] != adata.n_obs:
    Z = Z.T
adata.obsm["X_pca_harmony"] = Z
```
**Note**: `harmonypy` is always available when scanpy's wrapper is — it's a transitive dependency. Add `import harmonypy as hm` at the top of the script.

### Pitfall 26: sc.pp.neighbors must use X_pca_harmony after Harmony (CRITICAL)
**Symptom**: After Harmony batch correction, UMAP still shows batch-separated clusters. Samples don't mix.
**Cause**: `sc.pp.neighbors()` defaults to `use_rep="X_pca"`. If you don't specify `use_rep="X_pca_harmony"`, the neighbor graph is built on the UNCORRECTED PCA coordinates, and all downstream steps (UMAP, Leiden) use the wrong space.
**Fix**:
```python
ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key)
Z = np.asarray(ho.Z_corr)
if Z.shape[0] != adata.n_obs:
    Z = Z.T
adata.obsm["X_pca_harmony"] = Z
# MUST specify use_rep — default X_pca ignores Harmony output!
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs,
                use_rep="X_pca_harmony")
```
**Also for re-embedding after outlier filtering**: always check `use_rep`:
```python
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs,
                use_rep="X_pca_harmony" if "X_pca_harmony" in adata.obsm else "X_pca")
```
**Rule**: After Harmony, EVERY `sc.pp.neighbors()` call MUST have `use_rep="X_pca_harmony"`. No exceptions.

### Pitfall 27: Redundant min(n_pcs, shape[1]) guard in neighbors
**Symptom**: `sc.pp.neighbors(n_pcs=min(n_pcs, adata.obsm["X_pca"].shape[1]))` — the `min()` guard is unnecessary and inconsistent (Harmony path doesn't use it).
**Cause**: The guard was added defensively but `n_pcs` is already validated upstream (auto-detect or user-specified). Having it in one code path but not the other creates inconsistency.
**Fix**: Remove the `min()` guard from the non-Harmony path. Use `n_pcs=n_pcs` directly, same as the Harmony path:
```python
# CORRECT — both paths use n_pcs directly
if batch_method not in ("bbknn", "harmony"):
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
# WRONG — inconsistent guard
if batch_method not in ("bbknn", "harmony"):
    sc.pp.neighbors(adata, n_neighbors=n_neighbors,
                    n_pcs=min(n_pcs, adata.obsm["X_pca"].shape[1]))
```
**Rule**: If a value is wrong, fail loudly. Don't add fallback guards that mask errors.

### Pitfall 4: pca_variance_ratio ax parameter
**Symptom**: `TypeError: pca_variance_ratio() got an unexpected keyword argument 'ax'`
**Fix**: Don't pass `ax`, save with `plt.savefig()` after calling

### Pitfall 5: DotPlot not a Figure
**Symptom**: `TypeError: close() argument must be a Figure... not <class 'scanpy.plotting._dotplot.DotPlot'>`
**Cause**: `sc.pl.dotplot(return_fig=True)` returns DotPlot, not matplotlib Figure
**Fix**: Check for `.savefig()` method or `.fig` attribute

### Pitfall 6: seurat_v3 requires skmisc
**Symptom**: `ModuleNotFoundError: No module named 'skmisc'`
**Fix**: Use `flavor="seurat"` instead, or `uv pip install scikit-misc`

### Pitfall 9: anndata nullable strings write error
**Symptom**: `RuntimeError: anndata.settings.allow_write_nullable_strings is None and pd.options.future.infer_string is False`
**Cause**: anndata ≥ 0.11 requires explicit opt-in for writing nullable string arrays
**Fix**: Before `adata.write_h5ad()`:
```python
import anndata
anndata.settings.allow_write_nullable_strings = True
adata.write_h5ad(output_path)
```

### Pitfall 18: 0-cell categories crash dotplot/violin
**Symptom**: `KeyError: "['B_cell', 'Oocyte', 'T_cell'] not in index"` when running `sc.pl.dotplot(groupby="cell_type")` or `sc.pl.violin(palette=...)`
**Cause**: `adata.obs["cell_type"]` has categorical types with0 cells (e.g., marker scoring assigned nobody to B_cell). scanpy's dotplot/violin tries to index into data for all categories, including empty ones.
**Detection**: Any cell type with0 cells in `adata.obs["cell_type"].value_counts()` will trigger this.
**Fix (dotplot)**: Remove unused categories before passing to dotplot:
```python
adata_dot = adata.copy()
adata_dot.obs["cell_type"] = adata_dot.obs["cell_type"].cat.remove_unused_categories()
sc.pl.dotplot(adata_dot, var_names=markers, groupby="cell_type", ...)
```
**Fix (palette for UMAP/violin)**: Build palette from ALL categories (including0-cell), but filter to non-empty for groupby operations:
```python
all_categories = list(adata.obs["cell_type"].cat.categories)  # includes 0-cell
ct_colors_all = {ct: PALETTE[i] for i, ct in enumerate(all_categories)}  # for palette=
ct_categories = [ct for ct in all_categories if (adata.obs["cell_type"] == ct).any()]  # for groupby
```
**Note**: scanpy's UMAP `palette=` needs colors for ALL categories (even0-cell), otherwise `KeyError`.

### Pitfall 11: colorbar_loc="none" crash
**Symptom**: `ValueError: 'none' is not a valid value for location; supported values are 'left', 'right', 'top', 'bottom'`
**Cause**: `sc.pl.umap(colorbar_loc="none")` passes string "none" to matplotlib which expects None
**Fix**: Use `colorbar_loc=None` (Python None, not string)
```python
# WRONG
sc.pl.umap(adata, color=gene, colorbar_loc="none")
# CORRECT
sc.pl.umap(adata, color=gene, colorbar_loc=None)
```

### Pitfall 51: mode_auto discards detect_diag and misses plot_pca_variance (CRITICAL)
**Symptom**: Running `--mode auto --plot-dir plots/` generates cluster UMAP and annotation plots, but NO PCA variance/elbow plot. Users can't verify auto-detected n_pcs.
**Cause**: `mode_auto()` has its own clustering logic (doesn't call `mode_cluster()`). In the PCA auto-detection block:
```python
# WRONG — discards diagnostics
n_pcs_detected, _ = detect_n_pcs(variance_ratio)
```
The `_` throws away the diagnostics dict needed for the two-subplot PCA visualization. Additionally, `mode_auto()` never calls `plotter.plot_pca_variance()`.
**Fix**:
1. Save diagnostics: `n_pcs_detected, detect_diag = detect_n_pcs(variance_ratio)`
2. Initialize before loop: `detect_diag: Dict = {}` (ensures variable exists if auto_n_pcs=False)
3. Add plot call in the plotting section:
```python
plotter = _make_plotter(plot_dir)
if plotter:
    plotter.plot_pca_variance(
        adata, n_pcs=n_pcs, auto_n_pcs=auto_n_pcs,
        detect_diag=detect_diag if auto_n_pcs else None,
    )
    plotter.plot_cluster(adata, cluster_key="leiden", sample_key=resolved_batch_key)
```
**Rule**: Any mode that calls `detect_n_pcs()` MUST save the diagnostics dict and pass it to `plot_pca_variance()`. The `_` discard pattern is a bug, not a feature.

### Pitfall 30: sc.pl.umap color expects obs column names, not uns keys
**Symptom**: `KeyError: 'cell_type_colors'` when calling `sc.pl.umap(adata, color=['cell_type_colors', 'sample_id'])`
**Cause**: The `color` parameter expects column names from `adata.obs`, not keys from `adata.uns`. The color palette (`cell_type_colors`) lives in `adata.uns`, but the column name in obs is just `cell_type`.
**Fix**: Use the obs column name. Scanpy automatically reads the matching palette from `uns['<column>_colors']`:
```python
# WRONG — KeyError
sc.pl.umap(adata, color=['cell_type_colors', 'sample_id'])

# CORRECT — scanpy auto-reads uns['cell_type_colors'] as palette
sc.pl.umap(adata, color=['cell_type', 'sample_id'])
```
**Rule**: `color=` always takes `adata.obs` column names. Palettes in `adata.uns` are read automatically by convention (`<column>_colors`).

### Pitfall 38: HVG with batch_key fails after filtering (NaN bin edges)
**Symptom**: `ValueError: Bin edges must be unique: Index([nan, nan, ...])` during `sc.pp.highly_variable_genes(batch_key=...)` in mode_auto iteration 2+
**Cause**: After filtering, some batches (sample_id) have too few cells. scanpy's per-batch HVG computation fails when a batch has insufficient cells for binning.
**Fix**: Wrap HVG call in try/except, fall back to no batch_key:
```python
try:
    sc.pp.highly_variable_genes(
        adata, n_top_genes=n_top_genes, flavor="seurat", subset=False,
        batch_key=resolved_batch_key if resolved_batch_key in adata.obs else None,
    )
except ValueError:
    logging.warning("HVG with batch_key failed (too few cells per batch). Retrying without batch_key.")
    sc.pp.highly_variable_genes(
        adata, n_top_genes=n_top_genes, flavor="seurat", subset=False,
    )
```
**Rule**: Always handle HVG batch_key failure gracefully in iterative pipelines. Filtering can unbalance batches.

### Pitfall 39: node.py controls DAG, rules just produce files
**Symptom**: User says "不需要如此复杂,规则只负责产出文件,控制用node.py"
**Cause**: Adding conditional logic (`_has_llm_config`, `if has_llm:`, `_final_h5ad()`) inside scanpy.smk to decide which rules to run.
**Fix**: Rules should have static inputs/outputs. Control logic belongs in node.py's `runscRNAseq()`:
```python
# node.py: decide which output to request based on config
for tissue in tissue_samples.keys():
    for counter in counters:
        ann = datajson["Params"].get(counter, {}).get("annotate", {})
        if ann.get("llm_method"):
            outfiles.append(f"{outdir}/common/5_combine_h5ad/{tissue}/{tissue}_{counter}_advanced.h5ad")
        else:
            outfiles.append(f"{outdir}/common/5_combine_h5ad/{tissue}/{tissue}_{counter}_merged.h5ad")
```
**Rule**: Snakemake rules define WHAT to produce. node.py's outfiles define WHAT to request. DAG is built from requested outputs. Never add conditional logic inside .smk files.

### Pitfall 40: TE-dominated clusters need PubMed evidence, not prohibition
**Symptom**: LLM labels clusters as "Alu_high" without evidence. Or: user says "不要禁止,要公共数据可查"
**Wrong approach**: Prohibit TE-based labels entirely
**Correct approach**: Require PubMed PMID evidence for ALL annotations, including TE-dominated:
```
- ALL cell type annotations MUST have PubMed evidence. Include PMIDs in your reasoning.
- If top genes are TE elements, you MUST search for PubMed evidence.
  If published literature supports this TE-high population (with PMID), annotate accordingly.
  If no public evidence exists, set cell_type to "Unverified_TE".
```
**Rule**: Never prohibit a label category. Require evidence. If the LLM can find PMID support, the label is valid.

### Pitfall 41: Blind QC thresholds destroy biologically low-QC cell types
**Symptom**: Oocyte (naturally small cells with low gene/UMI counts) filtered out as "low quality" even with high confidence + PMID support
**Cause**: Generic QC thresholds (min_genes=800, min_counts=3000) applied to ALL flagged clusters
**Fix**: Context-aware filtering — use `_filter_flagged_cells(adata, quality_reports, annotations=annotations)`:
- High confidence + PMID → skip filtering entirely (biological low QC)
- TE-dominated → filter by TE fraction per cell (> 0.5 = noise)
- Medium confidence → relaxed thresholds (0.5× min_genes/counts, 1.5× max_mt)
- Low confidence → strict thresholds (original values)
**See**: `references/auto_mode_context_aware_filtering.md`

### Pitfall 42: TE-dominated cluster entire removal is wrong
**Symptom**: All cells in TE-dominated cluster removed, including cells with real protein-coding gene expression
**Cause**: Old logic removed entire cluster when `te_dominated` flag was set
**Fix**: Use TE fraction per-cell filtering:
```python
te_genes = adata.var_names[adata.var["gene_type"] == "TE"]
te_frac = te_counts / total_counts  # per cell
# TE > 0.5 → pure noise → remove
# TE ≤ 0.5 → has real expression → keep
```
**Data**: Normal cells have TE fraction 20-40% (median 31%). TE > 50% is unusual (9.8% of cells). TE > 80% is near-pure noise (0.3%).

### Pitfall 43: Categorical crash when preserving rare cell types
**Symptom**: `TypeError: Cannot setitem on a Categorical with a new category (Oocyte)`
**Cause**: `_preserve_lost_cell_types()` assigns a cell_type value not in the categorical
**Fix**: Add category before assignment:
```python
if lost_type not in adata.obs["cell_type"].cat.categories:
    adata.obs["cell_type"] = adata.obs["cell_type"].cat.add_categories([lost_type])
```

### Pitfall 44: Rare cell types lost during re-clustering
**Symptom**: Oocyte (33 cells, high confidence, PMID support) disappears after filtering + re-clustering at lower resolution
**Cause**: Rare cell types don't form independent clusters at lower resolution → absorbed into larger clusters
**Fix**: `_preserve_lost_cell_types()` compares previous vs current annotations, restores labels for cells that were concentrated in one cluster
**See**: `references/auto_mode_context_aware_filtering.md`

### Pitfall 45: Debug mode for per-iteration visualization
**Symptom**: Hard to diagnose what happens between iterations
**Fix**: Use `--debug` flag to save per-iteration UMAP and annotation plots:
```
plots/auto/iter_1/ cluster_umap_leiden.png, annotate_umap_cell_type.png, ...
plots/auto/iter_2/ ...
```
Default OFF. Enable for testing/debugging iterative behavior.

### Pitfall 36: mode_auto missing annotation plots
**Symptom**: Running `--mode auto --plot-dir plots/` generates only cluster UMAP plots, not annotation plots (cell_type UMAP, dotplot, rank_genes).
**Cause**: `mode_auto()` only called `plotter.plot_cluster()`, not `plotter.plot_annotate()`.
**Fix**: Added `plot_annotate()` call after `plot_cluster()` in mode_auto:
```python
# In mode_auto(), after plot_cluster():
plotter.plot_cluster(adata, cluster_key="leiden", sample_key=resolved_batch_key)

# NEW: Generate annotation plots
annotation_keys = []
if "cell_type" in adata.obs.columns:
    annotation_keys.append("cell_type")
if "llm_label" in adata.obs.columns:
    annotation_keys.append("llm_label")

has_rank_genes = "rank_genes_groups" in adata.uns
plotter.plot_annotate(
    adata,
    marker_file="",
    annotate_group="leiden",
    annotation_keys=annotation_keys,
    has_rank_genes=has_rank_genes,
)
```
**Output**: Generates `annotate_umap_cell_type.png`, `annotate_deg_dotplot.png`, `annotate_rank_genes_groups.png`, `cluster_umap_leiden.png`, `cluster_umap_sample_id.png`.

### Pitfall 46: Orchestrator prompt too complex → empty action (CRITICAL)
**Symptom**: Orchestrator returns empty `action`, defaults to "accept". Log shows:
```
Orchestrator returned invalid action '' — defaulting to 'accept'.
```
**Cause**: Orchestrator prompt has too many verbose rules, action descriptions, and structural checks. LLM (especially smaller models like mimo-v2.5-pro) gets overwhelmed and returns malformed JSON or JSON without the `action` field.
**Fix**: Keep orchestrator prompt MINIMAL:
- 1-line instruction per action (not paragraphs)
- Remove rules_block entirely — put key rules inline in action descriptions
- Include structural signals as data (sep_summary, ct_summary), not as instructions
- Always include a JSON schema example in the prompt
**Correct prompt structure**:
```
You are the orchestrator of an scRNA-seq annotation pipeline.
Decide: accept, correct, filter, or recluster.
Round {n}/{max}. Current resolution: {res}.
{ct_summary}  ← cell types with multiple clusters
{sep_summary} ← over_clustering + misannotated from separation_diag

## Available actions (choose EXACTLY ONE)
1. "accept" — good enough. Use when most trust=high/medium AND no over_clustering AND no misannotated.
2. "correct_annotations" — relabel trust=low + alternative!=null. REQUIRES: annotation_corrections.
3. "filter_and_recluster" — drop bad cells. REQUIRES: filter_plan.
4. "adjust_resolution_and_recluster" — merge over-fragmented. Use when Jaccard>0.3. Lower by ~0.15-0.2. REQUIRES: new_resolution.

Output ONLY valid JSON: {"action": "...", "reasoning": "...", ...}

## STATE
{state_json}
```
**Rule**: Never add more than 4-5 lines per action. The LLM needs to parse the prompt AND produce structured JSON — don't fill its context with rules.

### Pitfall 47: Orchestrator sets same resolution → wasted round
**Symptom**: Orchestrator chooses adjust_resolution_and_recluster but sets `new_resolution` to the same value as current. Next round produces identical clustering.
**Cause**: LLM doesn't know the current resolution (not in prompt) or doesn't follow the "lower by ~0.15-0.2" instruction.
**Fix**: TWO safeguards:
1. Include `Current resolution: {resolution}` in orchestrator prompt header
2. In mode_auto, validate that `new_resolution != current`:
```python
if float(new_res) == resolution:
    resolution = max(0.05, resolution - 0.2)
    logging.warning("CP set same resolution — forcing decrease to %.2f", resolution)
```
**Pass resolution through chain**: `_build_orchestrator_prompt(resolution=...)` ← `_call_orchestrator(resolution=...)` ← `mode_auto`

### Pitfall 48: PubMed XML parsing NoneType crash
**Symptom**: `'NoneType' object is not subscriptable` during PubMed efetch. Affects specific genes (e.g., TAGLN, CKS2).
**Cause**: Some PubMed articles have `<PubmedArticle>` elements with missing or empty `<PMID>`, `<ArticleTitle>`, or `<PubDate>`. Accessing `.text` on a None element or indexing None.
**Fix**: Wrap each article in try/except + guard all field access:
```python
for article in root.findall(".//PubmedArticle"):
    try:
        pmid_el = article.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = str(pmid_el.text).strip()
        title = str(title_el.text).strip() if title_el is not None and title_el.text else ""
        # ... same for year
        if pmid:
            results.append({"pmid": pmid, "title": title[:120], "year": year})
    except (AttributeError, TypeError, ValueError):
        continue
```

### Pitfall 49: PubMed verification query too specific → all markers "unverified"
**Symptom**: `_verify_tissue_markers` reports 35/45 markers "NOT found on PubMed" including well-known markers like CD68, PECAM1, FOXL2.
**Cause**: Search query `{gene} AND {cell_type} AND {tissue}` is too specific. "CD68 AND Macrophage AND macaque (Macaca mulatta) ovaries" has no exact PubMed match.
**Fix**: In `_verify_tissue_markers`, search with just `{gene} AND {cell_type}` (no tissue context):
```python
refs = _search_pubmed(gene, ct, tissue="", max_results=1)
```
The purpose is to verify the marker EXISTS, not to find the exact tissue context.

### Pitfall 50: Orchestrator uses cluster count instead of Jaccard for structural decisions
**Symptom**: Orchestrator prompt says "NO same cell_type appears in >2 clusters" as accept criterion. This is biologically wrong — proliferating Granulosa vs quiescent Granulosa are legitimate subtypes.
**Root cause**: Same cell type CAN appear in multiple clusters with LOW Jaccard (different markers = legitimate subtypes). Only HIGH Jaccard (>0.3) = over-fragmentation (same markers split).
**Fix**: Use `_check_cell_type_separation` metrics (Jaccard, max_distance) instead of cluster counts:
- Jaccard > 0.3 → over-clustering → adjust_resolution
- Jaccard ≤ 0.3 → misannotated or legitimate subtypes → correct_annotations or accept
- LOW Jaccard + SMALL max_distance → legitimate biological subtypes → accept
**CRITICAL**: The orchestrator prompt must reference separation_diag data, not instruct the LLM to count clusters.

### Pitfall 35: Same cell type split across distant UMAP clusters
**Symptom**: Same cell type (e.g., Stromal) appears in 2-3 separate Leiden clusters that are far apart in UMAP space. User says "同一种细胞在UMAP上分离过远" (same cell type separated too far).
**Cause**: Two possibilities:
1. **Over-clustering** (resolution too high) splits biologically continuous populations
2. **Annotation error** — LLM mislabeled a low-quality cluster as a known cell type

**Detection**: `_check_cell_type_separation()` now uses **marker Jaccard similarity** to distinguish:
1. Computes UMAP centroid for each cluster
2. Groups clusters by cell_type
3. Computes pairwise UMAP distance between same-type clusters
4. If max distance > threshold (5.0), compares `key_markers` between clusters:
   - **Jaccard > 0.3** → genuine over-clustering (markers match) → suggest lower resolution
   - **Jaccard ≤ 0.3** → annotation error (markers diverge) → flag smallest cluster as misannotated

**Fix for over-clustering**: In `mode_auto`, Step 3.5 adjusts resolution:
```python
needs_reclustering, separation_diag = _check_cell_type_separation(
    adata, cell_type_key="cell_type", cluster_key="leiden",
    distance_threshold=5.0, annotations=annotations)
if needs_reclustering and separation_diag.get("suggested_resolution"):
    suggested_res = separation_diag["suggested_resolution"]
    if suggested_res < resolution:
        resolution = suggested_res
```

**Fix for misannotation**: Flagged clusters get added to quality_reports for filtering:
```python
misannotated = separation_diag.get("misannotated", [])
for ma in misannotated:
    flag_cluster = ma["flagged_cluster"]
    # Add to quality_reports with misannotated_low_marker_overlap flag
```

**Separation ratio thresholds** (for over-clustering):
- >30% cell types separated → resolution 0.2 (aggressive merge)
- >10% separated → resolution 0.25
- Otherwise → resolution 0.3

**Priority**: Filter low-quality/misannotated FIRST, then adjust resolution for over-clustering. Misannotation is more common than over-clustering.

### Pitfall 37: LLM annotates clusters in isolation (no cross-cluster context)
**Symptom**: LLM assigns same cell type to multiple clusters but doesn't know they exist. Can't detect subclusters or over-clustering.
**Cause**: Each cluster was annotated independently — LLM never saw other clusters' annotations or UMAP distances.
**Fix**: Modified `_build_auto_annotation_prompt()` to include:
1. **Other clusters' annotations**: cluster_id, cell_type, confidence, top 5 markers, UMAP distance
2. **Subcluster detection instructions**: LLM must check if markers are similar to another cluster
3. **New output fields**: `is_subcluster` (bool), `parent_cluster` (str), `should_merge` (bool)
```python
# In _build_auto_annotation_prompt():
other_context = ""
if other_annotations:
    for cid, ann in other_annotations.items():
        ct = ann.get("cell_type", "Unknown")
        markers = ", ".join(ann.get("key_markers", [])[:5])
        dist_info = f" (UMAP distance: {umap_distances[cid]:.1f})" if cid in umap_distances else ""
        other_lines.append(f"  - Cluster {cid}: {ct} (markers: {markers}){dist_info}")
```
**Decision rules given to LLM**:
- Markers similar + UMAP close (< 5.0) → is_subcluster=true, should_merge=true
- Markers similar + UMAP far (> 10.0) → over-clustering, still merge
- Markers different + UMAP close → distinct cell types
**Result**: LLM correctly identifies subclusters (e.g., Granulosa subcluster) and merge candidates (e.g., Endothelial should merge with parent).

### Pitfall 32: TE genes dominate clustering in scTE data (CRITICAL)
**Symptom**: Large clusters defined entirely by TE expression (ERVK_high, Alu_high) with no protein-coding marker genes. UMAP shows TE-expression-based separation rather than cell-type-based separation.
**Cause**: scTE pipeline quantifies both genes AND transposable elements. When TE genes are included in HVG selection, cells with similar TE profiles cluster together regardless of cell type. Example: Alu_high (481 cells) had ZERO protein-coding markers in top100 — all were Alu/SINE/L1/L2/MIR elements. ERVK_high (3373 cells) had125 protein-coding markers alongside ERVK elements.
**Detection**: Check marker gene composition per cluster. If a cluster's top markers are >80% TE/repeat elements with no protein-coding genes, it's TE-dominated.
**Diagnostic QC comparison** (Alu_high vs ERVK_high — both are NOT low-quality):
| Metric | Alu_high | ERVK_high | Normal cells |
|--------|----------|-----------|-------------|
| n_genes | 1361 | 2574 | 2000-2700 |
| total_counts | 5801 | 10161 | 7000-11000 |
| MT% | 0.44% | 0.16% | 0.1-0.2% |
| TE% of UMI | 26.69% | 13.47% | 3-8% |
| Top20 gene% | 40.55% | 24.04% | 24-28% |
Alu_high has fewer detected genes because reads map to repeats instead of genes — this is biological (TE derepression), NOT a QC artifact. Do NOT filter these cells as "low quality".
**Fix — annotate gene types, then exclude TE before HVG**:
```python
# Step 1: Annotate gene types using GTF references
from scRNAseq import annotate_gene_type
annotate_gene_type(adata, te_gtf="rmsk.gtf", gene_gtf="genes.gtf")
# adata.var['gene_type'] now has: 'TE', 'protein_coding', 'lncRNA', etc.

# Step 2: Filter TE before HVG selection
from scRNAseq import _filter_te
adata_coding = _filter_te(adata)  # removes all genes where gene_type == 'TE'

# Step 3: Cluster on protein-coding genes only
sc.pp.highly_variable_genes(adata_coding, n_top_genes=3000)
# ... rest of pipeline
```
**CLI**: `scRNAseq.py cluster --skip-te` or `scRNAseq.py auto --skip-te`
**Key insight**: TE expression should be analyzed as a SEPARATE dimension (overlay on clusters), not as a clustering driver. Cells with high TE expression will scatter across their real cell-type clusters instead of forming artificial TE-defined clusters.

### Pitfall 33: sc.pl.umap color expects obs column names, not uns keys
(Same as Pitfall 30 — already documented above.)

### Pitfall 31: Sparse matrix indexing fails with pandas boolean Series
**Symptom**: `AttributeError: 'Series' object has no attribute 'nonzero'` when indexing `adata[boolean_mask]`
**Cause**: `adata.X` is scipy sparse. Indexing with a pandas boolean Series fails because scipy sparse expects numpy arrays (which have `.nonzero()`), not pandas Series (which don't).
**Fix**: Use `.values` to convert pandas boolean Series to numpy array:
```python
# WRONG — pandas Series doesn't have .nonzero()
mask = adata.obs['cell_type'] == 'ERVK_high'
adata[mask]  # crashes on sparse X

# CORRECT — .values converts to numpy bool array
mask = (adata.obs['cell_type'] == 'ERVK_high').values
adata[mask]  # works

# Also works with scipy sparse .mean():
ervk_mean = np.array(X_raw[mask].mean(axis=0)).flatten()
other_mean = np.array(X_raw[~mask].mean(axis=0)).flatten()
```
**Note**: This is related to Pitfall 1 (BooleanArray) but distinct. Pitfall 1 is about `adata.var_names.str.startswith()` returning nullable BooleanArray. Pitfall 31 is about `adata.obs[col] == value` returning a pandas Series that scipy sparse can't index with.

### Pitfall 10: Gene name case varies by species
**Rhesus macaque (Macaca mulatta)**: Gene names use ENSMMUG prefix (e.g., `ENSMMUG00000064799`). MT genes are UPPERCASE: `MT-ND1`, `MT-COX1`, etc. KRT8 is ABSENT in macaque genome.
**Mouse (Mus musculus)**: MT genes are lowercase: `mt-Nd1`, `mt-Co1`.
**Human**: MT genes are uppercase: `MT-ND1`, `MT-COX1`.

Always check species before setting MT gene detection:
```python
# For rhesus macaque / human (uppercase MT-):
adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-"))
# For mouse (lowercase mt-):
adata.var["mt"] = np.array(adata.var_names.str.startswith("mt-"))
# Universal (covers both):
adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-") | adata.var_names.str.startswith("mt-"))
```

## Step 7: Cluster Merging (Critical for Purity)

When the same cell type is split into multiple disconnected Leiden clusters, they appear as fragmented islands in UMAP. The user will notice "B1靠近A而不是B2" (B1 closer to A than to B2). Merge these using connected components.

**CRITICAL**: The merge function MUST update `leiden` directly (not just create `leiden_merged`). After merging, you MUST redo DEG + annotation on the merged clusters. If you only create `leiden_merged` without updating `leiden`, all downstream steps (DEG, annotation, plots) will still use the old fragmented clusters.

```python
from scipy.sparse.csgraph import connected_components

def merge_fragmented_clusters(adata, cluster_anno):
    """Merge disconnected clusters of the same cell type.
    
    CRITICAL: Updates adata.obs['leiden'] in place with merged labels.
    After calling this, you MUST redo:
      adata = step_deg(adata)
      adata = step_annotate(adata, marker_dict, plot_dir)
    """
    if "connectivities" not in adata.obsp:
        return adata

    ct_clusters = {}
    for cluster, info in cluster_anno.items():
        ct = info["cell_type"]
        ct_clusters.setdefault(ct, []).append(cluster)

    # Only merge cell types that span multiple clusters
    multi_ct = {ct: cl for ct, cl in ct_clusters.items() 
                if len(cl) > 1 and not ct.startswith("Unknown")}
    if not multi_ct:
        return adata

    merge_map = {}
    merged_id = 0

    for ct, clusters in multi_ct.items():
        ct_mask = adata.obs["leiden"].isin(clusters).values
        ct_indices = np.where(ct_mask)[0]
        if len(ct_indices) == 0:
            continue

        conn = adata.obsp["connectivities"]
        sub_conn = conn[np.ix_(ct_indices, ct_indices)]
        n_components, labels = connected_components(sub_conn, directed=False)
        component_map = {idx: labels[i] for i, idx in enumerate(ct_indices)}

        for cluster in clusters:
            cluster_mask = adata.obs["leiden"] == cluster
            cluster_indices = np.where(cluster_mask)[0]
            if len(cluster_indices) == 0:
                continue
            cluster_components = [component_map.get(idx, -1) for idx in cluster_indices]
            main_component = max(set(cluster_components), key=cluster_components.count)
            merge_key = f"{ct}_{main_component}"
            if merge_key not in merge_map:
                merge_map[merge_key] = merged_id
                merged_id += 1
            merge_map[cluster] = merge_map[merge_key]

    # Non-fragmented clusters keep their own ID
    for cluster in adata.obs["leiden"].cat.categories:
        if cluster not in merge_map:
            merge_map[cluster] = merged_id
            merged_id += 1

    # CRITICAL: update leiden directly, not just leiden_merged
    adata.obs["leiden_merged"] = adata.obs["leiden"].map(merge_map).astype(str).astype("category")
    adata.obs["leiden"] = adata.obs["leiden_merged"].copy()
    return adata
```

**Pipeline order after merge**:
```python
adata = step_deg(adata)           # DEG on original clusters
adata = step_annotate(adata, ...)  # annotate original clusters
adata = step_merge_clusters(adata, ...)  # merge + update leiden
# MUST redo DEG + annotation on merged clusters:
adata = step_deg(adata)
adata = step_annotate(adata, ...)
step_plots(adata, ...)
```

**Verification** — after merge, every cell type should map to exactly one leiden cluster:
```python
for ct in sorted(adata.obs['cell_type'].unique()):
    clusters = sorted(adata.obs.loc[adata.obs['cell_type'] == ct, 'leiden'].unique())
    assert len(clusters) == 1, f"⚠️ {ct} spans {len(clusters)} clusters!"
```

### Pitfall 7: Fragmented clusters of same cell type
**Symptom**: Same cell type split into disconnected UMAP islands; B1 closer to A than to B2; "注释的同种细胞没有聚在一起"
**Cause**: Over-clustering (resolution too high) splits biologically continuous populations
**Diagnostic**: Compare max distance between same-type clusters vs min distance to different types
**Fix**: (1) Lower resolution to 0.3-0.4, (2) Merge clusters post-annotation using leiden_merged:
```python
# Simple merge: assign same cell_type label → create leiden_merged
label_to_merged = {}
for clust, ct in cluster_to_ct.items():
    if ct not in label_to_merged:
        label_to_merged[ct] = str(len(label_to_merged))
adata.obs["leiden_merged"] = adata.obs["cell_type"].map(label_to_merged).astype("category")
```
Use `leiden_merged` for UMAP coloring (not `cell_type` which has category issues). Build merged_palette from adata.obs mapping.
**User signal**: "细胞群颜色不纯净", "同类cluster分散", "B1靠近A而不是B2", "注释的同种细胞没有聚在一起"

### Pitfall 8: Shared markers cause cell type proximity
**Symptom**: Pericyte and Smooth_muscle too close in UMAP; Stromal and Theca overlapping
**Cause**: Biologically related cell types share markers (e.g., ACTA2/TAGLN in both Pericyte and Smooth_muscle; DCN/VIM/PDGFRA in both Stromal and Theca)
**Diagnostic**: Check marker expression overlap between close cell types (>50% shared = expect proximity)
**Expected**: Central UMAP region (Stromal/Smooth_muscle/Pericyte/OSE) forms a continuum — this is biology, not a bug
**Fix**: Use more specific markers, or accept biological continuity and explain in paper

## Post-Clustering QC Filtering (Cluster-Level Flagging + Cell-Level Filtering)

**User explicitly corrected twice:**
1. "去除低质量细胞不是去除整个cluster" — remove low-quality CELLS, not entire clusters
2. "你需要思考cluster对过滤的作用是什么,为什么要cluster之后再过滤" — think about WHY cluster first

### Why Cluster First, Then Filter?

Clustering provides **biological context**. Without it, cell-level QC (gene count, UMI, MT%) would also remove biologically real cells that happen to have lower expression (e.g., red blood cells, small neurons). With clustering:

- **Normal cluster** (markers are real genes): keep ALL cells — even low-gene cells belong here biologically
- **Suspicious cluster** (markers are ENSMMUG/MT genes): filter individual cells more aggressively within this cluster

**Logic**: A cell with 800 genes in a healthy cluster is fine. The same cell in a cluster where most cells have 400 genes and markers are all ENSMMUG is suspicious — it clusters with noise.

### Workflow

```
1. Cluster with scRNAseq.py --mode cluster
2. Analyze each cluster:
   - Mean genes, mean UMI, mean MT%
   - Top N marker composition: % ENSMMUG (unannotated), % MT genes
3. Flag clusters with suspicious patterns
4. For flagged clusters: apply strict cell-level QC (min_genes, min_counts, max_mt%)
   For normal clusters: keep all cells
5. Save RAW counts for filtered cells (NOT processed data)
6. Re-cluster with scRNAseq.py --mode cluster
```

### Cluster Flagging Thresholds

```python
CLUSTER_THRESHOLDS = {
    "min_genes": 800.0,           # Mean genes per cluster
    "min_counts": 3000.0,         # Mean UMI per cluster
    "max_pct_unannotated": 50.0,  # % ENSMMUG in top N markers
    "max_pct_mt_genes": 30.0,     # % MT genes in top N markers
    "top_n_markers": 20,
}
```

### Cell-Level Filtering (Within Flagged Clusters Only)

```python
CELL_THRESHOLDS = {
    "min_genes": 800,    # Stricter than initial QC
    "min_counts": 3000,  # Stricter than initial QC
    "max_pct_mt": 20.0,
}

# For flagged clusters: apply cell-level QC
# For normal clusters: keep all cells
for cluster in flagged_clusters:
    cluster_cells = adata.obs[adata.obs["leiden"] == cluster]
    cell_qc_mask = (
        (cluster_cells["n_genes_by_counts"] >= CELL_THRESHOLDS["min_genes"])
        & (cluster_cells["total_counts"] >= CELL_THRESHOLDS["min_counts"])
        & (cluster_cells["pct_counts_mt"] <= CELL_THRESHOLDS["max_pct_mt"])
    )
    # Remove cells that fail QC within this cluster
    cells_to_remove = cluster_cells[~cell_qc_mask].index
    keep_mask[cells_to_remove] = False
```

### Pitfall 28: Re-clustering fails on processed data (CRITICAL)

**Symptom**: `ValueError: Bin edges must be unique: Index([nan, nan, ...])` when re-clustering after filtering.

**Cause**: The filtered h5ad was saved from processed (normalized, log-transformed) data. When `scRNAseq.py --mode cluster` runs, it calls `sc.pp.normalize_total()` then `sc.pp.log1p()` again. This fails because:
1. "WARNING: adata.X seems to be already log-transformed"
2. Cells with zero counts after filtering cause NaN in log1p
3. HVG detection fails on NaN-filled data

**Fix**: Save RAW counts for filtered cells, NOT processed data:
```python
# WRONG: saves processed data
adata_filtered.write_h5ad(output)

# CORRECT: save raw counts from original merged file
adata_raw = ad.read_h5ad(original_merged_file)
adata_raw_filtered = adata_raw[adata_filtered.obs.index].copy()
adata_raw_filtered.write_h5ad(output)
```

**Key**: Always re-read from the original merged h5ad to get raw counts. The clustered h5ad has processed data (normalized, log-transformed, scaled) that cannot be re-clustered.

### Example Test Script Pattern

```python
# Step 1: Cluster
subprocess.run([sys.executable, "scRNAseq.py", "--mode", "cluster",
                "--input", str(merged_file), "--output", str(clustered_file), ...])

# Step 2: Analyze cluster quality
adata = ad.read_h5ad(clustered_file)
cluster_report = analyze_cluster_quality(adata)  # markers + QC metrics

# Step 3: Filter cells in flagged clusters
adata_filtered, cell_report = filter_cells_in_flagged_clusters(adata, cluster_report)

# Step 4: Save RAW counts (NOT processed data!)
adata_raw = ad.read_h5ad(merged_file)
adata_raw_filtered = adata_raw[adata_filtered.obs.index].copy()
adata_raw_filtered.write_h5ad(filtered_file)

# Step 5: Re-cluster
subprocess.run([sys.executable, "scRNAseq.py", "--mode", "cluster",
                "--input", str(filtered_file), "--output", str(reclustered_file), ...])
```

## QC-First Workflow (CRITICAL)

**User explicitly corrected: "没有思考qc是否合理等等" (didn't check if QC is reasonable)**

**RULE: Always check QC metrics BEFORE clustering. Never jump to clustering/annotation without validating QC first.**

### QC Validation Checklist (run BEFORE any clustering):
```python
# 1. Check basic stats
print(adata.obs['n_genes_by_counts'].describe())
print(adata.obs['total_counts'].describe())
print(adata.obs['pct_counts_mt'].describe())

# 2. Check for low-quality cells
low_umi = adata.obs['total_counts'] < 1000
low_genes = adata.obs['n_genes_by_counts'] < 500
high_mt = adata.obs['pct_counts_mt'] > 10
print(f'Low UMI (<1000): {low_umi.sum()} ({low_umi.mean()*100:.1f}%)')
print(f'Low genes (<500): {low_genes.sum()} ({low_genes.mean()*100:.1f}%)')
print(f'High MT% (>10%): {high_mt.sum()} ({high_mt.mean()*100:.1f}%)')

# 3. Check doublet detection
if 'doublet_score' in adata.obs.columns:
    print(adata.obs['doublet_score'].describe())
    print(f'High doublet score (>0.1): {(adata.obs["doublet_score"] > 0.1).sum()}')
    print(f'High doublet score (>0.2): {(adata.obs["doublet_score"] > 0.2).sum()}')

# 4. Check sample distribution
print(adata.obs['sample_id'].value_counts())

# 5. Check batch effect (PCA distance between samples)
sample1_mask = adata.obs['sample_id'] == sample1
sample2_mask = adata.obs['sample_id'] == sample2
centroid1 = adata.obsm['X_pca'][sample1_mask].mean(axis=0)
centroid2 = adata.obsm['X_pca'][sample2_mask].mean(axis=0)
print(f'PCA distance between samples: {np.linalg.norm(centroid1 - centroid2):.3f}')
```

### QC Rules:
1. **If clustering looks bad → check QC first** before trying different UMAP parameters
2. **Holes in UMAP are often caused by low-quality cells**, not just min_dist
3. **Scattered points are often doublets or dying cells**, not clustering artifacts
4. **Strict QC dramatically improves clustering** — filtering out15% of cells can make clusters10x cleaner

### Strict QC Parameters (validated for macaque ovary):
```python
adata = adata[
    (adata.obs['n_genes_by_counts'] >= 500) &
    (adata.obs['n_genes_by_counts'] <= 5000) &
    (adata.obs['pct_counts_mt'] <= 5) &
    (adata.obs['total_counts'] >= 1500) &
    (adata.obs['total_counts'] <= 25000) &
    (adata.obs['doublet_score'] < 0.1) &
    ((adata.obs['total_counts'] / adata.obs['n_genes_by_counts']) < 10) &
    ((adata.obs['total_counts'] / adata.obs['n_genes_by_counts']) > 1)
].copy()
```

**Typical effect**: Filters out15-20% of cells, remaining cells form tight, hole-free clusters.

### Workflow Order:
```
1. Load merged h5ad
2. Check QC metrics (describe, percentiles, sample distribution)
3. Apply strict QC filters
4. Verify QC improvement (re-check stats)
5. Preprocess → HVG → PCA → Harmony → neighbors → UMAP → Leiden
6. Check clustering quality (dense? holes? scattered points?)
7. If clustering bad → go back to step2 (check QC again)
8. Only when clustering is good → proceed to annotation
```

**User correction**: "聚类效果一般,你没有把聚类调整到完美层次,就急着注释了" (clustering is mediocre, you didn't perfect clustering before rushing to annotation). NEVER annotate before clustering is good.

## Parameter Guidelines

| Parameter | Loose | Tight separation | Ultra-compact |
|-----------|-------|------------------|---------------|
| n_top_genes | 2000 | 3000 | 5000 |
| n_neighbors | 30 | 50 | 100 |
| n_pcs | auto (default) | auto | auto |
| min_dist | 0.3 | 0.1 | 0.001 |
| spread | 1.0 | 0.8 | 1.0 |
| resolution | 1.0 (scanpy default) | user-directed | user-directed |
| outlier_filter | none | 2% | 2% |

**Resolution**: Default is 1.0 (scanpy default). User explicitly stated "我从来没有推荐范围" — there is NO recommended range. Adjust based on biological context and user direction, not arbitrary defaults.

**n_pcs**: Default is auto-detection (`auto_n_pcs=True`). User explicitly stated "n_pcs是自动决定的，不是说数量越多越好". The `detect_n_pcs()` algorithm uses relative change rate + sliding window stability (方案C) to find the plateau.

### HVG Selection: flavor matters (CRITICAL)

**Tested on macaque ovary (19144 cells):** `cell_ranger` flavor gives significantly better clustering than `seurat` for the same `n_top_genes`. Vision analysis confirmed `2000 cell_ranger` produces "compact clusters, clear separation, minimal scattered points" while `3000 seurat` has scattered points and overlapping clusters.

**Tested combinations** (8 total, 2 flavors × 4 gene counts):
- `2000 cell_ranger` — **BEST**: compact, well-separated, minimal scattered points
- `3000 cell_ranger` — good but more small clusters
- `5000 cell_ranger` — compact but more noise
- `1000 cell_ranger` — too few genes, loses signal
- `seurat` flavor (all counts) — consistently worse than cell_ranger: more scattered points, less compact

**Rule**: For macaque/reproductive tissues, prefer `flavor="cell_ranger"` over `flavor="seurat"`. Start with `n_top_genes=2000`.

### PCA Dimensionality

**User suggested 11 PCs** instead of default 50. Lower PC count can improve UMAP visualization by reducing noise dimensions. Test with the boundary cell metric (see below) to validate.

**Auto-detection methods** (see `references/elbow-detection-auto-params.md`):
- `cumvar` (DEFAULT) — cumulative variance reaches 85%. Standard single-cell practice.
- `plateau` — first PC where variance stops declining significantly.
- `curvature` — maximum second derivative (elbow). NOT recommended as default for scRNA-seq.

**User correction**: "PCA不应该去平稳点吗，按照单细胞实践来说" — PCA should go to the plateau/cumulative variance point, NOT the elbow. Use `cumvar` as default.

**Boundary cell analysis** — diagnostic for UMAP quality:
```python
# Calculate % of cells closer to another cluster's centroid than their own
centroids = {}
for clust in np.unique(leiden_labels):
    mask = leiden_labels == clust
    centroids[clust] = umap_coords[mask].mean(axis=0)

boundary_count = 0
for i in range(adata.n_obs):
    clust = leiden_labels[i]
    own_dist = np.linalg.norm(umap_coords[i] - centroids[clust])
    min_other = min(np.linalg.norm(umap_coords[i] - centroids[c])
                    for c in centroids if c != clust)
    if min_other < own_dist:
        boundary_count += 1

boundary_pct = boundary_count / adata.n_obs * 100
print(f"Boundary cells: {boundary_pct:.1f}%")
# <5% = excellent, 5-10% = good, >10% = needs improvement
```

This metric quantifies how well UMAP preserves cluster structure. ~6% boundary cells is typical; >10% suggests UMAP parameters or HVG selection need adjustment.

### Root Cause Analysis Workflow (CRITICAL)

**User explicitly corrected**: "好好反思一下" (reflect properly), "为什么总有一些分散细胞群" (why always scattered groups)

**RULE: When clustering looks bad, diagnose BEFORE changing parameters.**

**Step-by-step diagnosis:**
1. **Check QC first** — are there low-quality cells causing holes/scatter?
2. **Check HVG selection** — try different `flavor` and `n_top_genes`
3. **Check batch effect** — are samples mixing in UMAP?
4. **Check PCA variance** — how many PCs are needed?
5. **Only then adjust UMAP parameters** — min_dist, spread, n_neighbors, resolution

**Wrong approach** (what I did): Try random parameter combinations without understanding root cause. User was frustrated: "你确定是QC的问题吗" (are you sure it's a QC problem?), "一直以来你都没尝试" (you never tried HVG selection).

**Right approach**: Analyze → diagnose → fix specific issue → verify → move to next issue.

**Common root causes (in order of likelihood):**
1. **Bad HVG selection** — wrong flavor or n_top_genes → try cell_ranger flavor
2. **Poor QC** — low-quality cells scattered in UMAP → stricter filters
3. **Batch effect not corrected** — samples don't mix → check Harmony parameters
4. **Wrong PCA dimensionality** — too many PCs add noise → try fewer PCs
5. **UMAP parameters** — only after fixing above → adjust min_dist/spread/resolution

**Note**: Resolution 0.8 on ovaries creates21 clusters with a big mixed blob (continuous granulosa/theca differentiation trajectory). Resolution 0.4 merges these into ~16 clean, distinct islands. Always check UMAP after clustering — if you see a "star-shaped" connected structure with multiple clusters inside, lower resolution.

**spread parameter controls cluster proximity**: lower spread (0.3) = clusters far apart, higher spread (1.0) = clusters closer together. User wants clusters close but not overlapping. User complained "分散的太开了,导致cluster看上去很小" with spread=0.3 — use spread=1.0 to bring clusters closer.

**min_dist parameter controls cluster tightness**: 0.001 = ultra-compact (user preference for "tight clusters, close together, no overlap"), 0.01 = very tight, 0.1 = standard. Lower min_dist creates tighter clusters but may create holes if QC is poor.

**Validated macaque ovary config**: `n_top_genes=3000, n_neighbors=50, n_pcs=50, min_dist=0.1, spread=0.8, resolution=0.3` produces compact clusters with fewer holes. `min_dist=0.05` creates too many internal holes/空洞; `min_dist=0.1` with `spread=0.8` is better balanced. User complained "细胞群不够紧密,很多空洞" with min_dist=0.05.

**Ultra-compact UMAP config** (user preference: tight clusters, close together, no overlap):
```python
min_dist=0.01, spread=0.8, resolution=0.5
batch_correction="harmony", theta=3, lamb=0.5, nclust=50
# NO outlier filtering — keep all cells
```
User complained "分散的太开了,导致cluster看上去很小" with spread=0.3 — spread=0.8 brings clusters closer together while maintaining separation.

**CRITICAL: Do NOT remove edge cells.** User explicitly corrected: "为什么要去除边缘细胞" (why remove edge cells?). Removing cells at cluster edges is WRONG because:
- Edge cells may contain real biology (transitional states, rare subtypes)
- It reduces cell count unnecessarily
- It doesn't solve the real problem (bad UMAP parameters)
- Fix UMAP parameters instead of deleting data

**Validated clean-separation config** (tested on macaque ovary,19144 cells):
```python
min_dist=0.01, spread=0.8, resolution=0.5
harmony_theta=3, harmony_lamb=0.5, harmony_nclust=50
n_neighbors=50, n_pcs=50
# Result: 16 compact, well-separated clusters, all cells preserved
```
This produces clusters that are compact and close together without overlap. Resolution 0.3 creates too many overlapping clusters (21 clusters with mixed blob); 0.5 gives clean separation (16 clusters).

**Validated macaque hystera config**: `n_neighbors=50, resolution=0.4` produces clean, well-separated clusters for uterine tissue.

For Nature-quality: always use Harmony batch correction when >1 sample.

**Tight separation mode**: Use `min_dist=0.1, spread=0.8, n_neighbors=50, resolution=0.3` when user complains about mixed/impure clusters. Outlier filtering (>1.5σ from centroid, re-embed) removes scattered points. min_dist=0.05 creates too many internal holes; 0.1 is better balanced.

**Outlier filtering** (add after initial Leiden): Remove cells >1.5σ from cluster centroid in UMAP space, then re-embed. Removes2-5% of cells, dramatically cleans scattered points. See Pitfall21.

See `references/validated_configs_20260904.md` for tested parameter combinations.

**Expected biological continuity**: Central UMAP regions connecting Stromal, Smooth_muscle, Pericyte, OSE, and Proliferating are biologically realistic — these mesenchymal/epithelial cell types share大量基因表达, forming a continuum in expression space. UMAP reflects this. Clean separation of these types requires unique markers, not just parameter tuning.

## Post-Filtering Annotation with annotate_all.py

After re-clustering filtered data, annotate using `annotate_all.py` (NOT `scRNAseq.py --mode annotate`):

```bash
# annotate_all.py expects _clustered.h5ad in filename for auto-output naming
# If your file is named differently, copy with correct suffix:
cp hystera_cellranger_reclustered_v2.h5ad hystera_cellranger_reclustered_v2_clustered.h5ad

# MUST use absolute path to avoid empty dirname bug
python /path/to/annotate_all.py \
    --input /full/path/to/hystera_cellranger_reclustered_v2_clustered.h5ad \
    --tissue hystera \
    --counter cellranger
```

**Pitfall 29: annotate_all.py crashes on relative paths**
**Symptom**: `FileNotFoundError: [Errno2] No such file or directory: ''`
**Cause**: `os.path.dirname(output_h5ad)` returns empty string when input is a relative filename (no directory component)
**Fix**: Always use absolute paths for `--input`

**Output**: Generates `*_annotated.h5ad` + `*_markers.tsv` + plots in `plots/<counter>/cluster_annotate/`

## Marker File Format (TSV)
```
cell_type	markers
Oocyte	DDX4,DAZL,GDF9,ZP3,FIGLA,NOBOX,SYCP3
Granulosa	FSHR,CYP19A1,AMH,FOXL2,BMPR1B,LHCGR
```

Check markers exist in `adata.var_names` before running annotation. Shared markers between cell types (e.g., LHCGR in Granulosa AND Theca, STAR in Theca AND Luteal) reduce annotation purity — use unique markers when possible.

### Macaque Ovary Markers (validated)
All64 markers below confirmed present in both cellranger (26,509 genes) and scTE (19,141 genes) datasets:
- Oocyte: DDX4, DAZL, GDF9, ZP3, FIGLA, NOBOX, SYCP3
- Granulosa: FSHR, CYP19A1, AMH, FOXL2, BMPR1B, LHCGR
- Cumulus: FST, NR5A2, PPARG, CRHBP, GRB14, HAS2, PTX3 (specialized granulosa)
- Theca: CYP17A1, IGF1, STAR, CYP11A1
- Luteal: STAR, CYP11A1, HSD3B1, PTCH2, GPC5 (corpus luteum)
- Stromal: COL1A1, COL3A1, DCN, LUM, VIM, PDGFRA
- Smooth_muscle: ACTA2, MYH11, TAGLN, CNN1, DES
- Myofibroblast: ACTA2, MYH11, TAGLN, POSTN, IGFBP5, SFRP1 (SM+Stromal hybrid)
- Endothelial: PECAM1, VWF, CDH5, KDR, EMCN
- Lymphatic_endo: MMRN1, CCL21, PROX1, LYVE1, PDPN, CAVIN2, FLT4
- Macrophage: CD68, CD163, CD74, CSF1R, C1QA
- T_NK_cell: CD3E, CD3D, CD8A, NKG7, GZMB
- B_cell: CD79A, CD79B, MS4A1, PAX5
- OSE/Mesothelial: KRT18, EPCAM, WT1, LGR5, UPK3B, MSLN, ITLN1
- Pericyte: RGS5, PDGFRB, NOTCH3, ABCC9
- Proliferating: MKI67, TOP2A, PCNA, CENPF

**Note**: KRT8 absent in macaque genome. LHCGR shared between Granulosa/Theca. STAR shared between Theca/Luteal. These overlaps cause annotation ambiguity in those populations.

## Nature Reviewer Checklist

When preparing scRNA-seq for Nature/Cell-level journals, address these issues proactively:

### Issue 1: Missing Cell Types
**Reviewer concern**: "Oocyte/B_cell/Luteal not identified as separate clusters"
**Root cause**: These cell types are too rare to form independent Leiden clusters
**Investigation**: Trace marker-positive cells:
```python
for gene in ["DDX4", "CD79A", "HSD3B1"]:
    expr = adata[:, gene].X.toarray().flatten()
    positive = expr > 0
    print(f"{gene}: {positive.sum()} positive cells")
    print(adata.obs[positive]["cell_type"].value_counts())
```
**Fix**: Document as "detected but not clustered" in Methods. Store in `adata.uns["rare_cell_types"]`.

### Issue 2: UMAP Legend Required
Every cell type UMAP MUST have a color legend. Scanpy default omits it.
```python
sc.pl.umap(adata, color="cell_type", legend_loc="right margin",
           legend_fontsize=10, legend_fontoutline=2)
```

### Issue 3: Colorblind-Friendly Palette
Avoid red/green pairs. Use Okabe-Ito extended palette:
```python
CB_PALETTE = {
    "Endothelial":       "#0072B2",  # blue
    "Granulosa":         "#E69F00",  # orange
    "Macrophage":        "#009E73",  # green
    "OSE":               "#CC79A7",  # pink (NOT red)
    "Pericyte":          "#56B4E9",  # light blue
    "Proliferating (mixed)": "#F0E442",  # yellow
    "Smooth_muscle":     "#D55E00",  # vermillion
    "Stromal":           "#999999",  # grey
    "T_NK_cell":         "#000000",  # black
    "Theca":             "#882255",  # dark purple
}
```

### Issue 4: Proliferating is Not a Cell Type
MKI67/TOP2A are universal proliferation markers, not cell-type-specific.
Label as "Proliferating (mixed)" to indicate it spans multiple lineages.

### Issue 5: Doublet Verification
If marker X (e.g., CD79A) appears in unexpected cell type Y (e.g., Macrophage):
1. Check co-expression with Y's own markers (CD68, CD163)
2. If <30% co-expression → likely contamination/ambient RNA, not doublet
3. If >70% co-expression → likely doublet
4. Generate marker expression UMAP for visual verification

### Issue 6: STAR Background Expression
STAR+ cells in Stromal (3373 cells) mostly DON'T express Theca markers:
- Only 6.4% express CYP17A1, 8.3% express CYP11A1
- This is low-level background, not real Theca/Luteal cells

### Issue 7: Sample Mixing Verification
Always generate post-Harmony sample UMAP to prove batch correction worked.
```python
sc.pl.umap(adata, color="sample_id", title="Samples (post-Harmony)")
```

## Rare Cell Type Detection
```python
def detect_rare_cell_types(adata, marker_dict):
    """Detect cell types too rare to form independent clusters."""
    rare_types = {}
    for ct, genes in marker_dict.items():
        expr_matrix = np.zeros((adata.n_obs, len(genes)))
        for i, gene in enumerate(genes):
            if gene in adata.var_names:
                gexpr = adata[:, gene].X
                if hasattr(gexpr, 'toarray'):
                    gexpr = gexpr.toarray().flatten()
                expr_matrix[:, i] = gexpr
        co_expr = (expr_matrix > 0).sum(axis=1)
        n_multi = int((co_expr >= 2).sum())
        if n_multi > 0:
            rare_types[ct] = {"multi_marker": n_multi}
            adata.obs.loc[co_expr >= 2, "rare_cell_type"] = ct
    if rare_types:
        adata.uns["rare_cell_types"] = rare_types
    return rare_types
```

## Publication-Quality Plot Checklist (Nature Standards)

### Figure sizing
- Single column: 3.5 × 3 inches (89 × 76 mm)
- Double column: 7.2 × 4 inches (183 × 102 mm)
- Font base: 8pt (renders ≥6pt at50% reduction)
- Axis labels: 7pt, tick labels: 6pt
- Legend: 7pt, legend title: 8pt

### Figure Style Preference (CRITICAL)

**User prefers INDIVIDUAL figures, NOT multi-panel combinations.** User explicitly said "我不希望你绘制组合图,因为绘制的不咋地" (don't want combination figures, they don't look good). Generate separate PNG files for each plot type (umap_cell_type.png, umap_leiden.png, dotplot.png, etc.), NOT a single figure1_main.png with panels (a-d).

**Legend placement**: ALWAYS outside the plot (right side). Use `bbox_to_anchor=(1.02, 1.0)` with `loc="upper left"`. User explicitly complained about legends inside the plot.

```python
# CORRECT: legend outside, with border
leg = ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0),
                fontsize=7, frameon=True, framealpha=0.95, edgecolor="#cccccc",
                markerscale=1.0, handletextpad=0.4, columnspacing=0.5,
                borderaxespad=0., labelspacing=0.6, handlelength=1.2,
                scatterpoints=1, fancybox=True)
leg.get_frame().set_linewidth(0.5)

# WRONG: legend inside, no border, wrong marker size
ax.legend(loc="lower left", bbox_to_anchor=(0.0, 0.0), fontsize=5.5,
          markerscale=1.5, edgecolor="none", ...)
```

### Multi-panel Figure 1 Layout (Consolidated Main Figure)

Instead of separate individual plots, create ONE consolidated Figure1 with panels (a-d):

```python
from matplotlib.gridspec import GridSpec

# Nature-style rcParams
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.linewidth": 0.5,
    "axes.labelsize": 8,
    "axes.titlesize": 9,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2,
    "ytick.major.size": 2,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6.5,
    "legend.frameon": False,
    "legend.handletextpad": 0.3,
    "legend.columnspacing": 0.5,
    "lines.linewidth": 0.5,
})

fig = plt.figure(figsize=(7.2, 6.8), dpi=300)
gs = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 0.85],
                      hspace=0.35, wspace=0.30, left=0.08, right=0.95, top=0.93, bottom=0.06)

# (a) UMAP cell type — small dots, legend inside bottom-left
ax_a = fig.add_subplot(gs[0, 0])
sc.pl.umap(adata, color="cell_type", ax=ax_a, show=False, palette=ct_colors_all,
           frameon=True, linewidth=0.4, title="", size=3, alpha=0.7)
ax_a.tick_params(axis="both", which="both", length=0, labelbottom=False, labelleft=False)
ax_a.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=5.5, frameon=True, framealpha=0.9,
            edgecolor="none", markerscale=1.5, handletextpad=0.2, columnspacing=0.4, borderaxespad=0.)

# (b) UMAP sample — prove batch correction
ax_b = fig.add_subplot(gs[0, 1])
sc.pl.umap(adata, color="sample_id", ax=ax_b, show=False, size=3, alpha=0.7)

# (c) Dotplot — groupby cell_type (NOT leiden), remove unused categories first
ax_c = fig.add_subplot(gs[1, 0])
adata_dot = adata.copy()
adata_dot.obs["cell_type"] = adata_dot.obs["cell_type"].cat.remove_unused_categories()
sc.pl.dotplot(adata_dot, var_names=markers, groupby="cell_type", use_raw=True,
              show=False, color_map="RdBu_r", expression_cutoff=0.5, title="", ax=ax_c)

# (d) Cell type proportions — horizontal bar with percentages
ax_d = fig.add_subplot(gs[1, 1])
ct_counts = adata.obs["cell_type"].value_counts()
ct_pct = 100 * ct_counts / ct_counts.sum()
ax_d.barh(range(len(ct_pct)), ct_pct.values, color=[ct_colors[ct] for ct in ct_pct.index])
for i, pct in enumerate(ct_pct.values):
    ax_d.text(pct + 0.3, i, f"{pct:.1f}%", va="center", fontsize=5.5)

# Panel labels
for ax, label in [(ax_a,"a"),(ax_b,"b"),(ax_c,"c"),(ax_d,"d")]:
    ax.text(-0.08, 1.08, label, transform=ax.transAxes, fontsize=10, fontweight="bold")

fig.suptitle(f"Single-cell transcriptomic profiling of macaque {tissue}", fontsize=9, fontweight="bold")
fig.savefig("figure1_main.png", dpi=300, bbox_inches="tight")
```

**Key design rules**:
- UMAP: `size=3, alpha=0.7` (individual dots visible, not color blobs)
- UMAP: `tick_params(length=0, labelbottom=False, labelleft=False)` — clean axes
- Legend OUTSIDE UMAP (right side, `bbox_to_anchor=(1.02, 1.0)`) — user explicitly said "图例位置不是很合适,建议放在图外". NEVER put legend inside the plot.
- Dotplot groupby `cell_type` (not cluster numbers) — reader wants to see markers per cell type
- Dotplot: remove unused categories first (`cat.remove_unused_categories()`)
- Bar chart: horizontal, percentage labels, no0-cell types
- Panel labels: bold, outside top-left (a, b, c, d), fontsize=10
- Font: base7pt, axis labels8pt, panel labels10pt bold
- rcParams: set globally at script start, not per-figure

### Required plots
1. `fig_umap_celltype` — cell type UMAP with on-data labels, legend_fontsize=5, legend_fontoutline=1.5, frameon=True, no title
2. `fig_umap_sample` — sample UMAP (post-Harmony proof), right margin legend
3. `fig_marker_expression` — multi-panel marker UMAP grid (no ticks, no frame, no colorbar, bold gene names as titles)
4. `fig_dotplot_markers` — marker dotplot grouped by cell_type
5. `fig_dotplot_deg` — DEG dotplot (top3 per cluster)
6. `fig_composition` — cell type composition barplot per sample
7. `fig_summary_table` — QC stats table (cell type, n, %, med genes, med UMI, med MT%)
8. `fig_umap_confidence` — annotation confidence (green/orange/red)
9. QC violin before/after filtering

### Color palette (Okabe-Ito extended, sorted by cell type function)
```python
CB_PALETTE = [
    "#0072B2",  # Endothelial (blue)
    "#E69F00",  # Granulosa (orange)
    "#009E73",  # Macrophage (green)
    "#CC79A7",  # OSE (pink)
    "#56B4E9",  # Pericyte (light blue)
    "#D55E00",  # Smooth_muscle (vermillion)
    "#999999",  # Stromal (grey)
    "#882255",  # Theca (dark purple)
    "#44AA99",  # T_NK_cell (teal)
    "#332288",  # Proliferating (indigo)
    "#F0E442",  # Epithelial (yellow)
]
```

### Multi-format output
Save both PNG (300 DPI) and PDF (vector, fonttype=42 for editable text):
```python
matplotlib.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
})
```

### Marker expression UMAP grid
```python
fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 2, nrows * 1.8))
for i, gene in enumerate(key_markers):
    r, c = divmod(i, ncols)
    sc.pl.umap(adata, color=gene, ax=axes[r, c], show=False,
               title=gene, frameon=False, size=1, alpha=0.6,
               colorbar_loc=None, vmin=0)  # colorbar_loc=None NOT "none"
    axes[r, c].set_xticks([]); axes[r, c].set_yticks([])
    axes[r, c].title.set_fontsize(8); axes[r, c].title.set_fontweight("bold")
```

1. ✓ UMAP cell type with legend (right margin, fontoutline=2)
2. ✓ UMAP merged clusters (on data labels)
3. ✓ UMAP sample (post-Harmony, prove batch correction)
4. ✓ UMAP confidence (high/medium/low with distinct colors)
5. ✓ Marker dotplot by cell type
6. ✓ DEG dotplot (rank_genes_groups)
7. ✓ Individual marker UMAPs for rare cell types (DDX4, CD79A, HSD3B1)
8. ✓ Doublet check UMAPs (CD79A, STAR expression)
