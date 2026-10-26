# Case: Ovaries v8 — Spatial Discontinuity Fix + Annotation Failure (2026-09-18)

## Problem
User reported cluster 15 (Theca_Stromal_Cells) and cluster 18 (Oocyte) had
"非常大的分散群" in the leiden UMAP. Initial analysis incorrectly focused on
n_pcs=15 being too low (PCA variance ratio showed it was reasonable — PC1
only 3.1%, flat after PC15).

## Root Cause
Cluster 18 had **spatially disconnected fragments** in UMAP:
- max_gap=4.254 on UMAP1 (67+370 cells, two separate groups)
- `_check_cluster_continuity` existed in mode_auto but was positioned AFTER
  the early exit `if not flagged: break` → never executed

Cluster 15 had max_gap=1.728 (borderline) — appeared dispersed in UMAP but
marker expression analysis (CYP17A1, CYP11A1) showed it was a compact,
specific population. The "dispersed" appearance was a UMAP visualization
artifact, not a clustering problem.

## Key Lesson: Investigate Before Concluding
The user corrected the agent multiple times:
1. "你刚才给我的信息有误" — analyzed default params instead of actual run script params
2. "你确定是分散的问题吗，能不能好好查查" — jumped to n_pcs conclusion without checking
3. "你查询marker干嘛" — went off-track when user said it's a clustering problem
4. "是聚类问题" — user had to explicitly redirect
5. "如果你怀疑什么,就检查验证,不要猜测" — agent guessed about Cluster 4 biology instead of verifying

**Rule**: When user says clustering is bad, check spatial continuity FIRST.
Don't assume parameter issues without evidence. If you suspect something,
VERIFY with data — don't present guesses as conclusions.

## Fix Applied
1. Moved `_check_cluster_continuity` before early exit in mode_auto
2. Added `min_side_pct=0.05` parameter to filter outlier false positives
3. Added `plot_markers()` method to ScanpyPlotter for marker UMAP visualization
4. Improved Step 0 prompt to include transitional/mixed-phenotype cell types
5. Redesigned plot_markers to group by cell type (not cluster), plot ALL markers

## Results
- v8 iteration 1: detected Cluster 11 (44+510) and 18 (67+370) as discontinuous
- Cluster 11 outlier cells (74) filtered by QC
- Cluster 16 misannotated cells filtered
- Iteration 3: all clusters clean, 19 clusters, 0 flagged
- Marker plots: 43 unique markers, 19 clusters

## Additional Finding: Cluster 4 Annotation Failure

Cluster 4 was annotated as Smooth_Muscle_Cell but is actually a dual-phenotype
population (SMC + stromal/ECM remodeling). The Step 0 tissue query returned 40
cell types for macaque ovaries but **Myofibroblast was missing**.

### Evidence
| Gene | C4 | C12 (pure SMC) | C5 (Stromal) | Conclusion |
|---|---|---|---|---|
| IGFBP5 | 3.804, 99.5% | 2.392, 93% | 3.245, 97% | C4 highest in dataset |
| SFRP1 | 2.570, 91.4% | 0.106, 10.7% | 0.968, 48% | C4 highest, NOT ambient RNA |
| DCN | 2.144, 95.8% | 0.302, 26% | 2.410, 93% | C4 ≈ C5, >> C12 |
| MYH11 | 2.875 | 3.044 | 0.683 | C4 < C12 (SMC marker lower) |

Fix: added to Step 0 prompt:
```
- IMPORTANT: Include transitional, activated, and mixed-phenotype cell types
  (e.g. Myofibroblast, Activated_Stromal_Cell, ...)
```

## Parameters
```
resolution=0.8, n_neighbors=50, n_pcs=15(auto), max_iterations=3
batch_method=harmony, species=Mmul_10, skip_te=True
UMAP: min_dist=0.1, spread=0.8
```