# Scanpy Plot Function ax Parameter Reference

## Functions that DO NOT accept `ax`

These raise `TypeError: got an unexpected keyword argument 'ax'` if you pass `ax`:

| Function | Workaround |
|----------|-----------|
| `sc.pl.highly_variable_genes(adata, show=False)` | Call without ax, then `_save()` |
| `sc.pl.pca_variance_ratio(adata, show=False)` | Call without ax, then `_save()` |
| `sc.pl.rank_genes_groups_dotplot(adata, n_genes=N, show=False)` | Call without ax, then `_save()` |

Pattern:
```python
# WRONG — TypeError
fig, ax = plt.subplots()
sc.pl.highly_variable_genes(adata, show=False, ax=ax)

# CORRECT
sc.pl.highly_variable_genes(adata, show=False)
self._save("qc_highly_variable_genes.png")  # plt.savefig + plt.close("all")
```

## Functions that DO accept `ax`

| Function | Notes |
|----------|-------|
| `sc.pl.umap(adata, color=..., show=False, ax=ax)` | Standard UMAP |
| `sc.pl.violin(adata, key, show=False, ax=ax)` | Single violin |
| `sc.pl.scatter(adata, x, y, color=..., show=False, ax=ax)` | Scatter |
| `sc.pl.diffmap(adata, color=..., show=False, ax=ax)` | Diffusion map |
| `sc.pl.dotplot(adata, var_names=..., show=False, ax=ax)` | Dotplot |
| `sc.pl.rank_genes_groups(adata, n_genes=N, show=False)` | Actually uses its own figure layout |
| `sc.pl.rank_genes_groups_matrixplot(adata, show=False)` | Own layout |
| `sc.pl.rank_genes_groups_stacked_violin(adata, show=False)` | Own layout |
| `sc.pl.rank_genes_groups_heatmap(adata, show=False)` | Own layout |

## Deprecation: sc.settings.set_figure_params

In scanpy >= 1.10:
```python
# DEPRECATED
sc.settings.set_figure_params(dpi=80, facecolor="white", frameon=False)

# CURRENT
sc.set_figure_params(dpi=80, facecolor="white", frameon=False)
```

Always use `sc.set_figure_params()` (top-level function), not `sc.settings.set_figure_params()`.
