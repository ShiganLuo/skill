# Orchestrator Prompt Design Lessons (2026-09-14)

## ❌ Cluster counting as structural check (violates biology)

WRONG prompt rule:
```
- NO same cell_type appears in >2 clusters (no over-clustering)
```

This violates biological common sense. Same cell type CAN appear in
multiple clusters legitimately:
- Proliferating vs quiescent Granulosa cells
- CD4+ vs CD8+ T cells
- Arterial vs venous Endothelial cells

The user's correction: "谁让你提这种违背常识的修改的"

CORRECT approach: use `_check_cell_type_separation` output:
- `separated_types[].marker_jaccard > 0.3` → over-fragmentation (same
  markers split across clusters → must merge via adjust_resolution)
- `misannotated[].marker_jaccard ≤ 0.3` → misannotation (different
  markers under same label → correct_annotations to rename)
- Same-type clusters with LOW Jaccard + SMALL max_distance = legitimate
  biological subtypes → accept

## ❌ Orchestrator prompt too complex → empty action

If the orchestrator prompt exceeds ~4K tokens, the LLM returns empty
`action` field, which `_parse_orchestrator_decision` defaults to "accept".

Symptom in log:
```
Orchestrator returned invalid action '' — defaulting to 'accept'.
CP decision: accept
CP reasoning:
```

Fix: keep prompt focused on:
1. Per-cluster trust/alternative/should_drop (compressed state)
2. Separation_diag summary (over_clustering + misannotated)
3. Cell type summary (how many clusters per type)
4. Short action descriptions (3-4 lines each)

Do NOT add long rule explanations — the LLM ignores them anyway.

### Working prompt structure (v4, tested)
```
You are the orchestrator of an scRNA-seq annotation pipeline.
Decide: accept, correct, filter, or recluster.

Round {round}/{max}.
{ct_summary}          # cell types with >1 cluster
{sep_summary}         # over_clustering + misannotated from separation_diag

## Available actions (choose EXACTLY ONE)
1. "accept" — short description
2. "correct_annotations" — short description
3. "filter_and_recluster" — short description
4. "adjust_resolution_and_recluster" — short description

Output ONLY valid JSON:
{"action": "...", "reasoning": "...", "filter_plan": {...}, "new_resolution": null, "annotation_corrections": {}}

## STATE
{state_json}
```

Total prompt ~2-3K tokens. No rules_block, no schema_block (schema is inline).

## ❌ Orchestrator may not lower resolution on first adjust_resolution

Even when the prompt says "Lower resolution by ~0.15-0.2", the LLM may return
the same resolution (e.g., 0.80→0.80). This wastes a round.

Possible fix (not yet implemented): program-side enforcement — if separation_diag
shows over_clustering, force `new_resolution = max(0.1, current - 0.2)` regardless
of what the LLM returns. Or: add current resolution to the prompt explicitly so
the LLM knows what to subtract from.

## ✅ Step 0.5 marker verification (new feature)

After `_query_tissue_cell_types` returns tissue_cell_types, run
`_verify_tissue_markers` to sample 3 markers per cell type against PubMed.

Purpose: catch LLM hallucinated markers (fabricated gene names).

Implementation: `_search_pubmed(gene, cell_type, tissue="", max_results=1)`
— note: do NOT include tissue in query (too specific, fails on real markers).

Results go into `ctx["marker_verification"]` for the audit report.
Markers are NOT dropped — only flagged.

## ✅ PMID pre-check for program-confident branches

Program-scored clusters (score ≥ 1.5, margin ≥ 0.3) used to skip PMID
verification entirely. Now they get an early PMID check:
- Search 3 markers against PubMed
- If 0 refs for non-skipped type → confidence downgraded from "high" to "medium"

This catches cases where Step 0 tissue_cell_types contains hallucinated
markers that happen to match the scoring algorithm.

## ✅ PubMed verification query fix

The query `{gene} AND {cell_type} AND {tissue}` is too specific.
Real example: `PECAM1 AND Endothelial_cell AND macaque (Macaca mulatta) ovaries`
→ 0 results on PubMed.

Fix: use `{gene} AND {cell_type}` (no tissue). This verifies the marker
exists for the cell type without over-constraining on tissue context.

Applied in `_verify_tissue_markers` and `_search_pubmed_for_markers`.

## ❌ Over-clustering = annotation error, NOT resolution error (2026-09-15)

The original action_block said:
```
4. "adjust_resolution_and_recluster" — merge over-fragmented clusters.
   Use when over_clustering Jaccard>0.3...
```

This is WRONG. When same cell_type appears in multiple distant clusters with
Jaccard > 0.3 (high marker overlap), the clusters are well-separated and
biologically distinct. They were mislabeled as the same type. The fix is
to relabel each cluster to its correct distinct cell_type, NOT to lower
resolution.

