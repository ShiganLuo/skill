# anndata `layers[None]` — By Design, Not a Bug

## The Phenomenon

In anndata 0.13.x, `adata.layers` always contains a `None` key (Python `None`, not the string `"None"`). `adata.layers[None]` is an alias for `adata.X` — they point to the same object.

```python
import anndata as ad
a = ad.AnnData(X=some_matrix)
None in a.layers  # True
a.layers[None] is a.X  # True
```

This is **by design** in anndata 0.13.x, not a bug from reading/writing HDF5.

## Why It Appears in h5ad Files

When an AnnData with no explicit layers is written to h5ad:
1. Writer detects `None in layers` → writes `X` separately, filters out `None` key
2. HDF5 file has an empty `layers` group (keys=`[]`, attrs=`encoding-type: dict`)
3. On read, `read_mapping` returns `{}` for the empty group
4. `AnnData.__init__` with `layers={}` internally creates `layers[None]` as alias for `X`

## Critical: NEVER Delete `None` from Layers

```python
# WRONG — destroys .X!
if None in adata.layers:
    del adata.layers[None]  # adata.X is now None!
```

Deleting `layers[None]` removes the only reference to the underlying `.X` data. After deletion, `adata.X` becomes `None`.

## Safe Handling

- **Ignore it**: downstream code using `adata.X` or `adata.layers["counts"]` is unaffected
- **When building layer lists**: filter with `[k for k in adata.layers if k is not None]`
- **When writing**: anndata's writer already handles `None` correctly (writes X, filters None key)
- **Version note**: this behavior is specific to anndata 0.13.x. Upgrading to 0.14+ (when available) may change this

## scTE Context

scTE outputs h5ad files with an empty `layers` group. After `mode_qc` adds `adata.layers["counts"]`, the file has two layers: `None` (alias for X) and `counts`. This is correct and harmless.

## Pandas BooleanArray + Scipy Sparse

`pd.Series.str.contains()` returns a nullable `BooleanArray` (not numpy bool). Scipy sparse matrix indexing requires numpy bool arrays with `.nonzero()`. Always wrap with `np.array()`:

```python
# WRONG
adata.var["hb"] = adata.var_names.str.contains(r"^HB[^(P)]")  # BooleanArray

# CORRECT
adata.var["hb"] = np.array(adata.var_names.str.contains(r"^HB[^(P)]"))
```

This applies to `str.contains()`, `str.startswith()`, and `str.endswith()` when the result will be used for scipy sparse indexing or boolean masking on sparse matrices.
