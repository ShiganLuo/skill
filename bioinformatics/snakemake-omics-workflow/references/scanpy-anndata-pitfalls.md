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
sc.pp.highly_variable_genes(adata, ..., subset=True)  # HVG BEFORE scale
sc.pp.scale(adata, max_value=10)          # scale HVGs only
sc.tl.pca(adata)                          # PCA on HVGs
```

**Why**: HVG detection should be on log-normalized data, not scaled data.
Scaling all genes is wasteful. `adata.raw` preserves all genes for
downstream DEG (`use_raw=True`).

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
    sc.external.pp.harmony_integrate(adata, key=batch_key)
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
```

Do NOT call `sc.pp.neighbors()` before BBKNN — it's wasted.

## UMAP and Leiden Params for Tight Clusters

User preference for clean, separated clusters:
```python
sc.tl.umap(adata, min_dist=0.1, spread=0.8)
sc.tl.leiden(adata, resolution=resolution, key_added="leiden",
             flavor="igraph", n_iterations=2, directed=False)
```

Default UMAP params produce more spread-out clusters.

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
3. neighbors → UMAP → Leiden → DEG

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
