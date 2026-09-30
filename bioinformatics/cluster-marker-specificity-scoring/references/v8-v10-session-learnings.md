# v8→v10 Session Learnings (2026-09-18)

## Continuity Check Placement Bug

`_check_cluster_continuity()` was at Step 3.6, AFTER early exit.
When 0 quality-flagged clusters → break → continuity check never runs.
Cluster 18 (Oocyte, max_gap=4.25) was never detected.

**Fix**: Move to Step 3.5, BEFORE early exit.

## min_side_pct Filter

After moving check, 10 clusters flagged as discontinuous.
Most had 1-7 outlier cells (e.g., Cluster 5: 1849+1 cells).

```
Cluster 5:  1849+1 cells  → 1 outlier triggers false positive
Cluster 18: 67+370 cells  → truly discontinuous
```

**Fix**: `min_side_pct=0.05` — gap sides must each have >= 5% of cluster cells.

## LLM JSON Retry

`_call_anthropic()` had no retry. JSON parse failures returned `{}`.
Step 0 querying 0 cell types → pipeline cascades failure.

**Fix**: `max_retries=3` with exponential backoff on `json.JSONDecodeError`.

## Step 0 Prompt — Transitional Types

Queried 40 types but missed Myofibroblast. Cluster 4 had dual SMC+stromal
markers (IGFBP5 highest in dataset, SFRP1 91% vs 10% in SMC clusters).

**Fix**: Added transitional/activated/mixed-phenotype requirement to prompt.
Result: 40 → 50+ cell types.

## Marker Visualization

Changed from per-cluster top-3 to per-cell-type ALL markers with UMAP
cluster reference as last subplot. Allows direct comparison of marker
expression against cluster boundaries.

## LLM Non-Determinism

Same prompt + same data → different results across runs.
Production run (20:13) got Cycling_Granulosa_Cell instead of Oocyte
despite specificity-first prompt.

Data-driven generic DEG detection (avg_spec < 1.5) is the most robust
mitigation because it operates at the data level, not prompt compliance.