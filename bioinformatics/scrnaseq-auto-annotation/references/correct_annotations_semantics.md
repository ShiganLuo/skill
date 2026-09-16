---
topic: "correct_annotations semantics — what 'relabel' actually does (and what it does NOT do)"
audience: any future session that needs to explain the LLM's annotation corrections to the user
created: 2026-09-14
session_origin: "ovaries_scTE v11→v12 auto-mode audit; user pushed back on '合并' wording"
---

# correct_annotations Semantics — Lesson From v12 Refactor

## TL;DR

`annotation_corrections` does **NOT** merge clusters. It rewrites the
`cell_type` STRING column of `adata.obs` for each cluster's cells.
Leiden cluster IDs (`adata.obs.leiden`) are **unchanged**. The function is
relabeling, not merging.

## Why this matters

Future sessions will explain the auto-mode orchestrator's actions to the
user. The word "merge" is tempting because many cells in the user's head
logically belong to one biological type and the CP is "putting them
together." But the data layer doesn't merge — the leiden ID stays, the
UMAP position stays, the X_pca stays. Only one categorical column changes.

If a future session says "the CP merged cluster 5 into cluster 3," the user
will look at the h5ad and see leiden=5 still exists with its own cells,
and will (rightly) call this out as wrong.

## What actually changes when the CP issues `correct_annotations`

For each `{cluster_id: {new_cell_type, reasoning}}`:

| Layer | Before | After |
|---|---|---|
| `annotations[cl]["cell_type"]` | LLM's first-pass label | new_cell_type |
| `adata.obs.loc[adata.obs.leiden == cl, "cell_type"]` | first-pass label | new_cell_type |
| `adata.obs.leiden` | "5" | "5" (unchanged) |
| `adata.obsm["X_umap"]` | original coords | original coords |
| `adata.obsm["X_pca"]` | original coords | original coords |
| `adata.uns["rank_genes_groups"]` | original DEG table | original DEG table |

Downstream tools that key on `leiden` (any `sc.tl.*` calls, UMAP
re-plotting, per-cluster DEG re-runs) will still treat cluster 5 as
its own thing. Only downstream tools that key on `cell_type` (composition
analysis, cell-type colored UMAP, type-keyed DEG) will see the merge.

## How to physically merge clusters (real merge)

If the user actually wants cluster 5's cells to be absorbed into cluster 3
in the data — not just relabeled — the only mechanism in the pipeline is
`adjust_resolution_and_recluster`: re-runs Leiden+Harmony+annotation with
a lower resolution, which lets the algorithm itself produce fewer
clusters. The cells of C5 then naturally end up in a single new cluster
along with C3's cells (or in C3 itself if the algorithm happens to assign
that label). The trade-off: minutes-to-tens-of-minutes of compute vs. a
free string rewrite.

## History (why this was confusing)

In v3 (three-checkpoint architecture), the per-cluster LLM at Step 2 was
instructed to set `is_subcluster=True, parent_cluster=3, should_merge=True`
when it suspected over-clustering. The `should_merge` field was then used
by the orchestrator to construct `annotation_corrections` with
`merge_to_cluster=3`. The v3 code at the apply step adopted the parent
cluster's cell_type for the subcluster — semantically the same as just
writing the parent's name as `new_cell_type`. The `merge_to_cluster`
field was redundant with `new_cell_type` and was removed in v12.

The word "merge" leaked into user-facing explanations and was
misleading. Future explanations should say "relabel" or "adopt the
parent's label" — never "merge" — unless the user explicitly asks about
re-resolution.

## User pushback pattern

When a user says "你说的 X 听起来很奇怪" (X sounds weird) or "其实在
合并什么?" (what are you actually merging?), the right response is:

1. **Stop and re-read the apply code** (e.g. `_apply_annotation_corrections`)
2. State exactly which fields/columns are written vs. untouched
3. Use the operation's actual name (relabel, not merge) going forward

Do not defend the original wording. The user is reporting that your
mental model diverged from theirs, and they are right to push back.
