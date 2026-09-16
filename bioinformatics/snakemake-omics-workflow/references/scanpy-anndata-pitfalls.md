# Scanpy & anndata Pitfalls for Omics Workflow

## anndata `layers[None]` IS `adata.X` by Design

In anndata 0.13.x, when you create `AnnData(X=some_matrix)`, the constructor
automatically stores `layers[None]` as an alias for `.X`:

```python
a = ad.AnnData(X=matrix)
None in a.layers  # True
a.layers[None] is a.X  # True
```

**NEVER delete `layers[None]`** — it destroys `.X`:
```python
del a.layers[None]  # a.X becomes None!
```

This is NOT a bug in how h5ad files are read. It's the design of anndata 0.13.x.
Even files with an empty `layers` group in HDF5 will show `[None]` after reading.

The write path in anndata already handles this correctly: if `None in layers`,
it writes `.X` separately and filters out the `None` key. So h5ad files never
actually store the `None` key on disk.

**Impact on pipeline**: The `None` key propagates through QC → merge → cluster.
It's harmless — downstream code uses `adata.layers["counts"]` or `adata.X`.
Don't try to "fix" it.

## `sc.pp.highly_variable_genes` batch_key Must Match Merge Column

`mode_merge` creates `adata.obs["sample_id"]`. But `mode_cluster` had
`batch_key='sample'` hardcoded → `KeyError: 'sample'`.

**Rule**: The `batch_key` in `sc.pp.highly_variable_genes()` must match the
column name created by the merge step. In this project it's `"sample_id"`.

## BooleanArray vs numpy bool for var columns

`pd.Series.str.contains()` returns a pandas `BooleanArray` (nullable boolean),
NOT a numpy bool array. scipy sparse matrix indexing requires numpy bool arrays
(with `.nonzero()` method). Always wrap with `np.array()`:

```python
# WRONG — returns BooleanArray
adata.var["hb"] = adata.var_names.str.contains(r"^HB[^(P)]")

# CORRECT — wrap with np.array()
adata.var["hb"] = np.array(adata.var_names.str.contains(r"^HB[^(P)]"))
```

`adata.var["mt"]` and `adata.var["ribo"]` already use `np.array()` wrapping.
`adata.var["hb"]` was missed — this caused `AttributeError: 'BooleanArray'
object has no attribute 'nonzero'` in `sc.pp.calculate_qc_metrics`.

## scTE Data Has Very Low Mitochondrial %

scTE quantifies transposable elements, not the full transcriptome. MT genes
are barely represented. After QC, `pct_counts_mt` max is typically <0.3%.
This is expected — not a QC bug.

## plot_qc: HVG Plot Belongs in plot_cluster, Not plot_qc

`sc.pl.highly_variable_genes(adata)` requires `adata.uns["hvg"]` which is set
by `sc.pp.highly_variable_genes()` in `mode_cluster`. Calling it in `plot_qc`
(before clustering) causes `KeyError: 'hvg'`.

## Explicit Parameters Pattern for Plot Functions

All plot functions should receive explicit parameters, not pull from adata
internals. This makes dependencies visible to callers:

```python
# WRONG — hidden dependencies
def plot_cluster(self, adata):
    sc.pl.umap(adata, "leiden")  # what if column is named differently?

# CORRECT — explicit
def plot_cluster(self, adata, cluster_key="leiden", sample_key="sample"):
    sc.pl.umap(adata, cluster_key)
```

The caller passes the values explicitly:
```python
plotter.plot_cluster(adata, cluster_key="leiden", sample_key="sample")
```

## Correct Gene Processing Order in mode_cluster

**WRONG** (what was there before):
```python
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.scale(adata, max_value=10)          # scales ALL genes
sc.pp.highly_variable_genes(adata, ...)   # HVG after scale
sc.tl.pca(adata, use_highly_variable=True)
```

