# scRNA-seq PPT Report Structure

Standard slide order for single-cell RNA-seq analysis reports (Nature-quality).

## Design Reference

- Template script: `workflow/Omics/modules/RNAseq_report/bin/generate_report.py`
- Style: navy header bar (#182543), light gray bg (#F6F8FB), accent blue tables (#0094D8)
- See `python-scientific-plotting-scripts` skill §12 for full design constants

## Slide Order (15 slides)

| # | Title | Content |
|---|-------|---------|
| 1 | Title | Navy bg, centered white title, subtitle, date, accent band |
| 2 | Workflow | Colored ROUNDED_RECTANGLE boxes + CHEVRON arrows, bullet list of params |
| 3 | Sample Overview | Table (sample/tissue/cells CR/scTE) + cell count bar chart |
| 4 | QC Metrics | Table (pipeline/total cells/median genes/median counts/MT%) |
| 5 | UMAP Cell Ranger | UMAP colored by cell_type + cell type count sidebar |
| 6 | UMAP scTE | Same as above for scTE pipeline |
| 7 | Cell Type Composition | Grouped bar chart: CR vs scTE side by side |
| 8 | Marker Dotplot CR | Dotplot from rank_genes_groups (top 3 per cell type) |
| 9 | Marker Dotplot scTE | Same for scTE |
| 10 | Batch Correction | Sample-colored UMAP showing mixing |
| 11 | Rare Cell Types | Highlighted on UMAP + bullet list of markers |
| 12 | Doublet Validation | Doublet score heatmap + predicted doublets UMAP |
| 13 | Annotation Confidence | Pie chart (high/medium/low) |
| 14 | Conclusions | Navy bg, bullet points, stat cards (cells/types/clusters/samples) |
| 15 | Thank You | Navy bg, centered text, accent band |

## Key Data Points to Extract

From annotated h5ad:
- `adata.obs["cell_type"].value_counts()` — cell type distribution
- `adata.obs["sample_id"].value_counts()` — cells per sample
- `adata.obs["leiden"].nunique()` — number of clusters
- `adata.uns["rank_genes_groups"]` — marker genes for dotplot
- `adata.obsm["X_umap"]` — UMAP coordinates
- `adata.obs["annotation_confidence"]` — confidence levels
- `adata.obs["rare_cell_type"].notna()` — rare cell mask (use `.notna()`, NOT `.astype(bool)`)
- `adata.obs["doublet_score"]` — doublet scores
- `adata.obs["pct_counts_mt"]` — QC metric

## Image Fallback Strategy

1. Check `plots_v3/{pipeline}/{name}.png` (highest quality, post-refinement)
2. Check `plots_v2/{pipeline}/{name}.png`
3. Generate dynamically from h5ad data

## Marker Dotplot Generation

When `rank_genes_groups` is in `adata.uns`:
1. Extract top 3 genes per cell type from `adata.uns["rank_genes_groups"]["names"]`
2. Deduplicate gene list (preserve order)
3. Compute mean expression and pct expressed per cell type
4. Plot: x=gene, y=cell_type, size=pct, color=mean_expr
5. Colorbar for expression, size legend for % expressed
