# scRNA-seq Cell Type Annotation Patterns

## Marker-Based Annotation Algorithm

### Specificity-Weighted Scoring

Simple marker overlap counting fails when markers are shared across cell types (e.g., COL1A1 appears in both Stromal and Pericyte). Use specificity-weighted scoring:

```python
# Compute gene specificity: 1 / (number of cell types it appears in)
gene_specificity = {}
for ct, markers in valid_markers.items():
    for g in markers:
        gene_specificity[g] = gene_specificity.get(g, 0) + 1
for g in gene_specificity:
    gene_specificity[g] = 1.0 / gene_specificity[g]

# Score each cluster against each cell type
for clust, top_genes in cluster_markers.items():
    top_set = set(top_genes)
    for ct, markers in valid_markers.items():
        matched = top_set & markers
        # Rank-weighted: higher-ranked DEGs get more weight
        score = 0.0
        for g in matched:
            rank = top_genes.index(g)  # 0-based
            rank_weight = 1.0 / (1.0 + rank * 0.1)  # rank0=1.0, rank10=0.5, rank49=0.17
            score += gene_specificity.get(g, 0) * rank_weight
```

**Why rank weighting**: When Pericyte (RGS5 at rank 2) and Stromal (COL1A1 at rank 8) tie on specificity, the higher-ranked marker wins. This correctly separates Pericyte from Smooth_muscle/Stromal in UMAP-space.

### HGNC Gene Validation

Always validate marker genes against HGNC approved symbols before use:

```bash
curl -s "https://www.genenames.org/cgi-bin/download/custom?col=gd_app_sym&col=gd_status&status=Approved&hgnc_dbtag=on&order_by=gd_app_sym_sort&format=text&submit=submit" | tail -n+2 | cut -f1 | sort -u > /tmp/hgnc_symbols.txt
```

Common false positives from automated text extraction:
- SARS, COVID, TMPRSS2 (COVID papers)
- CTB, EVTB, STB (cell type abbreviations)
- FPKM, ZGA (measurement/development terms)
- AKT, IGF, PI3K, MAPK (pathway names)
- MT-ND1, MT-CO1 (mitochondrial genes, not cell type markers)

### Post-Annotation Validation

1. **UMAP spatial check**: Same-labeled clusters should be spatially proximate. Distant clusters with the same label indicate misannotation.
2. **Biological plausibility**: Check cell type proportions against published reference ranges.
3. **Negative markers**: Confirm that absent markers are truly low in each cluster.

## Macaque (Macaca mulatta / M. fascicularis) Ovary/Uterus Markers

Species: Macaque gene names are human orthologs (>99% identity).

### Key References

- **Zhao et al. (2026)** Cell Discov. PMID:42552301 — Cynomolgus macaque HPOU axis (ovary + uterus + hypothalamus + pituitary). DOI: 10.1038/s41421-026-00908-2
- **Wang et al. (2024)** Stem Cell Res Ther. PMID:38191526 — Rhesus macaque ovary snRNA-seq. DOI: 10.1186/s13287-023-03631-x

### Ovary Cell Type Markers

| Cell Type | Markers | Source |
|-----------|---------|--------|
| Oocyte | ZP1,ZP2,ZP3,ZP4,FIGLA,NOBOX,GDF9,BMP15,DAZL,DDX4 | Wang 2024; CellMarker DB |
| Granulosa | HSD17B1,FSHR,CYP19A1,AMH,FOXL2,INHA | Zhao 2026 (HSD17B1+ GC) |
| Theca | STAR,CYP17A1,DLK1,INSL3 | Zhao 2026 (STAR+ theca) |
| Stromal | COL1A1,COL1A2,DCN,LUM,PDGFRA,VIM | Zhao 2026 (COL1A1+ SC) |
| Endothelial | PECAM1,VWF,CDH5,ERG,KDR,FLT1,EMCN | Zhao 2026 (PECAM1+ Endo) |
| Epithelial | EPCAM,KRT18,KRT8,CDH1,CLDN4 | Zhao 2026 (EPCAM+ Epi) |
| Smooth_muscle | ACTA2,MYH11,TAGLN,CNN1,MYLK | Zhao 2026 (MYH11+ SMC) |
| Pericyte | RGS5,PDGFRB,NOTCH3,MCAM | Zhao 2026 (RGS5+ pericyte) |
| Macrophage | C1QC,C1QA,CD68,CD163,CSF1R,MRC1,MARCO | Zhao 2026 (C1QC+ MAC) |
| Monocyte | CD14,LYZ,S100A8,S100A9 | Zhao 2026 (CD14+ monocyte) |
| T_cell | CD3G,CD3D,CD3E,CD4,CD8A,IL7R,TRAC | Zhao 2026 (CD3G+ T cell) |
| Proliferating | MKI67,TOP2A,STMN1,HMGB2,NUSAP1,CENPF,TYMS,UBE2C | Zhao 2026 (MKI67+ Pro) |

