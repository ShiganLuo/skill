# Rhesus Macaque Hystera (Uterus) Markers

Validated on rhesus macaque (Macaca mulatta) scRNA-seq data.
Cellranger: 26,509 genes. scTE: 19,141 genes.

## Markers

| Cell Type | Markers |
|-----------|---------|
| Epithelial | EPCAM, KRT18, CDH1, KRT8, FOXA2 |
| Glandular_Epi | ESR1, PGR, FOXA2, LGR5, WNT4 |
| Stromal | COL1A1, COL3A1, DCN, LUM, VIM, PDGFRA |
| Smooth_muscle | ACTA2, MYH11, TAGLN, CNN1, DES |
| Endothelial | PECAM1, VWF, CDH5, KDR, EMCN |
| Macrophage | CD68, CD163, CD74, CSF1R, C1QA |
| T_NK_cell | CD3E, CD3D, CD8A, NKG7, GZMB |
| B_cell | CD79A, CD79B, MS4A1, PAX5 |
| NK_cell | NKG7, GNLY, KLRD1, NCAM1 |
| Mast_cell | KIT, TPSAB1, TPSB2, CPA3 |
| Pericyte | RGS5, PDGFRB, NOTCH3, ABCC9 |
| Proliferating | MKI67, TOP2A, PCNA, CENPF |

## Key Expression UMAP Markers

EPCAM, ESR1, COL1A1, ACTA2, PECAM1, CD68, CD3E, RGS5, MKI67

## Notes

- KRT8 absent in macaque genome — use KRT18 instead
- Stromal is the dominant population (~30-40% of cells)
- Endothelial is surprisingly abundant (~19%) — may reflect tissue vascularization
- Epithelial cells show sample-specific enrichment (zigong-1411200 has most)
- Pericyte and Smooth_muscle share contractile markers (ACTA2, TAGLN) — expect UMAP proximity

## Validated Config

`n_top_genes=2000, n_neighbors=50, min_dist=0.1, spread=0.8, resolution=0.6`
Produced 17 Leiden clusters → 9 merged cell types (cellranger), 8 (scTE).
