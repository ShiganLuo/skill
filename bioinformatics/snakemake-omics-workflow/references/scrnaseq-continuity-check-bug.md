# scRNAseq Auto Mode: Spatial Continuity Check Bug (2026-09)

## The Bug

`_check_cluster_continuity()` in `scRNAseq.py` was placed AFTER the early exit for
"no flagged clusters". When all clusters passed quality analysis (0 flagged), the code
hit:

```python
if not flagged:
    logging.info("All clusters clean. Saving final results.")
    break  # ← exits BEFORE continuity check
```

This meant spatially discontinuous clusters were NEVER detected on clean runs.

## Real Impact

Cluster 18 (Oocyte, 437 cells) had `max_gap=4.254` on UMAP1 — well above the 2.0
threshold — but was never flagged because no quality issues existed. The cluster had
4 disconnected fragments scattered across UMAP space.

Cluster 15 (Theca_Stromal_Cells) had `max_gap=1.728` — borderline, below threshold.

## The Fix

Moved `_check_cluster_continuity()` (Step 3.5) to BEFORE the early exit. New flow:

```
Step 3:    Quality analysis → flagged clusters
Step 3.25: Merge flags from LLM
Step 3.5:  Spatial continuity check ← NOW RUNS ALWAYS
           ├─ discontinuity + no quality flagged → increase resolution → continue
           ├─ discontinuity + quality flagged → defer, filter first
           └─ no discontinuity → continue to early exit
Early exit: if not flagged → break
Step 3.75: Cell type separation check
Step 4:    Filter or finish
```

Key change: when discontinuity is detected without quality-flagged clusters, the code
directly increases resolution (×1.5, max 1.5) and re-clusters, regardless of iteration
number. The old code had `iteration == 1` protection that deferred to QC filter — but
when there are no QC issues, deferral just means the problem is never fixed.

## Investigation Methodology (Lesson Learned)

**WRONG approach (what happened):**
1. Looked at function default params (`n_neighbors=15` in cluster_annotate.py) instead
   of actual run script params (`--n-neighbors 50` in v7 .sh)
2. Jumped to "n_pcs=15 is too low" without checking PCA variance ratio plot
3. Kept suggesting marker expression checks when user said "是聚类问题"

**RIGHT approach:**
1. ALWAYS read the actual run script first — function defaults ≠ runtime params
2. Check diagnostic plots (PCA variance, UMAP) before making parameter claims
3. When user says "it's a clustering problem", investigate clustering — don't deflect
   to annotation/markers
4. Use `_check_cluster_continuity` logic programmatically to detect discontinuity:
   ```python
   for dim in range(2):
       sorted_coord = np.sort(cluster_umap[:, dim])
       gaps = np.diff(sorted_coord)
       max_gap = float(gaps[np.argmax(gaps)])
       if max_gap > 2.0:
           print(f"DISCONTINUOUS: max_gap={max_gap:.2f}")
   ```
5. Also check neighbor graph connected components:
   ```python
   from scipy.sparse import csgraph
   sub_conn = conn[np.ix_(idx, idx)]
   n_comp, _ = csgraph.connected_components(sub_conn, directed=False)
   ```

## Neighbor Graph vs UMAP Disconnect

Both cluster 15 and 18 showed 1 connected component in the neighbor graph despite
being spatially fragmented in UMAP. This is because n_neighbors=50 creates enough
connections to bridge distant cells in high-dimensional space, but UMAP projection
reveals the spatial discontinuity. The continuity check operates on UMAP coordinates
(not the graph), which is the correct level for detecting visual fragmentation.
