# scTE vs Cell Ranger: Quantitative Differences

## Overview

scTE and Cell Ranger produce different cell type annotations even for the same tissue. This is NOT a bug — it's a fundamental difference in quantification strategy.

## Quantitative Matrix Differences

| Metric | scTE | Cell Ranger |
|--------|------|-------------|
| Total genes | 19,141 | 26,509 |
| Protein-coding | 16,988 | ~20,000+ |
| TE genes | 1,272 | 0 |
| Other (lncRNA, etc.) | 881 | ~6,000+ |

**Key fact**: 1,271 of 1,272 TE genes in scTE are NOT in Cell Ranger. Only 1 TE gene overlaps.

**Protein-coding overlap**: 16,980 / 16,988 (99.95%) — almost identical.

## Why Annotations Differ

### 1. Read Allocation (Root Cause)

scTE allocates some reads to TE quantification that Cell Ranger counts toward genes:
- Same protein-coding gene → different expression values in two matrices
- This cascades: different PCA → different UMAP → different clusters → different DEGs → different annotations

### 2. Clustering Resolution

| Method | Resolution | Clusters | Cell Types |
|--------|-----------|----------|------------|
| Cell Ranger (manual) | 0.8 | 22 | 13 |
| Auto mode (scTE) | 0.4 | 13 | 9-10 |

Higher resolution → more subtypes split (Luteal, Cumulus, Myofibroblast, Pericyte)

### 3. Annotation Method

| Method | Approach | Precision |
|--------|----------|-----------|
| Cell Ranger | Manual curated markers (OVARY_MARKERS) + specificity scoring | High |
| Auto mode | LLM + canonical_markers + specificity scoring | Medium-High |

## Cell Type Correspondence

| Cell Ranger (13 types) | Auto v3 (9 types) | Match |
|------------------------|-------------------|-------|
| Luteal (22.8%) | Granulosa_cells (25.0%) | ≈ merged |
| Endothelial (20.4%) | Endothelial (23.4%) | ✓ |
| Stromal (19.3%) | Stromal_cells (20.4%) | ✓ |
| Myofibroblast (9.2%) | Smooth_muscle (19.7%) | ≈ merged |
| Pericyte (6.6%) | Smooth_muscle | ≈ merged |
| Smooth_muscle (6.5%) | Smooth_muscle | ✓ (includes Myo+Peri) |
| Cumulus (5.0%) | Granulosa_cells | ≈ merged |
| Macrophage (2.7%) | Macrophage (2.8%) | ✓ |
| Epithelial (2.0%) | Mesothelial_cells (1.1%) | ≈ |
| T_cell (1.6%) | T_cell (1.4%) | ✓ |
| Lymphatic_endo (1.6%) | Endothelial | ≈ merged |
| Mesothelial (1.6%) | Mesothelial_cells (1.1%) | ✓ |
| Proliferating (0.7%) | Granulosa_cells | ≈ merged |
| — | Theca_cells (1.6%) | ✓ (auto only) |
| — | Unverified_TE (4.5%) | scTE only |

## Smooth_muscle Quantity Validation

Cell Ranger: SM(6.5%) + Myofibroblast(9.2%) + Pericyte(6.6%) = 22.3%
Auto v3: Smooth_muscle_cells = 19.7%

**Quantities match!** The difference is naming granularity, not cell count.

## Key Takeaways

1. **Both methods are correct** — they measure different things (TE+genes vs genes only)
2. **Big cell types match well** — Endothelial, Stromal, Macrophage, T_cell proportions are similar
3. **Small subtypes differ** — Luteal, Cumulus, Myofibroblast require higher resolution + tissue-specific markers
4. **scTE has unique types** — Unverified_TE (4.5%) only appears in scTE data
5. **Resolution is the main lever** — increasing from 0.4 to 0.8 would split more subtypes

## Recommendations

- For **publication**: use Cell Ranger + manual annotation for precise subtype identification
- For **exploration**: use auto mode for fast, tissue-agnostic annotation
- For **TE analysis**: use scTE data (Cell Ranger has 0 TE genes)
- For **comparison**: always note the quantification method when comparing cell type proportions
