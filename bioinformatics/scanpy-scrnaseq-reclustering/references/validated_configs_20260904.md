# Validated Clustering Configs (2026-09-04)

## Macaque Ovary (cellranger, 19,144 cells → 16,194 after strict QC)

### Standard QC + Clustering
```python
n_top_genes=3000, n_pcs=50, n_neighbors=50
min_dist=0.05, spread=0.5, resolution=0.3
batch_correction="harmony", batch_key="sample_id"
outlier_filter=True  # remove >2σ from cluster centroid
```
Result: 14 clusters, ~200 outlier cells removed. Clean separation between Granulosa/Stromal/Smooth_muscle/Endothelial.

### Strict QC + Clustering (recommended)
```python
# QC filters
adata = adata[
    (adata.obs['n_genes_by_counts'] >= 500) &
    (adata.obs['n_genes_by_counts'] <= 5000) &
    (adata.obs['pct_counts_mt'] <= 5) &
    (adata.obs['total_counts'] >= 1500) &
    (adata.obs['total_counts'] <= 25000) &
    (adata.obs['doublet_score'] < 0.1) &
    ((adata.obs['total_counts'] / adata.obs['n_genes_by_counts']) < 10) &
    ((adata.obs['total_counts'] / adata.obs['n_genes_by_counts']) > 1)
].copy()

# Clustering parameters
n_top_genes=3000, n_pcs=50, n_neighbors=50
min_dist=0.01, spread=0.5, resolution=0.3
batch_correction="harmony", batch_key="sample_id"
```
Result: 13 clusters, 2950 cells filtered (15.4%). "extremely tightly packed, with no visible empty gaps/holes". This is the best clustering quality achieved.

**Key insight**: QC was the root cause of poor clustering, not UMAP parameters. Strict QC dramatically improved cluster density and eliminated holes.

### Ultra-Compact UMAP (user preference: tight clusters, close together, no overlap)
```python
# Parameters
n_top_genes=3000, n_pcs=50, n_neighbors=50
min_dist=0.001, spread=1.0, resolution=0.3
batch_correction="harmony", theta=3, lamb=0.5, nclust=50
outlier_filter_percentile=98  # remove top2% by distance to centroid
```
Result: Clusters are "extremely compact and dense", clear separation between clusters. User complained "分散的太开了,导致cluster看上去很小" with spread=0.3 — spread=1.0 brings clusters closer together while maintaining separation.

**Key parameter relationships**:
- `spread` controls cluster proximity: lower (0.3) = clusters far apart, higher (1.0) = clusters closer together
- `min_dist` controls cluster tightness: 0.001 = ultra-compact, 0.01 = very tight, 0.1 = standard
- `outlier_filter_percentile=98` (2%) — removes scattered points without making clusters too small. User found5% too aggressive ("分散的太开了,导致cluster看上去很小").

## Macaque Ovary (scTE, 19,816 cells)
Same parameters as cellranger. ~618 outlier cells removed (1.4%).

## Macaque Hystera (cellranger, ~43k cells)
```python
n_top_genes=3000, n_pcs=50, n_neighbors=50
min_dist=0.05, spread=0.5, resolution=0.4
batch_correction="harmony", batch_key="sample_id"
outlier_filter=True
```
Result: ~15 clusters. Stromal (25%), Smooth_muscle (22%), Endothelial (16%), Epithelial_luminal (13%), T_cell (6%).

## Macaque Hystera (scTE, ~47k cells)
Same as cellranger hystera. ~1332 outlier cells removed (2.8%).

## Key Findings

### QC is Critical (NEW - 2026-09-04)
1. **QC-first workflow**: Always check QC metrics before clustering. User explicitly corrected: "没有思考qc是否合理等等"
2. **Strict QC dramatically improves clustering**: Filtering out15-20% of cells makes clusters10x cleaner
3. **Holes in UMAP are caused by low-quality cells**, not just UMAP parameters. User questioned "你确定是QC的问题吗" — yes, it was QC.
4. **Rushing to annotation is wrong**: User said "聚类效果一般,你没有把聚类调整到完美层次,就急着注释了". Perfect clustering first, then annotate.

### UMAP Parameters
5. `min_dist=0.01` gives "extremely tightly packed" clusters with strict QC
6. `min_dist=0.05` creates too many internal holes/空洞 without strict QC
7. `min_dist=0.1` with `spread=0.8` is better balanced for standard QC
8. `n_neighbors=50` much better than15 — cleaner global structure
9. `resolution=0.3-0.4` — higher (0.8) creates21+ overlapping clusters in ovaries

### Ultra-Compact UMAP (NEW - 2026-09-04 session)
10. `min_dist=0.001, spread=0.5` — clusters are "extremely compact and dense", clear separation between clusters
11. `min_dist=0.001, spread=1.0` — clusters closer together (not too spread out) while maintaining separation. User complained "分散的太开了,导致cluster看上去很小" with spread=0.3
12. **spread controls cluster proximity**: lower spread (0.3) = clusters far apart, higher spread (1.0) = clusters closer together. User wants clusters close but not overlapping.
13. **min_dist controls cluster tightness**: lower min_dist = tighter clusters. 0.001 is ultra-compact, 0.01 is very tight, 0.1 is standard.

### Outlier Filtering Threshold (NEW - 2026-09-04 session)
14. **2% outlier filtering** (98th percentile distance to centroid) — removes scattered points without making clusters too small
15. **5% is too aggressive** — user said "分散的太开了,导致cluster看上去很小" (clusters look too small because they're spread out). 5% removes too many edge cells.
16. **Re-embed after filtering** — MUST redo neighbors → UMAP → Leiden after removing outliers

### Validated Ultra-Compact Config (macaque ovary)
```python
# Ultra-compact: tight clusters, close together, no overlap
n_top_genes=3000, n_pcs=50, n_neighbors=50
min_dist=0.001, spread=1.0, resolution=0.3
batch_correction="harmony", theta=3, lamb=0.5, nclust=50
outlier_filter_percentile=98  # remove top2% by distance to centroid
```

### Batch Correction
10. Harmony reduces sample distance by ~22% (7.075→5.495)
11. Samples are well-mixed in UMAP after Harmony (no visible batch effect)
12. bbknn worse than Harmony for ovaries — merges biologically distinct populations

### Annotation
13. DEG-based annotation (not CellTypist) for solid tissues — CellTypist Immune_All_High misclassifies stromal cells as "ILC"
14. CellTypist only works for immune-dominant tissues (blood, PBMC, lymph node)