**Pitfalls**:
- STAR is Theca-specific, NOT Granulosa
- LHCGR is Granulosa-specific, NOT Theca
- WT1 is Theca/Stromal, NOT Granulosa
- Neuronal markers (GPC5, RBFOX1) should NOT appear in ovary — likely misannotation
- Stromal_fst (FST, VCAN) has no literature support as a distinct ovary cell type

### Uterus Cell Type Markers

| Cell Type | Markers | Source |
|-----------|---------|--------|
| Epithelial_luminal | EPCAM,KRT18,KRT8,CDH1,CLDN4,PAEP,SLC2A1 | Zhao 2026 (EPCAM+ Epi) |
| Epithelial_glandular | PAX8,ESR1,EYA2,BMPR1B,ENPP3 | DEG-derived; PAX8/ESR1 are canonical |
| Stromal | COL1A1,COL1A2,DCN,LUM,VIM,WNT4,IGFBP1,SFRP4 | Zhao 2026 (SFRP4+ SC) |
| Smooth_muscle | ACTA2,MYH11,TAGLN,CNN1,MYLK | Zhao 2026 (MYH11+ SMC) |
| Pericyte | RGS5,PDGFRB,NOTCH3,MCAM,ABCC9,KCNJ8 | Zhao 2026 (RGS5+ pericyte) |
| Endothelial | PECAM1,VWF,CDH5,ERG,KDR,FLT1 | Zhao 2026 (PECAM1+ Endo) |
| Macrophage | C1QC,C1QA,CD68,CD163,CSF1R,MRC1 | Zhao 2026 (C1QC+ MAC) |
| Uterine_NK | NKG7,GNLY,KLRB1,NCAM1,KLRC1,CSF1,XCL1 | Zhao 2026 |
| T_cell | CD3G,CD3D,CD3E,CD4,CD8A,IL7R | Zhao 2026 (CD3G+ T cell) |
| Schwann_cell | PMP22,S100B,CDH19,PLP1,MPZ,CRYAB,MAL,GPM6B | Jäkel & Dimou 2017; Chen 2021 |
| Proliferating | MKI67,TOP2A,STMN1,HMGB2 | Zhao 2026 (MKI67+ Pro) |

**Pitfalls**:
- FCGR3B is NOT in macaque genome — remove from Neutrophil markers
- EYA2/BMPR1B are from DEG analysis, not canonical glandular markers
- rRNA genes (LSU_rRNA_eukarya, SSU_rRNA_eukarya) are NOT HGNC symbols
- MT genes (MT-ND1, MT-CO1) are not cell type markers

### scTE-Specific Cell Populations

scTE quantifies transposable elements alongside genes. Two populations are scTE-specific:

- **ERVK_high**: High endogenous retrovirus K expression (MacERVK2_LTR1c, MacNERVK2-int, etc.). Not found in CellRanger data.
- **Alu_high**: High Alu SINE element expression (AluSz, AluSx, AluY, etc.). Not found in CellRanger data.

These are real biological populations, not artifacts. They appear only in scTE because TE quantification reveals expression patterns invisible to gene-only methods.

## Harmony Batch Correction Pitfall

After Harmony batch correction, `sc.pp.neighbors` MUST use `use_rep="X_pca_harmony"`:

```python
# CORRECT
sc.pp.neighbors(adata, n_neighbors=50, n_pcs=n_pcs, use_rep="X_pca_harmony")

# WRONG — uses uncorrected X_pca
sc.pp.neighbors(adata, n_neighbors=50, n_pcs=n_pcs)
```

Without `use_rep`, downstream UMAP and Leiden clustering use uncorrected PCA coordinates, negating the batch correction.

## HVG Plotting Best Practices

Plot HVGs BEFORE subsetting to maintain all-gene background:

```python
sc.pp.highly_variable_genes(adata, ..., subset=False)
plotter.plot_hvg(adata, n_top_genes=n_top_genes)  # all genes visible
adata = adata[:, adata.var["highly_variable"]].copy()  # then subset
```

The plot should show:
- Left panel: mean expression vs normalized dispersion scatter (grey=non-HVG, blue=HVG), with cutoff line and gene count
- Right panel: sorted normalized dispersion elbow curve with selected count
