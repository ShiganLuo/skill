# HVG Selection Comparison — Macaque Ovary (19,144 cells)

## Test Setup
- **Data**: Macaque ovary, 2 samples (luanchao-11238, luanchao-21310), Cell Ranger quantification
- **Batch correction**: Harmony (theta=3, lamb=0.5, nclust=50)
- **UMAP**: min_dist=0.01, spread=0.8, n_neighbors=100
- **Clustering**: Leiden resolution=0.5, igraph flavour

## Results (8 combinations tested)

| HVG Count | Flavor      | Clusters | Visual Quality | Boundary Cells |
|-----------|-------------|----------|----------------|----------------|
| 2000      | cell_ranger | 14       | **BEST** — compact, separated, minimal scatter | ~6% |
| 3000      | cell_ranger | 15       | Good — more small clusters | ~7% |
| 5000      | cell_ranger | 15       | Compact but more noise | ~7% |
| 1000      | cell_ranger | 17       | Too few genes, loses signal | ~8% |
| 2000      | seurat      | 16       | Scattered points, overlap | ~8% |
| 3000      | seurat      | 14       | Scattered points, overlap | ~7% |
| 5000      | seurat      | 15       | Highly scattered | ~9% |
| 1000      | seurat      | 14       | Poor separation | ~8% |

## Key Finding
**`cell_ranger` flavor consistently outperforms `seurat` flavor** for macaque ovary data. The same `n_top_genes` with `cell_ranger` produces tighter, better-separated clusters.

## Why cell_ranger works better
- `cell_ranger` uses a different dispersion-based gene selection that captures more biologically relevant variance
- `seurat` tends to select genes with high mean expression, which may include housekeeping genes that don't distinguish cell types
- For tissues with subtle transcriptional differences (e.g., ovarian cell subtypes), `cell_ranger`'s gene selection is more discriminative

## Recommendation
For macaque/reproductive tissues: `flavor="cell_ranger", n_top_genes=2000` as starting point.
