# Macaque Ovary Marker Analysis Results

## Marker Overlap Between Close Cell Types

### Pericyte vs Smooth_muscle (UMAP distance: 2.51)
- Pericyte expressing Smooth_muscle markers: ACTA2 77.1%, TAGLN 84.7%, MYH11 56.8%
- Smooth_muscle expressing Pericyte markers: PDGFRB 61.9%, RGS5 49.4%
- **Both are contractile cell types sharing收缩蛋白基因**

### Stromal vs Theca (UMAP distance: 3.61)
- Theca expressing Stromal markers: DCN 82.0%, VIM 94.0%, PDGFRA 92.5%
- **Theca is a specialized ovarian stromal cell (theca interna produces androgens)**

### Stromal vs Smooth_muscle (UMAP distance: 7.50)
- Stromal expressing Smooth_muscle markers: ACTA2 37.9%, TAGLN 46.6%
- Smooth_muscle expressing Stromal markers: VIM 85.2%, PDGFRB 65.1%

## Cluster Fragmentation Analysis (Before Merging)

### Cellranger (resolution=1.0, 23 clusters)
| Cell Type | Clusters | Max Same-Type Dist | Min Diff-Type Dist | Issue |
|-----------|----------|-------------------|-------------------|-------|
| Stromal | 5 | 13.98 | 2.34 (Theca) | ⚠️ Fragmented |
| Smooth_muscle | 3 | 11.49 | 2.70 (Pericyte) | ⚠️ Fragmented |
| Endothelial | 4 | 6.73 | 4.12 (Proliferating) | ⚠️ Fragmented |
| OSE | 4 | 4.76 | 1.39 (Proliferating) | ⚠️ Fragmented |
| Granulosa | 2 | 1.47 | 8.22 | ✓ OK |

### After Merging (resolution=0.6)
- Cellranger: 18 clusters → 9 merged groups (matching 9 cell types)
- scTE: 17 clusters → 9 merged groups (matching 9 cell types)
- All cell types now contiguous in UMAP

## Rare Cell Type Investigation

### Oocyte (DDX4+ cells: 305)
- Only 54 cells co-express 2+ oocyte markers (DDX4, DAZL, GDF9, ZP3, FIGLA)
- Too rare to form independent cluster
- Stored in `adata.uns["rare_cell_types"]["Oocyte"]`

### B_cell (CD79A+ cells: 325)
- 120 cells co-express 2+ B cell markers (CD79A, CD79B, MS4A1, PAX5)
- CD79A+ Macrophage cells (147): only 29% express CD68, 5.4% express CD163
- Low co-expression suggests ambient RNA contamination, not doublets

### Luteal (PRLR+ cells: 4,931)
- 1,137 cells co-express 2+ luteal markers (HSD3B1, PRLR)
- HSD3B1 has 0 positive cells in cellranger data
- PRLR mostly in Stromal (3,580 cells) — no clear separation

### STAR Background Expression
- STAR+ Stromal cells: 3,373
- Only 6.4% express CYP17A1, 8.3% express CYP11A1
- Low-level background, not real Theca/Luteal

## Nature Reviewer Fixes Applied (v3)

1. ✓ Missing cell types documented as rare
2. ✓ UMAP legend added (right margin, fontoutline=2)
3. ✓ Doublet verification UMAPs (CD79A, STAR)
4. ✓ Colorblind-friendly palette (Okabe-Ito)
5. ✓ Sample UMAP (post-Harmony)
6. ✓ Proliferating labeled as "Proliferating (mixed)"
7. ✓ Marker expression UMAPs for rare cell types

## Validated Pipeline Configuration

```bash
python recluster_annotate_v3.py \
  --input ovaries_cellranger_merged.h5ad \
  --output ovaries_cellranger_annotated.h5ad \
  --marker-file macaque_ovary_markers.tsv \
  --plot-dir plots_v3/cellranger \
  --n-top-genes 2000 --n-pcs 50 --n-neighbors 50 --resolution 0.6
```

### Results (original 7-sample analysis)
- 62,474 cells, 18 clusters → 9 merged cell types
- Harmony batch correction: 7 samples, converged in 7 iterations
- All clusters annotation confidence: high
- Rare cell types: Oocyte (54), B_cell (120), Luteal (1,137)

### Results (2-sample luancao dataset, 2026-09)
- CellRanger: 19,144 cells, 18 clusters → 10 merged cell types
  - Granulosa 25.1%, Smooth_muscle 23.0%, Stromal 22.3%, Endothelial 18.5%
  - OSE 2.8%, Macrophage 2.6%, Pericyte 2.2%, Theca 1.7%, T_NK_cell 1.4%, Proliferating 0.6%
- scTE: 17,239 cells → 9 merged cell types
- Harmony: 2 samples, converged
- All annotation confidence: high
- Key markers: FSHR/CYP19A1 (Granulosa), CYP17A1/STAR (Theca), KRT18/EPCAM/WT1 (OSE)
