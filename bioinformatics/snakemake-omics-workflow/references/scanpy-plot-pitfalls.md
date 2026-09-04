# Scanpy Plot Pitfalls for scRNA-seq Pipeline

## HVG Plot Belongs in Cluster, Not QC

`sc.pl.highly_variable_genes(adata)` requires `adata.uns["hvg"]` which is set by `sc.pp.highly_variable_genes()` in `mode_cluster`. Calling it in `plot_qc` causes `KeyError: 'hvg'` because HVG hasn't been computed yet at QC stage.

**Rule**: `plot_qc` handles counts/mt distributions and scatter plots. `plot_cluster` handles PCA variance ratio and HVG plots.

## Scatter Plot Colorbar Positioning

`sc.pl.scatter()` creates its own colorbar automatically, but positioning is unreliable. For proper control:

```python
fig, ax = plt.subplots(figsize=(8, 6))
sc.pl.scatter(adata, x_col, y_col, color=color_col, show=False, ax=ax)

# Remove scanpy's auto-colorbar, create properly positioned one
if ax.collections:
    old_cbar = ax.collections[0].colorbar
    if old_cbar is not None:
        old_cbar.remove()
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cbar = fig.colorbar(ax.collections[0], cax=cax)
    cbar.set_label("label text")
```

## Side-by-Side Scatter Comparison

For before/after QC comparison, use unified axis limits:

```python
# Compute global limits from both datasets
all_x = np.concatenate([before.obs[x_col].values, after.obs[x_col].values])
all_y = np.concatenate([before.obs[y_col].values, after.obs[y_col].values])
all_c = np.concatenate([before.obs[color_col].values, after.obs[color_col].values])
x_lim = (all_x.min() * 0.95, all_x.max() * 1.05)
y_lim = (all_y.min() * 0.95, all_y.max() * 1.05)
c_min, c_max = float(all_c.min()), float(all_c.max())

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
for ax, src, title in [(ax1, before, "Before"), (ax2, after, "After")]:
    sc.pl.scatter(src, x_col, y_col, color=color_col, show=False, ax=ax)
    ax.set_title(title)
    ax.set_xlim(x_lim)
    ax.set_ylim(y_lim)
    if ax.collections:
        ax.collections[0].set_clim(c_min, c_max)
        # remove old colorbar, create new one on ax2 only
```

## Explicit Plot Function Parameters

All plot functions should receive explicit parameters, not pull from adata internals. This makes dependencies visible to callers:

```python
# BAD — hidden dependencies
def plot_cluster(self, adata):
    sc.pl.umap(adata, color="leiden")  # hardcoded "leiden"

# GOOD — explicit parameters
def plot_cluster(self, adata, cluster_key="leiden", sample_key="sample"):
    sc.pl.umap(adata, color=cluster_key)
```

This applies to: column names for scatter axes, cluster/sample keys, annotation columns, pseudotime column names, batch keys.

## batch_key Must Match mode_merge Column

`mode_merge` creates `obj.obs["sample_id"]`, not `obj.obs["sample"]`. Any downstream function using a batch key (e.g., `sc.pp.highly_variable_genes(batch_key=...)`) must use `"sample_id"`. Using `"sample"` causes `KeyError`.

**Rule**: Don't use fallback logic (`"sample_id" if ... else "sample"`). Use the correct value directly. If it's wrong, the error message from scanpy will be clear.
