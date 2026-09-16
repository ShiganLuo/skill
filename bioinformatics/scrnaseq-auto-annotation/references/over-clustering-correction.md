# Over-clustering Correction — Auto-correct Algorithm

## Problem

When `_check_cell_type_separation` detects over-clustering (same cell_type in
multiple distant clusters, marker Jaccard > 0.3), the orchestrator CP may:
1. Dismiss it as "biological heterogeneity" → choose accept
2. Choose correct_annotations but return empty `annotation_corrections`
3. Choose adjust_resolution_and_recluster (wrong — clustering is fine, annotation is wrong)

All three leave the over-clustering unresolved in the final result.

## Solution: `_auto_correct_overclustered()`

Programmatic safety net that runs after CP decisions when over-clustered
types remain. Called from two paths:

1. **CP = correct_annotations + empty corrections**: runs for ALL over-clustered types
2. **CP = correct_annotations + some corrections**: runs for types NOT covered by CP
   (uses `skip_clusters` parameter to avoid overriding CP decisions)
3. **CP = accept + over-clustering exists**: runs for ALL over-clustered types

## Algorithm (v2 — 2026-09-15 rewrite)

Previous version used UNIQUE markers (not shared with siblings) for scoring.
This caused overcorrection: all clusters in a group got reassigned to the
same new type (e.g., 4 Smooth_muscle_cells → all Pericytes).

New version uses FULL markers with strict thresholds and UMAP distance check:

```
for each over-clustered cell_type (from separation_diag.separated_types):
    1. Find current clusters sharing this cell_type
    2. Skip clusters in skip_clusters set (CP already addressed)
    3. Pre-compute UMAP centroids for all clusters (distance check)

    for each cluster NOT in skip_clusters:
        4. Get FULL key_markers from annotations dict (not just unique)
        5. Score FULL markers against tissue_cell_types via
           _score_cluster_against_tissue_types()
        6. Find current_type score and best alternative type score

        STRICT conditions for reassignment (ALL must hold):
        a. new_type score > current_type score + 0.5  (significant improvement)
        b. new_type score > 1.0                        (absolute threshold)
        c. new_type has >= 3 matched markers            (not noise)

        7. UMAP distance check: if cluster is CLOSE (dist < 3.0) to any
           sibling cluster of the same type → same biological population,
           DON'T reassign even if markers suggest otherwise

        8. If all conditions met: reassign cluster
        9. If not met: keep current type (conservative)
```

Key differences from v1:
- **Full markers** instead of unique markers → more accurate scoring
- **Score gap > 0.5** instead of absolute score > 0.3 → fewer false positives
- **UMAP distance check** → prevents reassigning spatially close clusters
- **No LLM fallback** → removed to prevent additional non-determinism
- **>= 3 matched markers** → prevents noise-driven reassignments

## Known Issues

### CP non-determinism
Even with the same tissue_cell_types cache, the orchestrator LLM makes
different correction decisions between runs. The auto-correct safety net
helps but doesn't fully solve instability.

### Program-confidence protection needed
Program scoring confidence=high clusters should NOT be modifiable by the CP.
Currently the CP can override any annotation regardless of program confidence.
This is a remaining design gap.

## Log signatures

```
# Auto-correct triggered (CP empty corrections):
CP chose correct_annotations but provided 0 corrections — running programmatic auto-correct

# Auto-correct triggered (CP accept + over-clustering):
CP accepted but N over-clustered types remain — forcing programmatic correction

# Per-cluster (v2 — full markers):
[auto-correct] Smooth_muscle_cells: 4 clusters (Jaccard=0.633, max_dist=10.08) — scoring full markers against tissue reference...
  Cluster 2: current='Smooth_muscle_cells'(2.50) best_alt='Pericytes'(1.20, 3 matched)
  Cluster 2: keeping 'Smooth_muscle_cells' (alt score not high enough)

# Reassignment:
  Cluster 2: current='Smooth_muscle_cells'(1.20) best_alt='Theca_Cell'(2.80, 5 matched)
  [auto-correct] Cluster 2: 'Smooth_muscle_cells' -> 'Theca_Cell' (score 2.80 vs 1.20, 5 matched)

# UMAP distance check:
  Cluster 2: close to sibling 4 (dist=1.85) — same population, keeping 'Smooth_muscle_cells'

# Skipped (CP already addressed):
  Cluster 6: skipped (CP already addressed)

# All resolved:
  [auto-correct] All over-clustered types already resolved.
```

## Diagnostic commands

```bash
# Check if auto-correct ran
grep "auto-correct" run.log

# Check what was corrected
grep "\[auto-correct\].*->" run.log

# Check what was skipped
grep "skipped.*CP already" run.log

# Check UMAP distance skips
grep "close to sibling" run.log

# Check over-clustering detection
grep "over-clustering" run.log
```
