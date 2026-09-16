# Architecture Evolution: v3 → v12 → v13

## Why single CP, not three (v12 replaces v3)

The three-checkpoint design (CP1=QC, CP2=annotation, CP3=spatial) was
replaced because:
- Each CP is an LLM call → 3× cost per round
- CP1 and CP2 often gave conflicting signals
- The LLM at CP3 had to reconcile decisions from CP1+CP2 without seeing
  the raw state that led to those decisions

The single-CP design puts ALL state in ONE prompt and lets the LLM
decide holistically. The program computes trust/alternative/should_drop
per cluster (sensor), the LLM picks the action (policy).

## What changed from v3 to v12

- Removed CP1 (QC checkpoint) → `_basic_qc_check` is now a pure sensor
  (reports flags but never auto-decides `should_filter`)
- Removed CP2 (annotation checkpoint) → merged into single CP
- Removed CP3 (spatial checkpoint) → spatial signals pre-computed by
  program and included in single CP state
- Removed Step 2.5 (programmatic override of LLM annotations)
- Removed enforced_merges (Step 3.25/3.5)
- Added boundary sharpness detection (k-NN + cell-to-cell proximity)
- Added isolation detection (orphan Leiden clusters)

## Decision handlers and shared helpers (v13)

Shared helpers (mode_auto uses, not duplicated):
- `_apply_annotation_corrections` — relabel cell_type in adata.obs + annotations dict
- `_apply_filter_plan_to_raw` — drop cells from raw_adata (whole_cluster or cell-level)
- `_apply_orchestrator_decision` — dispatches to the above based on action

These are called from the single CP path in mode_auto.

## Route block readability (rule learned v12)

The orchestrator prompt has a "route block" that describes available
actions. Keep it SHORT — if the prompt exceeds ~4K tokens, the LLM
returns empty action (parsing failure). See pitfalls section.

## Boundary sharpness detection

`_compute_boundary_sharpness` detects two signals:
1. Per-cluster k-NN composition (own vs invading fractions)
2. Inter-cluster cell-to-cell proximity (p25 distance)

Used by the orchestrator to identify fuzzy boundaries and isolated clusters.

## Isolation detection for orphan Leiden clusters

`_compute_boundary_sharpness` also identifies isolated clusters whose
cells sit far from any other cluster (isolation_median > threshold).
These are likely Leiden noise / doublets and should usually be
whole_cluster_removal.
