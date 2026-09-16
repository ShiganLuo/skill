# Whole-Cluster Filter for Ambient-RNA Artifacts

## When to use whole_cluster_removal

A cluster should be whole-cluster removed when ALL of:
1. `should_drop=true` (quality_flag is low_quality/te_dominated/unknown AND trust=low)
2. The cluster is spatially isolated from same-type high-quality clusters
3. Even cells that pass per-cell QC would contaminate downstream analysis

The 70% threshold is empirical: clusters with 30-50% bad cells usually
still contain real biology. Better to keep the real cells than discard
the whole cluster.

## Implementation

`_apply_filter_plan_to_raw` handles both modes:
- `whole_cluster_removals`: drop ALL cells in those leiden clusters
- `cell_level_clusters`: keep only cells passing QC thresholds

## Precision matters

Over-aggressive whole_cluster_removal discards real biology. Under-
aggressive removal leaves ambient-RNA artifacts. The orchestrator sees
`low_quality_cell_pct` per cluster and decides.

## Testing without burning LLM quota

Run clustering + sensors without LLM calls to check structural signals:
```python
# In a Python script, call _run_one_clustering_iteration + sensors
# without the annotation/orchestrator loop
```
