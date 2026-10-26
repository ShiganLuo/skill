# harmonypy >= 0.1.0 Breaking Change: Z_corr Shape

## Problem

`sc.external.pp.harmony_integrate()` from scanpy does `adata.obsm[adjusted_basis] = harmony_out.Z_corr.T`.
But harmonypy >= 0.1.0 changed `Z_corr` from `(n_components, n_cells)` to `(n_cells, n_components)`.
The `.T` now produces wrong shape `(n_components,)` — a 1D array.

```
ValueError: Value passed for key 'X_pca_harmony' is of incorrect shape.
Values of obsm must match dimensions ('obs',) of parent.
Value had shape (50,) while it should have had (17255,).
```

GitHub issue: scverse/scanpy#3940 (fixed in scanpy >= 1.10.2 via PR #3953)

## Fix: Use harmonypy directly

```python
import harmonypy as hm
import numpy as np

# Instead of: sc.external.pp.harmony_integrate(adata, key=batch_key)
ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key, random_state=0)
Z = np.asarray(ho.Z_corr)
if Z.ndim == 1:
    raise ValueError(f"harmonypy Z_corr is 1D shape={Z.shape}, expected 2D")
# Ensure (n_cells, n_components) orientation
if Z.shape[0] != adata.n_obs:
    Z = Z.T
adata.obsm["X_pca_harmony"] = Z
sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, use_rep="X_pca_harmony")
```

## When this hits

- Container/venv has harmonypy >= 0.1.0 but scanpy < 1.10.2
- Common in Apptainer/SIF containers where packages were installed at different times

## anndata nullable strings write fix

Newer anndata requires explicit opt-in for writing nullable string arrays:

```python
import anndata as ad
ad.settings.allow_write_nullable_strings = True  # MUST be before any write_h5ad
```

Without this:
```
RuntimeError: `anndata.settings.allow_write_nullable_strings` is None and
`pd.options.future.infer_string` is False.
```
