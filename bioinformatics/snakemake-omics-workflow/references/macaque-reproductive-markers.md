# Macaque (Macaca mulatta) Reproductive Tissue Markers

Gene names are human orthologs (macaque genes share names). Use for Tier 1 marker-based annotation.

## Ovary Cell Types

| Cell Type | Markers (top candidates) |
|-----------|-------------------------|
| Oocyte | ZP1, ZP2, ZP3, ZP4, FIGLA, NOBOX, GDF9, BMP15, DAZL, DDX4 |
| Granulosa | FOXL2, CYP19A1, FSHR, AMH, HSD17B1, STAR, INHA, WT1 |
| Theca | CYP17A1, LHCGR, STAR, DLK1, PDGFRA, INSL3 |
| Stromal | COL1A1, COL1A2, DCN, LUM, PDGFRA, VIM, FBN1 |
| Endothelial | PECAM1, VWF, CDH5, ERG, KDR, FLT1, EMCN |
| Smooth muscle | ACTA2, MYH11, TAGLN, CNN1, MYLK |
| Macrophage | CD68, CD163, CSF1R, MRC1, MARCO, LYZ, S100A8 |
| T cell | CD3E, CD3D, CD3G, CD4, CD8A, IL7R, TRAC |
| NK cell | NKG7, GNLY, KLRB1, NCAM1, KLRC1 |
| B cell | CD19, MS4A1, CD79A, CD79B, PAX5 |
| Epithelial | EPCAM, KRT18, KRT8, CDH1, CLDN4 |

## Uterus (Hystera) Cell Types

| Cell Type | Markers (top candidates) |
|-----------|-------------------------|
| Epithelial luminal | EPCAM, KRT18, KRT8, CDH1, CLDN4, PAEP, SLC2A1 |
| Epithelial glandular | EPCAM, KRT18, KRT8, PAEP, SPP1, LIF, MUC1 |
| Stromal | COL1A1, COL1A2, DCN, LUM, PDGFRA, VIM, WNT4, IGFBP1 |
| Smooth muscle | ACTA2, MYH11, TAGLN, CNN1, MYLK |
| Endothelial | PECAM1, VWF, CDH5, ERG, KDR, FLT1 |
| Macrophage | CD68, CD163, CSF1R, MRC1, MARCO, LYZ, S100A8 |
| Uterine NK | NKG7, GNLY, KLRB1, NCAM1, KLRC1, CSF1, XCL1 |
| T cell | CD3E, CD3D, CD3G, CD4, CD8A, IL7R |
| B cell | CD19, MS4A1, CD79A |
| Neutrophil | FCGR3B, CSF3R, CXCR2, S100A8, S100A9 |

## Notes

- CellTypist models are human-trained but work for macaque immune cells (high orthology)
- Tissue-specific cells (oocyte, granulosa, theca, uterine NK) require manual marker annotation
- Uterine NK are distinct from peripheral blood NK (tissue-resident markers: CSF1, XCL1)
- Oocyte markers may be absent if ovary tissue lacks follicles (common in some preparations)
- Use top 3-4 markers per type for dotplot; full list for score_genes enrichment
