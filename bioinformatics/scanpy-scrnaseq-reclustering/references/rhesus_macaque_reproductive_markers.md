# Rhesus Macaque (Macaca mulatta) Reproductive Tissue Markers

## Species Notes
- Gene IDs: ENSMMUG prefix (e.g., ENSMMUG00000064799)
- MT genes: UPPERCASE (MT-ND1, MT-COX1, MT-ATP8, etc.)
- KRT8: ABSENT in macaque genome
- Cellranger: ~26,509 genes; scTE: ~19,141 genes

## Hystera (Uterus) Markers — Validated 2026-09-01

All markers confirmed present in cellranger dataset.

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

**Note**: KRT8 absent in macaque — Epithelial cluster still identifiable via EPCAM/KRT18/CDH1.
TPSAB1/TPSB2 absent in macaque gene annotation — Mast_cell may not cluster independently.

### Validated Results (cellranger, 5 samples)
- 43,330 cells → 17 Leiden clusters → 9 merged cell types
- Stromal 32.1%, Endothelial 19.2%, Smooth_muscle 14.4%, Epithelial 14.1%
- Pericyte 10.8%, T_NK_cell 6.3%, Macrophage 2.0%, NK_cell 0.6%, Proliferating 0.4%

### Validated Results (scTE, 5 samples)
- 42,795 cells → 8 cell types (NK_cell not separated, merged into T_NK_cell)
- Stromal 39.0%, Endothelial 19.6%, Smooth_muscle 13.1%, Epithelial 10.5%

### Config
`n_top_genes=2000, n_neighbors=50, min_dist=0.1, spread=0.8, resolution=0.6`
QC: n_genes 200-8000, pct_counts_mt ≤ 25, doublet filter if available

## Ovary Markers — Same as macaque_ovary_analysis.md

See `macaque_ovary_analysis.md` for full ovary markers and analysis results.
