# Boundary Sharpness & Spatial Detection Lessons

## The "Cluster 17 carved out of Cluster 6" lesson

In one dataset, Leiden at resolution=0.8 split what should be a single
Granulosa cell population into two clusters: a large Cluster 6 (1760
cells) and a tiny Cluster 17 (810 cells) that sat INSIDE Cluster 6's
UMAP region.

The k-NN composition test caught this: Cluster 17's cells had 80%+ of
their nearest neighbors in Cluster 6, not in their own cluster. The
boundary between them was not sharp — it was an arbitrary Leiden cut.

The orchestrator saw `boundary_quality="fuzzy"` for both clusters and
chose `adjust_resolution_and_recluster` to merge them.

## Discontinuity_details — imbalance vs balance distinction

A cluster can be spatially discontinuous in two ways:
1. **Imbalanced**: one large blob + one tiny outlier (e.g., 1588+1 cells).
   The tiny group is likely noise or a misassigned cell. Usually safe to
   filter the small side.
2. **Balanced**: two medium-sized groups separated by a gap (e.g., 800+600
   cells). This suggests the cluster merged two biologically distinct
   populations that happen to share marker expression. May need splitting
   or re-clustering at higher resolution.

The `continuity_diag.details[cluster]` dict has `left_cells` and
`right_cells` to distinguish these cases.

## CP3 spatial_mismatch — Leiden mis-fragmentation detection

When two clusters of the same cell_type are far apart in UMAP but have
high marker overlap (Jaccard > 0.3), this is over-fragmentation.

When two clusters of the same cell_type are far apart AND have LOW marker
overlap (Jaccard ≤ 0.3), this is likely a misannotation — one of them
has the wrong label.

The `_check_cell_type_separation` function computes:
- `max_distance`: UMAP distance between most distant same-type clusters
- `marker_jaccard`: average pairwise Jaccard of top markers
- `separated_types`: over-clustering entries (high Jaccard)
- `misannotated`: misannotation entries (low Jaccard)
