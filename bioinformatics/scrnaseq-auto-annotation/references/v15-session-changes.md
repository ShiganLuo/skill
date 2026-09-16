# v15 Session Changes (2026-09-14)

## Changes Applied

### 1. Step 0.5: PubMed Marker Verification
New function `_verify_tissue_markers(tissue_cell_types, tissue, n_sample=3)`.
Samples 3 markers per cell type, searches PubMed with `{gene} AND {cell_type}` (NO tissue).
Results written to `ctx["marker_verification"]` for audit trail.
Unverified markers are NOT dropped — flagged only.

### 2. PMID Pre-Check for Program-Confident Branch
In `_run_one_annotation_pass`, program_confident clusters (score>=1.5, margin>=0.3)
now search PubMed for 3 markers before setting confidence="high".
0 refs → confidence downgraded to "medium".
Catches hallucinated tissue_cell_types markers that match DEGs by coincidence.

### 3. rank_weight Coefficient
Changed from `rank * 0.1` to `rank * 0.05` in `_score_cluster_against_tissue_types`.
Flatter decay: rank 10 weight 0.67 (was 0.50), rank 30 weight 0.40 (was 0.25).

### 4. Orchestrator Structural Signals (corrected)
`_build_orchestrator_prompt` now receives `separation_diag` and builds:
- `ct_summary`: cell types with >1 cluster (informational, NOT a decision criterion)
- `sep_summary`: over-clustered types (Jaccard, max_distance) + misannotated candidates

**CRITICAL**: Structural check uses Jaccard/max_distance from separation_diag,
NOT cluster counting. "NO same cell_type in >2 clusters" was tried and rejected
by the user as "违背常识" (violates common sense). Same cell type in multiple
clusters is normal biological subtypes.

Action block (simplified, ~4 lines per action):
- accept: most clusters trust=high/medium AND no over_clustering AND no misannotated
- adjust_resolution: over_clustering Jaccard>0.3 OR many trust=low without alternatives
- correct_annotations: trust=low + alternative!=null, or synonym merging
- filter_and_recluster: should_drop=true or lq_pct>30

Rules block removed (too complex → LLM returns empty action). JSON schema
included directly in prompt. Keep prompt under ~4K tokens.

### 5. Orchestrator State Enrichment
`_collect_full_state` new param `basic_qc_reports`.
clusters_payload now includes: n_cells, mean_genes, mean_counts, pct_mt, qc_flags, score, n_matched.

### 6. te_dominated Logic Unified
`_compute_cluster_assessment` now uses same logic as `_analyze_cluster_quality`:
- low_quality/unknown → artifact
- te_dominated → artifact ONLY if lq_pct > 10%

### 7. Code Fixes
- mode_cluster duplicate code removed (markers/plot/write_h5ad executed twice)
- `_check_cell_type_separation` variable shadowing `j` → `jc`
- `_query_tissue_cell_types` pmids scope leak → `ct_pmids` dict

## Test Results (ovaries_scTE_merged.h5ad, 19816 cells)

### v1 (old orchestrator): 2 rounds, round 1 accept
- Smooth_muscle 4 clusters → no action
- Fibroblasts + Stromal overlap → no action

### v2 (new orchestrator): 3 rounds, progressive fix
- Round 1 (19 clusters, res=0.80): adjust_resolution → res=0.60
  Reason: Endothelial/Fibroblast/Granulosa/Smooth_muscle all 3+ clusters
- Round 2 (17 clusters, res=0.60): filter_and_recluster
  Reason: clusters with 70%+ low-quality cells (19816→16317 cells)
- Round 3 (15 clusters, res=0.60): accept
  Reason: structural issues resolved, remaining low-trust clusters have no alternatives

## LLM Config (Xiaomi MiniMax)
- Method: openai (OpenAI-compatible endpoint)
- Model: mimo-v2.5-pro
- Base URL: https://token-plan-cn.xiaomimimo.com/v1
- API key: from ~/.bashrc LLM_API_KEY

## v4 Test Results (simplified orchestrator prompt)

3 rounds, orchestrator correctly used Jaccard for structural decisions:
- Round 1 (19 clusters, res=0.80): adjust_resolution → res=0.80 (LLM didn't lower!)
  Reason: Smooth_muscle Jaccard=0.758, Stromal_fibroblast Jaccard=0.429
- Round 2 (19 clusters, res=0.80): adjust_resolution → res=0.60 (correctly lowered)
  Reason: Same over-clustering persisted
- Round 3 (17 clusters, res=0.60): adjust_resolution → wanted 0.40, max rounds forced accept

Key improvement: **Oocyte detected** (cluster 4, conf=medium, GDF9/FDX1 markers).
Previous runs missed Oocyte because LLM was overwhelmed by complex prompt.

Cell types found: Macrophage, Endothelial_cell×3, Smooth_muscle_cell×4,
Granulosa_cell, **Oocyte**, Stromal_fibroblast×3, Ovarian_surface_epithelium,
NK_cell, Unknown×2 (proliferating cluster).

### Remaining Issues
1. Round 1 LLM set resolution=0.80 (same) — wasted a round. Consider program-side
   enforcement: if separation_diag shows over_clustering, force resolution decrease.
2. Smooth_muscle Jaccard=0.758 persisted even at resolution=0.60 — 4 clusters
   didn't merge. May need even lower resolution or different batch correction.
3. PubMed NoneType bug: `_search_pubmed` crashes on some genes (TAGLN) with
   `'NoneType' object is not subscriptable`. Needs try/except in XML parsing.