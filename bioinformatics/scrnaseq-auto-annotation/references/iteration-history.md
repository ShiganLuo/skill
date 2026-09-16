# v7 → v14 Iteration History

## The progression

- v7: three checkpoints (CP1/QC, CP2/annotation, CP3/spatial)
- v8-v10: bug fixes in filter logic
- v11: boundary sharpness detection added
- v12: single CP design (replaces three checkpoints)
- v13: shared helpers, PMID gate for all clusters
- v14: orchestrator uses Jaccard/max_distance (not cluster counting),
  Step 0.5 marker verification, PMID pre-check for program branches

## Key lesson: each iteration revealed a new failure mode

- v7: CP1 and CP2 gave conflicting signals → merged into single CP
- v8: `correct_annotations` with `whole_cluster_removals` didn't actually
  filter cells → fixed in `_apply_filter_plan_to_raw`
- v9: `continue` in Step 3.6 skipped Step 4 `break` → clusters never filtered
- v10: `iteration == max_iterations → prefer accept` overpowered Leiden-fix
  signals → changed to forced accept only at hard ceiling
- v11: Tiny cluster carved out of large cluster by Leiden → boundary
  sharpness detection added
- v12: Three CPs too expensive and conflicting → single CP
- v13: Program-confident branches skipped PMID check → PMID pre-check added
- v14: Orchestrator used cluster counting (violates biology) → Jaccard-based
  structural check; PubMed query too specific → removed tissue from query

## CP2 filter bug — `correct_annotations` with filter_plan

In v8, `_apply_orchestrator_decision` for `correct_annotations` also
applied the filter_plan, which dropped cells from raw_adata. This was
wrong — `correct_annotations` should only relabel, not filter.

Fixed in v13: `_apply_orchestrator_decision` only applies
`annotation_corrections`; filter happens in `filter_and_recluster` path.

## CP2 `correct_annotations` with `whole_cluster_removals`

In v9, the orchestrator could send `correct_annotations` with a
`filter_plan.whole_cluster_removals` field. The code applied BOTH the
corrections AND the filter, which was confusing. Fixed to only apply
corrections in the `correct_annotations` path.