User correction: "不是recluster,因为聚类良好,优先correct_annotation,查找更多证据去支持"

Fix: rewrote action_block:
- Action 2 (correct_annotations): PREFERRED for over-clustering, with explicit
  steps to compare unique DEG markers and propose distinct types
- Action 4 (adjust_resolution): ONLY for true resolution problems (discontinuous
  clusters, too many tiny clusters), NOT for over-clustering

## ❌ CP returns empty annotation_corrections (2026-09-15)

The CP chooses `correct_annotations` action and describes corrections in its
`reasoning` text (e.g., "cluster 1 → Lymphatic_Endothelial, cluster 16 →
Proliferating"), but the `annotation_corrections` JSON field is empty `{}`.

Root cause: LLM generates good reasoning but doesn't structure the JSON
properly. The parsing code at `_parse_orchestrator_decision` only reads from
the structured JSON `annotation_corrections` field.

Fix:
1. Strengthened prompt: "When action=correct_annotations, annotation_corrections
   MUST be non-empty — one entry per cluster that needs relabeling"
2. Show explicit correction format in prompt JSON template
3. Programmatic `_auto_correct_overclustered()` as safety net when corrections empty

## ✅ Programmatic auto-correct for over-clustered types (2026-09-15)

New function `_auto_correct_overclustered()` runs as safety net after CP
decisions when over-clustered types remain:

- Computes UNIQUE markers per same-type cluster (not shared with siblings)
- Scores unique markers against tissue_cell_types reference
- If distinct cell_type scores > 0.3, reassigns cluster
- Falls back to LLM disambiguation with unique markers if no tissue match
- Uses `skip_clusters` to avoid overriding CP corrections

Called from three paths:
1. CP = correct_annotations + empty corrections → all over-clustered types
2. CP = correct_annotations + some corrections → only uncovered types
3. CP = accept + over-clustering exists → all over-clustered types

## ✅ rank_weight coefficient

Changed from `1.0 / (1.0 + rank * 0.1)` to `1.0 / (1.0 + rank * 0.05)`.

Old: rank 10 = 0.5 weight (too aggressive decay)
New: rank 10 = 0.67 weight (more gradual, mid-range markers contribute)

## ✅ QC metrics in orchestrator state

`_collect_full_state` now accepts `basic_qc_reports` parameter.
Each cluster in `clusters_payload` gets: n_cells, mean_genes, mean_counts,
pct_mt, qc_flags.

Previously `_basic_qc_check` was called but results were unused (dead code).

## ✅ te_dominated logic unified

`_compute_cluster_assessment` now uses the same logic as
`_analyze_cluster_quality`:
- low_quality / unknown → artifact (always)
- te_dominated → artifact ONLY if lq_pct > 10% (scTE data has real
  ERVK_high/Alu_high populations)

## LLM config for testing

User's .bashrc:
```
LLM_METHOD=openai
LLM_MODEL=mimo-v2.5-pro
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_API_KEY=tp-cuj3k2h83arneiuuuralxri5404enhkaxmn8ql1tekkkdso9
```

Must explicitly pass --llm-method, --llm-model, --llm-base-url, --llm-api-key
when running tests. Do NOT rely on env var inheritance (unreliable in
background processes).

## ✅ Step 2.5: Unknown cluster resolution (2026-09-15)

After annotation pass, Unknown clusters scored against tissue_cell_types.
If best score > 1.5 and >= 3 matched markers → reassign.

## ✅ Step 0 caching for cross-run stability (2026-09-15)

tissue_cell_types cached to `{output_dir}/tissue_markers_{sanitized_query}.json`.
Loaded on subsequent runs instead of re-querying LLM.

Key: cache is in output_dir (shared across all runs in same directory),
NOT in report_dir (per-run).

## ❌ LLM non-determinism across runs (2026-09-15)

Same prompt + same model + same API → different results every run.
Step 0 tissue_cell_types: 24→20→14→14→0→21→41→21 across 8 runs.
Even with same cache, CP orchestrator makes different corrections
(v9: 7 corrections, v9c same cache: 16 corrections).

Root cause: LLM temperature=0.1 is not fully deterministic.
Mitigation: Step 0 caching eliminates one source. CP non-determinism
remains unresolved.

## ❌ CP overrides program-confidence annotations (2026-09-15)

Program scoring confidence=high clusters can still be overridden by CP.
Example: CP changed Granulosa_Cell to Theca_Cell despite program
confidence=high with score=3.88 and 5 matched markers.

Fix needed: pass program_confident set to _apply_orchestrator_decision
and reject corrections for those clusters.
