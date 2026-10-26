# scTE-Specific Cell Types and Macaque Reproductive Markers

## scTE-Specific Cell Types

scTE quantifies both gene expression AND transposable elements (TEs) / rRNA. This creates cell types that ONLY appear in scTE data, never in Cell Ranger:

### ERVK_high (Ovary, ~20% of cells)
Cells with high expression of ERV-K endogenous retrovirus elements.
- **Markers**: `MacERVK2_LTR1c`, `MacNERVK2-int`, `MacERVK2_LTR1a`, `MacNERVK2a-int`, `MacERVK2-int`
- **Expression**: 94-100% of cells in this cluster express ERVK elements
- **NOT contamination** — these are real cells with high retrotransposon activity
- **NOT present in Cell Ranger** — Cell Ranger doesn't quantify TE elements
- **Biological significance**: ERV-K reactivation is associated with aging, stress response, and cellular identity in primates

### rRNA_enriched (Hystera, ~7.5% of cells)
Cells with dominant rRNA transcript levels.
- **Markers**: `LSU_rRNA_eukarya`, `SSU_rRNA_eukarya`, `GSTA4`, `CACNA1G`, `CFAP99`, `CIROP`
- **Expression**: 100% express LSU/SSU rRNA, but hemoglobin markers (HBE1, ALAS2) are 0-4% (NOT erythroid)
- **NOT erythroid** despite rRNA dominance — check HBE1/ALAS2/SPTA1 to distinguish
- **NOT present in Cell Ranger** — rRNA quantification is scTE-specific

### Key Principle
When annotating scTE data, always include TE and rRNA marker categories. If you only use gene-based markers (like Cell Ranger), you'll get large Unknown clusters that are actually TE/rRNA-defined populations.

## Macaque Ovary Markers (validated)

```python
OVARY_MARKERS = {
    "Oocyte":          ["ZP1","ZP2","ZP3","ZP4","FIGLA","NOBOX","GDF9","BMP15","DAZL","DDX4"],
    "Granulosa":       ["FOXL2","CYP19A1","FSHR","AMH","HSD17B1","STAR","INHA","WT1"],
    "Theca":           ["CYP17A1","LHCGR","STAR","DLK1","PDGFRA","INSL3"],
    "Stromal":         ["COL1A1","COL1A2","DCN","LUM","PDGFRA","VIM","FBN1"],
    "Stromal_fst":     ["FST","VCAN","CRHBP","SERPINE2","HTRA1","GRB14","CDH2","FHOD3"],
    "Endothelial":     ["PECAM1","VWF","CDH5","ERG","KDR","FLT1","EMCN"],
    "Smooth_muscle":   ["ACTA2","MYH11","TAGLN","CNN1","MYLK"],
    "Epithelial":      ["EPCAM","KRT18","KRT8","CDH1","CLDN4"],
    "Neuronal":        ["GPC5","RBFOX1","PCDH11X","DACH2","KCTD8","LONRF2"],
    "Macrophage":      ["CD68","CD163","CSF1R","MRC1","MARCO","LYZ","S100A8","S100A9"],
    "T_cell":          ["CD3E","CD3D","CD3G","CD4","CD8A","IL7R","TRAC"],
    "NK_cell":         ["NKG7","GNLY","KLRB1","NCAM1","KLRC1"],
    "B_cell":          ["CD19","MS4A1","CD79A","CD79B","PAX5"],
    "Proliferating":   ["MKI67","TOP2A","STMN1","HMGB2","NUSAP1","CENPF","TYMS","UBE2C"],
    "ERVK_high":       ["MacERVK2_LTR1c","MacNERVK2-int","MacERVK2_LTR1a","MacNERVK2a-int","MacERVK2-int"],
    "HighMT":          ["MT-ND1","MT-ND2","MT-CO1","MT-CO2","MT-ATP6","MT-CYB"],
}
```

## Macaque Hystera Markers (validated)

```python
HYSTERA_MARKERS = {
    "Epithelial_luminal":   ["EPCAM","KRT18","KRT8","CDH1","CLDN4","PAEP","SLC2A1"],
    "Epithelial_glandular": ["EPCAM","KRT18","KRT8","PAEP","SPP1","LIF","MUC1","EYA2","BMPR1B"],
    "Stromal":              ["COL1A1","COL1A2","DCN","LUM","PDGFRA","VIM","WNT4","IGFBP1"],
    "Smooth_muscle":        ["ACTA2","MYH11","TAGLN","CNN1","MYLK"],
    "Endothelial":          ["PECAM1","VWF","CDH5","ERG","KDR","FLT1"],
    "Macrophage":           ["CD68","CD163","CSF1R","MRC1","MARCO","LYZ","S100A8"],
    "Uterine_NK":           ["NKG7","GNLY","KLRB1","NCAM1","KLRC1","CSF1","XCL1"],
    "T_cell":               ["CD3E","CD3D","CD3G","CD4","CD8A","IL7R"],
    "B_cell":               ["CD19","MS4A1","CD79A"],
    "Neutrophil":           ["FCGR3B","CSF3R","CXCR2","S100A8","S100A9"],
    "Proliferating":        ["MKI67","TOP2A","STMN1","HMGB2","NUSAP1","CENPF","TYMS","UBE2C"],
    "rRNA_enriched":        ["LSU_rRNA_eukarya","SSU_rRNA_eukarya","GSTA4","CACNA1G","CFAP99","CIROP"],
    "HighMT":               ["MT-ND1","MT-ND2","MT-CO1","MT-CO2","MT-ATP6","MT-CYB"],
}
```

## Batch Annotation Script Pattern

When annotating multiple h5ad files (e.g., ovary scTE + Cell Ranger, hystera scTE + Cell Ranger):

```python
# Script: annotate_all.py — accepts multiple --input files
p.add_argument("--input", required=True, nargs="+")
p.add_argument("--tissue", required=True, choices=["ovaries", "hystera"])

# Auto-detect counter from filename
for input_h5ad in args.input:
    basename = os.path.basename(input_h5ad)
    if "_scTE_" in basename:
        counter = "scTE"
    elif "_cellranger_" in basename:
        counter = "cellranger"
```

**Output structure**:
```
<tissue>/
  <tissue>_<counter>_annotated.h5ad
  <tissue>_<counter>_markers.tsv
  plots/<counter>/cluster_annotate/
    umap_cell_type.png
    umap_leiden.png
    umap_sample_id.png
    cell_type_proportions.png
    dotplot_<tissue>_<counter>_markers.png
    violin_qc.png
```

## Resolving Unknown Clusters

When clusters have 0 marker overlap (Unknown), check their top DEGs:

1. **TE elements** (MacERVK2_*, LINE, SINE) → scTE-specific, add TE marker category
2. **rRNA** (LSU_rRNA, SSU_rRNA) → scTE-specific, check if erythroid (HBE1/ALAS2) or just rRNA-enriched
3. **Cell cycle** (MKI67, TOP2A, STMN1, HMGB2) → Proliferating
4. **ENSMMUG IDs** (unannotated macaque genes) → check Cell Ranger cluster for ortholog hints
5. **MT genes** (MT-CO1, MT-ND1) → HighMT (dying/stressed cells)
