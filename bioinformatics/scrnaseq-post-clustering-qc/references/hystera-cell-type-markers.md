# Hystera (Uterus) Cell Type Markers and QC Notes

## Cell Types in Hystera

Standard cell types identified in macaque uterus:
- Epithelial_luminal: EPCAM, KRT18, KRT8, CDH1, CLDN4, PAEP, SLC2A1
- Epithelial_glandular: EPCAM, KRT18, KRT8, PAEP, SPP1, LIF, MUC1, PAX8, ESR1
- Stromal: COL1A1, COL1A2, DCN, LUM, PDGFRA, VIM, WNT4, IGFBP1
- Smooth_muscle: ACTA2, MYH11, TAGLN, CNN1, MYLK
- Pericyte: RGS5, PDGFRB, NOTCH3, MCAM, ABCC9, KCNJ8
- Schwann_cell: PMP22, S100B, CDH19, PLP1, MPZ, CRYAB, MAL, GPM6B
- Endothelial: PECAM1, VWF, CDH5, ERG, KDR, FLT1
- Macrophage: CD68, CD163, CSF1R, MRC1, MARCO, LYZ, S100A8
- Uterine_NK: NKG7, GNLY, KLRB1, NCAM1, KLRC1, CSF1, XCL1
- T_cell: CD3E, CD3D, CD3G, CD4, CD8A, IL7R
- B_cell: CD19, MS4A1, CD79A
- Neutrophil: CSF3R, CXCR2, S100A8, S100A9
- Proliferating: MKI67, TOP2A, STMN1, HMGB2, NUSAP1, CENPF, TYMS, UBE2C

## QC Findings

### Hystera Cell Ranger
- Cluster with ENSMMUG + MT-COX2/MT-COX3 as top markers = low quality
- Cluster 10 had SM + Stromal co-expression (8.8%) with high doublet score (0.10) → doublets
- After removing102 doublets, Smooth_muscle clusters merged

### Hystera scTE
- Cluster 4 was "Unknown" with LSU_rRNA_eukarya, SSU_rRNA_eukarya as top markers = ribosomal contamination
- Cluster 0 (Endothelial) had low gene count (590) and UMI (1723) = low quality
- After filtering, all clusters properly annotated

## Key Differences: Cell Ranger vs scTE

- scTE has additional TE-specific cell types: ERVK_high, Alu_high
- scTE may have different cluster structure due to TE quantification
- Same QC workflow applies to both
