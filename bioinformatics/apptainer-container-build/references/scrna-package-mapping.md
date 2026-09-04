# scRNA-seq Package Name Mapping (R ↔ Python)

When adding scRNA-seq packages to conda YAML, many tools have different names across R and Python ecosystems. Use the Python name in the YAML.

## R → Python equivalents

| R package | Python package | Install channel |
|-----------|---------------|-----------------|
| DoubletFinder | doubletdetection | pip |
| magic (R magic) | magic-impute | pip |
| Seurat | scanpy | conda-forge |
| Harmony (harmony) | harmonypy | conda-forge |

## conda-forge vs PyPI-only

conda-forge available (put in `dependencies:`):
- louvain, leidenalg, igraph (python-igraph)
- bbknn, harmonypy, scvi-tools, cellrank
- scanpy, anndata, scrublet, scvelo, liana, celltypist

PyPI-only (put under `pip:`):
- adjustText, doubletdetection, magic-impute, palantir, infercnvpy

## Pitfalls

- `doubletfinder` does not exist on PyPI — use `doubletdetection`
- `magic` is a different package on PyPI — use `magic-impute`
- `harmony` on PyPI is `harmonypy` (conda-forge also has `harmonypy`)
- `louvain` is a separate package from `leidenalg` — both needed for scanpy's `tl.louvain` and `tl.leiden`
