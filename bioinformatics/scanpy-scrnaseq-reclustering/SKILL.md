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

## Trigger phrases
- "重新聚类" / "re-cluster" / "redo clustering"
- "注释效果不好" / "annotation not good"
- "细胞群颜色不纯净" / "impure clusters"
- "批次效应" / "batch effect"

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

### 5. Marker-based Annotation
```python
# Score each cell type
for ct, genes in marker_dict.items():
    sc.tl.score_genes(adata, gene_list=genes, score_name=f"score_{ct}")

# Per-cluster majority voting with confidence
score_cols = [c for c in adata.obs.columns if c.startswith("score_")]
scores_df = adata.obs[score_cols].copy()
scores_df.columns = [c.replace("score_", "") for c in scores_df.columns]

cluster_anno = {}
for cluster in adata.obs["leiden"].cat.categories:
    mask = adata.obs["leiden"] == cluster
    cluster_scores = scores_df[mask].mean()
    best_ct = cluster_scores.idxmax()
    best_score = cluster_scores.max()
    second_best = cluster_scores.nlargest(2).iloc[1] if len(cluster_scores) >= 2 else 0.0
    confidence = "high" if best_score > 0.1 and (best_score - second_best) > 0.05 else "medium" if best_score > 0.05 else "low"
    cluster_anno[cluster] = {"cell_type": best_ct, "score": float(best_score), "confidence": confidence}

adata.obs["cell_type"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["cell_type"]).astype("category")
adata.obs["annotation_confidence"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["confidence"]).astype("category")
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

### Pitfall 17: Redundant mode functions
**Symptom**: Duplicate preprocessing code in multiple modes
**Cause**: Separate batch and cluster modes both doing normalize/HVG/scale/PCA
**Fix**: Consolidate related operations into one mode. Batch correction is part of clustering, not a separate step. The cluster mode should handle: preprocess → batch correct → cluster

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
**Symptom**: Same cell type split into disconnected UMAP islands; B1 closer to A than to B2
**Cause**: Over-clustering (resolution too high) splits biologically continuous populations
**Diagnostic**: Compare max distance between same-type clusters vs min distance to different types
**Fix**: (1) Lower resolution to 0.6, (2) Merge clusters post-annotation using connected components (see Step 7)
**User signal**: "细胞群颜色不纯净", "同类cluster分散", "B1靠近A而不是B2"

### Pitfall 8: Shared markers cause cell type proximity
**Symptom**: Pericyte and Smooth_muscle too close in UMAP; Stromal and Theca overlapping
**Cause**: Biologically related cell types share markers (e.g., ACTA2/TAGLN in both Pericyte and Smooth_muscle; DCN/VIM/PDGFRA in both Stromal and Theca)
**Diagnostic**: Check marker expression overlap between close cell types (>50% shared = expect proximity)
**Expected**: Central UMAP region (Stromal/Smooth_muscle/Pericyte/OSE) forms a continuum — this is biology, not a bug
**Fix**: Use more specific markers, or accept biological continuity and explain in paper

## Parameter Guidelines

| Parameter | Loose (default) | Tight separation | Over-clustered |
|-----------|----------------|------------------|----------------|
| n_top_genes | 2000 | 2000 | >3000 |
| n_neighbors | 30 | 50 | 15 |
| min_dist | 0.3 | 0.1 | 0.1 |
| resolution | 0.3-0.5 | 0.6-0.8 | >1.0 |

**Validated macaque ovary config**: `n_top_genes=2000, n_neighbors=50, min_dist=0.1, spread=0.8, resolution=0.6` produced 18 clusters with good separation. After cluster merging: 9 contiguous cell type groups.

For Nature-quality: always use Harmony/BBKNN batch correction when >1 sample.

**Tight separation mode**: Use `min_dist=0.1, spread=0.8, n_neighbors=50, resolution=0.8-1.0` when user complains about mixed/impure clusters. This produces more compact UMAP islands but may not fully separate biologically related cell types (Stromal/Smooth_muscle/Pericyte/OSE share markers).

**Expected biological continuity**: Central UMAP regions connecting Stromal, Smooth_muscle, Pericyte, OSE, and Proliferating are biologically realistic — these mesenchymal/epithelial cell types share大量基因表达, forming a continuum in expression space. UMAP reflects this. Clean separation of these types requires unique markers, not just parameter tuning.

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
- Theca: CYP17A1, IGF1, STAR, CYP11A1
- Stromal: COL1A1, COL3A1, DCN, LUM, VIM, PDGFRA
- Smooth_muscle: ACTA2, MYH11, TAGLN, CNN1, DES
- Endothelial: PECAM1, VWF, CDH5, KDR, EMCN
- Macrophage: CD68, CD163, CD74, CSF1R, C1QA
- T_NK_cell: CD3E, CD3D, CD8A, NKG7, GZMB
- B_cell: CD79A, CD79B, MS4A1, PAX5
- OSE: KRT18, EPCAM, WT1, LGR5, UPK3B
- Pericyte: RGS5, PDGFRB, NOTCH3, ABCC9
- Luteal: HSD3B1, PRLR, LHCGR, STAR
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