**CORRECT**:
```python
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.raw = adata.copy()                  # save full-gene snapshot
sc.pp.highly_variable_genes(adata, ..., subset=False)  # HVG detect (no subset)
plotter.plot_hvg(adata, n_top_genes=3000)  # plot BEFORE subsetting
adata = adata[:, adata.var["highly_variable"]].copy()  # manual subset
sc.pp.scale(adata, max_value=10)          # scale HVGs only
sc.tl.pca(adata)                          # PCA on HVGs
```

**Why**: HVG detection should be on log-normalized data, not scaled data.
Scaling all genes is wasteful. `adata.raw` preserves all genes for
downstream DEG (`use_raw=True`).

**Critical**: Use `subset=False` in `highly_variable_genes`, then plot HVG
(all genes needed as background), THEN manually subset. If you use
`subset=True` first, non-HVG genes are gone and the HVG plot can only
show HVGs — no background of all genes, no proper scatter.

## adata.raw for Full Gene Coverage After HVG Subset

When `subset=True` in `highly_variable_genes`, non-HVG genes are physically
removed from `adata.X`. To access full gene info later:

```python
# Before HVG
adata.raw = adata.copy()

# After clustering, DEG uses full gene set
sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon", use_raw=True)
```

`adata.raw` is read-only. For mutable access, use layers:
```python
adata.layers["normalized"] = adata.X.copy()
```

## BBKNN vs Harmony: neighbors Call Handling

Batch correction is integrated into `mode_cluster`. BBKNN builds its own
graph; Harmony needs explicit `neighbors` call after integration:

```python
if batch_method == "bbknn":
    sc.external.pp.bbknn(adata, batch_key=batch_key)
elif batch_method == "harmony":
    # Direct harmonypy call to avoid scanpy wrapper .T bug
    ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key)
    Z = np.asarray(ho.Z_corr)
    if Z.ndim == 1:
        raise ValueError(f"harmonypy Z_corr is 1D shape={Z.shape}, expected 2D")
    if Z.shape[0] != adata.n_obs:
        Z = Z.T
    adata.obsm["X_pca_harmony"] = Z
```

**CRITICAL PITFALL**: After Harmony, `sc.pp.neighbors` MUST use
`use_rep="X_pca_harmony"`. Without this, it defaults to `X_pca`
(uncorrected), and batch correction is silently ignored for all
downstream analysis (UMAP, Leiden, DEG).

```python
# WRONG — uses uncorrected PCA, Harmony correction wasted
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)

# CORRECT — uses batch-corrected PCA
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs,
                use_rep="X_pca_harmony")
```

Do NOT call `sc.pp.neighbors()` before BBKNN — it's wasted.

## n_pcs vs n_neighbors: Independent Parameters

These control different aspects of the neighbor graph:

- **n_pcs**: Number of principal components for distance computation.
  Determines the dimensionality of the space. More PCs = more signal
  but also more noise. Use auto-detection (sliding window plateau) or
  default 50.

- **n_neighbors**: Number of nearest neighbors for k-NN graph.
  Determines graph connectivity. Higher = smoother, more global structure,
  fewer holes in UMAP. Lower = more local detail, more fragmentation.

They do NOT need to be the same. Typical values:
- n_pcs: 10-50 (auto-detected or manual)
- n_neighbors: 15-50 (15 is default, 50 for noisy data)

## UMAP and Leiden Params for Tight Clusters

User preference for compact, separated clusters with minimal holes:
```python
sc.tl.umap(adata, min_dist=0.05, spread=0.5)
sc.tl.leiden(adata, resolution=resolution, key_added="leiden",
             flavor="igraph", n_iterations=2, directed=False)
```

- `min_dist=0.05`: Points packed tighter (0.1 is default, 0.01-0.05 for compact)
- `spread=0.5`: Cluster more concentrated (0.8 is default, 0.5 reduces holes)

If clusters still have holes, increase `n_neighbors` (e.g., 30-50).

## Auto-detecting n_pcs: Sliding Window Plateau

Use a sliding window on the variance ratio curve to find where it flattens:

