# Scanpy + Harmony Pitfalls in the Omics Pipeline

## harmonypy >= 0.1.0 breaks `sc.external.pp.harmony_integrate()`

**Symptom**: `ValueError: Value passed for key 'X_pca_harmony' is of incorrect shape. Values of obsm must match dimensions ('obs',) of parent. Value had shape (50,) while it should have had (17255,).`

**Root cause**: harmonypy >= 0.1.0 changed `Z_corr` from `(n_components, n_cells)` to `(n_cells, n_components)`. The scanpy wrapper still does `.T`, breaking the shape. Tracked as [scanpy#3940](https://github.com/scverse/scanpy/issues/3940), fixed in scanpy PR #3953 — but the fix may not be in the SIF container.

**Fix**: Replace `sc.external.pp.harmony_integrate(adata, key=batch_key)` with direct harmonypy call:

```python
import harmonypy as hm
import numpy as np

ho = hm.run_harmony(adata.obsm["X_pca"], adata.obs, batch_key, random_state=0)
Z = np.asarray(ho.Z_corr)
if Z.ndim == 1:
    raise ValueError(f"harmonypy Z_corr is 1D shape={Z.shape}, expected 2D")
# Ensure (n_cells, n_components) orientation
if Z.shape[0] != adata.n_obs:
    Z = Z.T
adata.obsm["X_pca_harmony"] = Z
```

Applied in: `modules/scanpy/bin/scRNAseq.py` mode_cluster (line ~352).

## anndata nullable strings write error

**Symptom**: `RuntimeError: anndata.settings.allow_write_nullable_strings is None and pd.options.future.infer_string is False`

**Fix**: Add at top of script before any h5ad write:
```python
import anndata as ad
ad.settings.allow_write_nullable_strings = True
```

## Clustering parameters for clean UMAP

User preference (validated empirically on macaque scRNA-seq):
- `n_neighbors=50` (not default 15) — captures global structure, reduces central mixing
- `min_dist=0.1, spread=0.8` — tight compact clusters
- `resolution=0.8` — good balance for 10k-50k cells
- `n_pcs=50`

Default `n_neighbors=15` produces fragmented local structure with overlapping clusters in UMAP central region.

## Standalone scripts: output directory, not source repo

Analysis scripts for specific datasets (clustering, annotation, plotting) go in `output/<project>/`, NOT in `workflow/Omics/modules/`. The source repo should only contain reusable pipeline code. Per-dataset scripts pollute git and risk accidental commits.
