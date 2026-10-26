# v15 Optimization Round (2026-09-14)

## Context
Code review of `scRNAseq.py` (4257 lines) identified 3 bugs and 5 optimization
opportunities in the auto-mode annotation pipeline.

## Bugs Fixed

### 1. mode_cluster duplicate code (lines 679-688)
markers TSV write, plot, and write_h5ad were duplicated -- each executed twice.
**Fix**: removed the duplicate block.

### 2. Variable shadowing in _check_cell_type_separation (line 1820)
Loop variable `j` (inner loop index) was overwritten by Jaccard value.
**Fix**: renamed to `jc`.

### 3. pmids scope leak in _query_tissue_cell_types (line 1157)
Report loop used `pmids` from last iteration of the parsing loop. When last
cell_type was list-format (pmids={}), all types showed 0 unverified.
**Fix**: added `ct_pmids` dict, report loop uses `ct_pmids.get(ct, {})`.

## Optimizations

### P1: Step 0 marker verification (`_verify_tissue_markers`)
- Samples 3 markers per cell type, searches PubMed
- Catches hallucinated markers from Step 0 LLM query
- Results written to `ctx["marker_verification"]` for audit trail
- Does NOT block pipeline -- flags only
- Called in mode_auto after `_query_tissue_cell_types`

### P2: PMID pre-check for program_confident branch
- Previously: program_confident -> confidence="high" unconditionally
- Now: search PubMed for 3 markers, 0 refs -> confidence="medium"
- Catches cases where Step 0 hallucinated markers match DEGs by coincidence
- Located in `_run_one_annotation_pass`, inside `if program_confident:` block

### P3: rank_weight coefficient 0.1 -> 0.05
- In `_score_cluster_against_tissue_types`
- Flatter decay: rank 10 now 0.67 (was 0.50), rank 30 now 0.40 (was 0.25)
- Reduces dominance of top-2 DEGs in score calculation

### P4: Orchestrator state information increase
- `top_markers`: 5 -> 10 (in `_collect_full_state` clusters_payload)
- Added `score` and `n_matched` fields from annotation dict
- Orchestrator can now see program scoring strength per cluster

### P5: Disambiguation prompt full marker list
- In `_build_disambiguation_prompt`, added "Canonical markers per type" section
- LLM now sees complete `tissue_cell_types` marker list, not just top-3 candidates' matched markers
- Enables more informed disambiguation decisions

## Design Decisions

### Why not revert to per-cluster LLM search?
Old approach: every cluster -> LLM sees DEGs -> LLM searches + cites PMIDs.
Current approach: program scores first -> LLM only for ambiguous -> PMID gate for all.

Current is more reliable because:
- Program scoring cannot hallucinate (set intersection + weighted sum)
- PubMed verification catches LLM errors post-hoc
- LLM disambiguation task is more focused (pick from 3 candidates vs free annotation)
- 80-90% fewer LLM calls per round

### Where the real risk is
The entire pipeline depends on Step 0 `tissue_cell_types` quality. If that list
has hallucinated markers, the program scoring denominator is wrong. P1 (verification)
and P2 (PMID pre-check) are the two defenses against this.

## QC Data Flow Fixes

### Q1: basic_qc_reports integrated into orchestrator state
**Problem**: `_basic_qc_check` was called in mode_auto but its output
(`basic_qc_reports`) was never passed anywhere -- pure dead code.
Meanwhile, the orchestrator only saw `low_quality_cell_pct` (a single
percentage) and `should_drop` (a bool), with no raw QC metrics.

**Fix**:
- `_collect_full_state` now accepts `basic_qc_reports` parameter
- Builds `basic_qc_lookup` dict (cluster -> QC metrics)
- Each cluster in `clusters_payload` now includes:
  `n_cells`, `mean_genes`, `mean_counts`, `pct_mt`, `qc_flags`
- mode_auto passes `basic_qc_reports` to `_collect_full_state`

### Q2: te_dominated quality_flag logic unified
**Problem**: Two different functions judged `te_dominated` differently:
- `_analyze_cluster_quality`: te_dominated only flagged when combined
  with other QC issues (low_genes, low_counts, high_mt)
- `_compute_cluster_assessment`: te_dominated directly counted as
  artifact -> should_drop

scTE data has real ERVK_high/Alu_high populations, so te_dominated
alone should NOT trigger artifact classification.

**Fix**: `_compute_cluster_assessment` now uses the same logic:
- `low_quality` / `unknown` -> artifact (always)
- `te_dominated` -> artifact ONLY when `lq_pct > 10%` (non-trivial
  fraction of cells failing QC)
- This aligns with `_analyze_cluster_quality`'s approach of requiring
  QC issues alongside te_dominated