```python
def detect_n_pcs(variance_ratio, min_pcs=10, max_pcs=100,
                 window=5, ratio=0.15):
    delta = np.abs(np.diff(variance_ratio))
    # Baseline from first min_pcs PCs (active decline region)
    baseline_end = min(min_pcs, len(delta))
    baseline = np.median(delta[:baseline_end])
    if baseline == 0:
        return min(max_pcs, len(variance_ratio))
    threshold = baseline * ratio
    search_start = max(0, min_pcs - 1)
    for i in range(search_start, len(delta) - window + 1):
        if np.mean(delta[i:i + window]) < threshold:
            return max(min_pcs, min(i + 1, max_pcs, len(variance_ratio)))
    return min(max_pcs, len(variance_ratio))
```

**Why baseline from first min_pcs, not all PCs**: The first min_pcs PCs
represent the "active decline" region. Using all PCs would include the
flat tail, making baseline too small and threshold too strict.

## HVG Selection: Use scanpy's Internal Logic

**NEVER reimplement HVG selection** with custom algorithms (Mahalanobis
distance, 2D outlier detection, etc.). `sc.pp.highly_variable_genes()`
already handles gene ranking internally via normalized dispersions.

```python
# CORRECT — let scanpy handle selection
sc.pp.highly_variable_genes(adata, n_top_genes=3000, flavor="seurat",
                            subset=False, batch_key="sample_id")

# WRONG — don't re-rank or re-select genes after scanpy
sorted_idx = adata.var["dispersions_norm"].sort_values(ascending=False).index
adata.var["highly_variable"] = False
adata.var.loc[sorted_idx[:n], "highly_variable"] = True
```

Default n_top_genes=3000 works well for most datasets. Don't try to
auto-detect this value — the distribution of mean expression vs normalized
dispersion doesn't have a reliable automatic cutoff.

## HVG Plot: Two-Panel with All Genes as Background

The HVG plot must show ALL genes as background (grey) with HVGs highlighted
(blue). This requires calling `plot_hvg` BEFORE subsetting:

```python
sc.pp.highly_variable_genes(adata, ..., subset=False)  # detect only
plotter.plot_hvg(adata, n_top_genes=3000)               # plot with all genes
adata = adata[:, adata.var["highly_variable"]].copy()   # then subset
```

The HVG plot has two subplots:
- **Left**: mean expression vs normalized dispersion scatter
  (grey=non-HVG, blue=HVG). Title shows count: "Highly Variable Genes
  (3000 / 20000)". Red dashed horizontal line at dispersion cutoff.
- **Right**: sorted normalized dispersion elbow curve with vertical
  red line at selected gene count.

Key data sources from `adata.var`:
- `means` — mean expression per gene
- `dispersions_norm` — normalized dispersion per gene
- `highly_variable` — boolean mask

## PCA Variance Ratio Plot: Single or Two-Panel

When `auto_n_pcs=False`: single scree plot with PC labels on each scatter
point, red dashed vertical line at selected n_pcs.

When `auto_n_pcs=True`: two subplots:
- **Left**: scree plot (same as above) with auto-detected elbow marked.
- **Right**: per-PC delta curve (`|variance_ratio[i+1] - variance_ratio[i]|`)
  with red dashed threshold line and red dot at the elbow PC.

The `detect_n_pcs` function should return a diagnostics dict for plotting:
```python
def detect_n_pcs(variance_ratio, min_pcs=10, max_pcs=100, window=5, ratio=0.15):
    # Returns: (recommended_n_pcs, {"delta": ..., "threshold": ..., "elbow_pc": ...})
```

The diagnostics dict is passed to `plot_pca_variance` which decides
single vs two-panel based on `auto_n_pcs` flag and dict contents.

## Plot Method Separation: plot_hvg / plot_pca_variance / plot_cluster

Each major visualization step gets its own method, called at the right
point in the pipeline:

```
HVG detect (subset=False) → plotter.plot_hvg() → manual subset → scale → PCA
→ plotter.plot_pca_variance() → batch correct → neighbors → UMAP → Leiden
→ plotter.plot_cluster() (UMAP only)
```

`plot_cluster` should ONLY do UMAP plots. HVG and PCA variance are
separate methods called earlier in the pipeline when the data is in
the right state (e.g., all genes available for HVG background).

## Hard Filters vs MAD-Based Outlier Detection

MAD-based outlier detection is good for automatic thresholds, but hard
filters should complement it. Use `use_mad=False` (default) for strict
filtering, `use_mad=True` for more permissive filtering.

```python
# Hard filters only (default, more strict)
mode_qc(adata, output, min_genes=200, max_genes=6000, max_pct_mt=20, use_mad=False)

# MAD + hard filters (more permissive)
mode_qc(adata, output, min_genes=200, max_genes=6000, max_pct_mt=20, use_mad=True)
```

**When use_mad=False** (default):
```python
# Hard filters only
adata = adata[(adata.obs["n_genes_by_counts"] >= min_genes) &
              (adata.obs["n_genes_by_counts"] <= max_genes) &
              (adata.obs["pct_counts_mt"] <= max_pct_mt)].copy()
```

**When use_mad=True** (more permissive):
```python
# MAD first (on full data)
adata.obs["outlier"] = is_outlier(adata, "log1p_total_counts", 5) | ...
adata = adata[~adata.obs["outlier"]].copy()

# Then hard filters
adata = adata[(adata.obs["n_genes_by_counts"] >= min_genes) & ...].copy()
```

**MAD first → hard filter**: MAD is calculated on full data (includes extremes), so threshold is looser. More cells pass.
**Hard filter only**: Strict absolute thresholds. More predictable.

The `max_pct_mt` parameter replaces the old hardcoded 8% threshold.

## batch_key Consistency Between Snakemake and Python

Snakemake rule defaults and Python function defaults must match:
- Snakemake: `batch_key=lambda w: params.get(...).get("batch_key", "sample_id")`
- Python: `batch_key = batch_key or ("sample_id" if "sample_id" in adata.obs else "batch")`

Mismatch causes KeyError at runtime.

## Pipeline Architecture: merge → batch → cluster

The correct pipeline order for multi-sample scRNA-seq:

```
qc → merge → cluster (with batch correction) → annotate → advanced → de
```

**NOT** `qc → merge → cluster → batch` — that clusters on uncorrected data.

Batch correction is integrated into `mode_cluster` via parameters:
- `batch_method`: "harmony" (default), "bbknn", or "" (skip)
- `batch_key`: column in obs identifying batches (default: "sample_id")

```python
mode_cluster(adata, output, batch_method="harmony", batch_key="sample_id", ...)
```

The flow inside mode_cluster:
1. normalize → log1p → adata.raw → HVG → scale → PCA
2. batch correction (BBKNN or Harmony)
3. neighbors (use_rep="X_pca_harmony" for Harmony) → UMAP → Leiden → DEG

**Why batch before cluster**: Clustering on uncorrected data merges batch effects into clusters. Batch correction first ensures biological variation drives clustering.

## QC Strategy: Hard Filters First, MAD Optional

Default: hard filters only (more strict, predictable).
Optional: MAD-based outlier detection (more permissive, adaptive).

```python
mode_qc(adata, output, min_genes=200, max_genes=6000, max_pct_mt=20, use_mad=False, ...)
```

**Order when use_mad=True**: MAD first → hard filter second (more permissive).
**Order when use_mad=False**: hard filter only (default, more strict).

Hard filters are absolute thresholds; MAD adapts to data distribution. The `max_pct_mt` parameter replaces the old hardcoded 8% threshold.

## User Preferences

- **No fallbacks**: If a column doesn't exist, let it fail. Don't do
  `key if key in adata.obs.columns else "fallback"` — that silently hides
  problems. Direct values, explicit errors.
- **Only change what's asked**: Don't refactor unrelated code when fixing a bug.
- **Side-by-side comparison plots**: When comparing before/after, combine into
  a single figure with `plt.subplots(1, 2)` and unified axis ranges.
- **Don't modify build infrastructure** (EnvUtil.py) just to fix a container
  build error — the original template works. Only change the YAML and rebuild.
- **Don't reimplement what tools already do**: If scanpy handles gene selection
  internally, don't add custom selection logic on top. Understand what the tool
  does before adding layers.
