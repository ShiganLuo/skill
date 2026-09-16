---
name: scrnaseq-auto-annotation
description: Use when running scRNAseq.py auto mode for LLM annotation.
tags: [bioinformatics, scrnaseq, annotation, llm, single-cell]
version: "2.0"
author: hermes
license: MIT
metadata:
  hermes:
    tags: [bioinformatics, scrnaseq, annotation, llm, single-cell]
    related_skills: [snakemake-module-config, snakemake-omics-workflow]
---

# scRNAseq Auto Mode Annotation

## When to Use
- Running `scRNAseq.py --mode auto` for automated cell type annotation
- Improving annotation accuracy with species-specific markers
- Adding new parameters to the scanpy Snakemake module
- Debugging LLM-based annotation workflows

## Purpose
Automated cell type annotation for single-cell RNA-seq data using LLM + PubMed verification.
No manual marker dictionaries required — fully automated. **GENERAL-PURPOSE** — no tissue-specific hardcoding.

## Architecture

**Currently deployed**: commit `bed1b16` (simple LLM-annotation loop + species + skip_te).
**Latest code on main**: v14 orchestrator design (not in use — user reverted).

**Why `bed1b16` over `f6d3415`**: `f6d3415` lacks `--species` and `--skip-te`.
Without species, LLM gives generic annotations (no tissue-specific types like
Theca_cell, Ovarian_surface_epithelium). Without skip_te, TE genes dominate
DEG → Alu_high clusters, 429 rate limiting cascades Unknowns.

Simple loop (`bed1b16`):
```
Step 0: Query tissue-specific cell types from LLM (species-aware, once per run)
while iteration < max_iterations:
    Step 1: Cluster (Leiden, harmony batch correction)
    Step 2: AI annotate each cluster (LLM primary)
    Step 3: Quality analysis (QC + separation + continuity)
    Step 4: Filter flagged clusters or finish
```

v14 orchestrator (on main, not deployed):
- Program = sensor + executor (clustering, annotation, QC, state collection)
- LLM = sole decision-maker (sees complete state, picks action)
- PMID gate = constraint that exposes LLM hallucinations

```
Step 0: Query tissue-specific cell types from LLM (species-aware, once per run)
    ⚠️ CRITICAL DEPENDENCY: if this returns empty, ALL downstream scoring = 0
    📦 Cached to {output_dir}/tissue_markers_{query}.json for cross-run stability
Step 0.5: Verify tissue markers against PubMed (sample 3 per type)
    ↓
while round < max_recluster_rounds:
    Step 1: Cluster (Leiden, harmony batch correction)
    Step 2: AI annotate (program score → LLM disambiguate → PMID gate)
    Step 2.5: Resolve Unknown clusters against tissue reference (score>1.5, ≥3 matched)
    Sensors: QC + separation + boundary sharpness + continuity + spatial mismatch
    CP: SINGLE orchestrator checkpoint → accept / correct / filter / adjust_resolution
        + auto-correct safety net for over-clustered types
```

See `references/architecture-evolution.md` for v3→v14 history.

## Key Parameters

| Param | Default | Notes |
|-------|---------|-------|
| `--resolution` | 1.0 | Leiden resolution (scanpy default). NO recommended range — adjust per biological context. |
| `--n-pcs` | 50 | PCA components (ignored when auto_n_pcs=True) |
| `--auto-n-pcs` | True | Auto-detect n_pcs via relative change + stability (v2, fixed 2026-09-15). Use `--no-auto-n-pcs` to disable. |
| `--n-neighbors` | 50 | k-NN neighbors |
| `--n-top-genes` | 3000 | HVGs |
| `--batch-method` | harmony | harmony/bbknn/"" |
| `--skip-te` | False | Exclude TE from DEG |
| `--species` | (none) | Genome build for species mapping (e.g. Mmul_10, GRCh38, GRCm39) |
| `--max-iterations` | 3 | Hard ceiling on QC loops (bed1b16 uses `--max-iterations`, main uses `--max-recluster-rounds`) |
| `--min-genes` | 200 | QC: min genes per cell |
| `--min-counts` | 3000 | QC: min UMI per cell |
| `--max-pct-mt` | 20 | QC: max MT% |
| `--llm-method` | (required) | openai/anthropic/ollama — NOT read from env vars |
| `--llm-model` | (required) | Model identifier — NOT read from env vars |
| `--llm-base-url` | (required) | API endpoint — NOT read from env vars |
| `--llm-api-key` | (required) | API key — NOT read from env vars |

## Species Mapping

```python
species_map = {"Mmul_10": "macaque (Macaca mulatta)", "GRCh38": "human", "GRCm39": "mouse"}
```

Passed as `--species Mmul_10` → LLM gets "macaque (Macaca mulatta) ovaries".

## Annotation Flow (per cluster)

1. Fetch top 50 DEG from `rank_genes_groups`
2. Program scores against tissue_cell_types (specificity-weighted)
3. Three regimes:
   - score ≥ 1.5 + margin ≥ 0.3 → program decides, PMID pre-check
   - 0.5 ≤ score < 1.5 → LLM disambiguate (top-3 candidates)
   - score < 0.5 → LLM free annotation
4. PMID gate: search PubMed for cell_type + markers, 0 refs → confidence=low
5. Name normalization against tissue_cell_types

## Orchestrator Decision Logic

The orchestrator sees per-cluster: cell_type, top_markers (10), trust,
alternative, should_drop, low_quality_cell_pct, score, n_matched, plus
QC metrics (n_cells, mean_genes, mean_counts, pct_mt, qc_flags).

**Structural check uses separation_diag metrics, NOT cluster counting:**
- `separated_types[].marker_jaccard > 0.3` → **annotation error** → correct_annotations
- `misannotated[].marker_jaccard ≤ 0.3` → misannotation → correct_annotations
- Same-type clusters with LOW Jaccard = legitimate biological subtypes → accept

**Over-clustering (Jaccard > 0.3) = annotation error, NOT resolution error:**
When same cell_type appears in multiple distant clusters with high marker
overlap (Jaccard > 0.3), the clusters are well-separated and biologically
distinct — they were mislabeled as the same type. The fix is to relabel
each cluster to its correct distinct cell_type (correct_annotations), NOT
to lower resolution (adjust_resolution). Clustering is fine; annotation
is wrong.

**Programmatic auto-correct (safety net) — v2 (2026-09-15 rewrite):**
If CP returns `correct_annotations` but `annotation_corrections` is empty,
OR if CP `accept`s while over-clustered types remain, `_auto_correct_overclustered()`
runs automatically:
1. Scores each cluster's FULL key_markers against tissue_cell_types (not unique)
2. Requires: new_score > current_score + 0.5 AND new_score > 1.0 AND >= 3 matched
3. UMAP distance check: cluster close (dist<3.0) to sibling → same population, keep
4. No LLM fallback (removed to reduce non-determinism)
5. Respects `skip_clusters` — won't override clusters the CP already corrected

See `references/over-clustering-correction.md` for full algorithm.

## Quality Flags

| Flag | Meaning |
|------|---------|
| `low_quality` | mean_genes<800 or mean_counts<3000 or MT%>20 |
| `unannotated` | Top markers are ENSMMUG |
| `ribosomal` | Top markers are RPS/RPL |
| `te_dominated` | Top markers are TE elements (only flagged with other QC issues) |
| `unknown` | Cannot determine cell type |

te_dominated alone does NOT trigger filtering — scTE data has real
ERVK_high/Alu_high populations.

## Pitfalls

### ❌ Cluster counting as structural check (violates biology)
Same cell type in multiple clusters is NORMAL (proliferating vs quiescent
subtypes, CD4+ vs CD8+ T cells). Use Jaccard/max_distance from
separation_diag, not simple cluster count.

### ❌ Orchestrator prompt too complex → empty action
If prompt exceeds ~4K tokens, LLM returns empty `action` → defaults to
"accept". Keep prompt focused on compressed state + short action descriptions.

### ❌ PubMed query too specific
`{gene} AND {cell_type} AND {tissue}` fails on real markers.
Use `{gene} AND {cell_type}` (no tissue) for verification queries.

### ❌ resolution=0.4 too low for subtypes
Granulosa subtypes (cumulus, mural) merge at low resolution.
Default is 1.0 (scanpy default). NO recommended range exists —
user explicitly stated "我从来没有推荐范围". Adjust based on
biological context and user direction.

### ✅ auto-n-pcs detection fixed (v2, 2026-09-15)
`detect_n_pcs` rewritten: absolute delta → relative change rate + stability.
Default is now `auto_n_pcs=True` (was False).

**mode_auto detect_diag fix (2026-09-15)**:
`mode_auto()` had two bugs:
1. Discarded detect_diag with `_` instead of saving it
2. Never called `plotter.plot_pca_variance()`
Both fixed. Any mode calling `detect_n_pcs()` MUST save diagnostics and pass to plot.

**Old algorithm** (broken): `abs(diff(vr))` with `baseline * 0.15` threshold.
The baseline was dominated by high-variance early PCs (PC1→2 delta=0.0065
vs PC10→11 delta=0.0007), so threshold was too high → triggered at PC 10-14
when there's still significant variance at PC 20-30.

**New algorithm** (方案C): `abs(diff(vr) / vr[:-1])` (relative change).
This is scale-independent — PC1→2 drops ~18%, PC20→21 drops ~6%, both
are meaningful but absolute delta hides the latter.

Detection criteria (BOTH must hold for a window):
- `median(rel_change) < 0.05` (5% per PC — already flat)
- `std(rel_change) < 0.03` (stable — no longer fluctuating)
- `require_n=2` consecutive windows (prevents one-off outlier hits)

Uses median (not mean) for robustness — a single outlier PC with 0.6%
relative change was pulling the mean below threshold at PC14.

**Results**: ovaries 11→23, uterus 10→23.

See `references/scte-auto-npcs-fix.md` for full analysis with data.

### ❌ No species → generic markers
Always pass `--species` for tissue-specific annotation.

### ❌ Step 0 returns empty → entire pipeline cascades failure
**THE most critical failure mode.** If `_query_tissue_cell_types()` returns `{}`
(0 cell types), every downstream step fails silently:
1. `_score_cluster_against_tissue_types({})` → all scores = 0.0
2. No cluster reaches "program_confident" (needs score ≥ 1.5)
3. ALL clusters fall into LLM disambiguation with no tissue reference
4. LLM guesses freely → unstable results between runs
5. Orchestrator sees all-low trust → wastes rounds on adjust/filter loops
6. Name normalization is a no-op (no reference names to normalize against)

**Root causes** (from macaque ovary run, 2026-09-15):
- LLM_MODEL env var empty → `_call_openai` falls back to `"gpt-4o"` →
  Xiaomi API returns 400 "Unsupported model gpt-4o" → `_call_openai`
  catches exception, returns `{}` → `_query_tissue_cell_types` gets
  empty dict with no "cell_types" key → `raw.get("cell_types", {})` = `{}`
- Even when model IS set correctly, LLM response is non-deterministic:
  same prompt returned 24→20→14→14→0 cell types across 5 runs
- Prompt demands "ALL cell types + PMID per marker" → heavy for some models

**Detection**: In run.log, look for:
  `Queried 0 cell types for tissue '...'`
  `score=0.00, 0 matched, source=llm` on every cluster
  `Unsupported model gpt-4o` (means LLM_MODEL not set)

**Fix implemented** (2026-09-15):
- `_query_tissue_cell_types` now retries up to 3 times on empty result
- Each retry logs LLM raw response keys + first 500 chars for diagnosis
- All retries exhausted → `RuntimeError` hard fail (no silent empty dict)
- Verified: with correct LLM_MODEL set, first attempt succeeded (21 types)

**Remaining risk**: LLM non-determinism means even with retry, quality
varies (14-24 cell types across runs). Retry handles total failure but
not quality variance.

### ❌ LLM_MODEL env var empty → fallback to gpt-4o
`_call_openai` hardcodes `model=llm_model or "gpt-4o"` (line 827).
When `LLM_MODEL` env var is unset, the fallback sends `"gpt-4o"` to the
configured API endpoint. Non-OpenAI providers (Xiaomi mimo, etc.) reject
this with 400 → `_call_openai` catches exception → returns `{}`.
**Always set `LLM_MODEL` explicitly.** Check with:
`echo "LLM_MODEL=$LLM_MODEL"` before running.

### ❌ User wants "程序主导, AI辅助" — orchestrator too heavy
The user explicitly requested reverting to commit `f6d3415` (2026-09-15).
That version has the simplest architecture:
  - Step 1: Cluster
  - Step 2: LLM annotates each cluster
  - Step 3: Quality analysis
  - Step 4: Filter or finish (iterate)
  - No orchestrator, no program scoring, no Step 2.5

Backup version that produced good results:
  `/output/luancao/scRNAseq/common/5_combine_h5ad_backup/Uterus/test/`

**Restoration workflow** (when reverting to an old commit):
1. Save current detect_n_pcs fix: `git show HEAD:path | sed -n 'start,endp' > /tmp/backup.py`
2. `git checkout <commit> -- modules/scanpy/bin/scRNAseq.py`
3. Re-apply detect_n_pcs patch on top (old version lacks it)
4. Note: old version uses `--max-iterations` not `--max-recluster-rounds`
5. Old version may lack `--species`, `--skip-te` — check argparse

The orchestrator adds complexity, LLM non-determinism, and often overrides
correct program annotations. User feedback: "当前AI主导的注释效果还是太一般了".

**Design preference**: Keep it simple. Program scoring (if used) drives
annotations. LLM handles only ambiguous cases. No orchestrator checkpoint.

**Version restoration workflow** (when reverting to an old commit):
1. Save current detect_n_pcs fix: `git show HEAD:path | sed -n 'start,endp' > /tmp/backup.py`
2. `git checkout <commit> -- modules/scanpy/bin/scRNAseq.py`
3. Re-apply detect_n_pcs patch on top (old version lacks it)
4. Note: `bed1b16` uses `--max-iterations`, `--species`, `--skip-te`
5. Main branch uses `--max-recluster-rounds` (different param name)
6. `f6d3415` lacks `--species` and `--skip-te` — use `bed1b16` instead
7. After restore + patch, commit and push before testing
Program scoring confidence=high clusters (score≥1.5, margin≥0.3, PMID
verified) can still be overridden by the CP orchestrator. Example: CP
changed Granulosa_Cell to Theca_Cell despite program confidence=high.
This violates the "program drives, AI assists" architecture.
Fix needed: pass program_confident set to _apply_orchestrator_decision
and reject corrections for those clusters.

### ❌ LLM non-determinism across runs
Same prompt + same model + same API → different results every run.
Step 0 returned 24→20→14→14→0→21→41→21 cell types across 8 runs.
Even with cache, orchestrator CP makes different corrections.
Mitigation: Step 0 caching eliminates one source of variance.
CP non-determinism remains unresolved.

### ✅ Step 0 caching for cross-run stability
tissue_cell_types cached to `{output_dir}/tissue_markers_{query}.json`.
Loaded on subsequent runs instead of re-querying LLM. Cache is in output_dir
(shared), NOT report_dir (per-run). Query sanitized: spaces→underscores,
parentheses removed.

### ✅ Step 2.5: Unknown cluster resolution
After annotation pass, Unknown clusters scored against tissue_cell_types.
If best score > 1.5 and >= 3 matched markers → reassign. Log: `[Step 2.5]`

### ❌ Running without --species and --skip-te on scTE data
Tested on macaque ovaries (2026-09-15):
- **Without --skip-te**: TE genes dominate DEG → clusters 8,9 labeled Alu_high.
  429 rate limiting from PubMed hits → clusters 10-19 all Unknown (12/20 flagged).
- **Without --species**: LLM gives generic annotations. No tissue-specific types
  (Theca_cell, Ovarian_surface_epithelium, Lymphatic_endothelial_cell).
- **With both** (bed1b16): 0 Unknown, tissue-specific types detected,
  162 PubMed refs (vs 89 without),19 clean clusters.

**Always use** `--species Mmul_10 --skip-te` for scTE macaque data.

### ❌ Manual marker dictionaries not scalable
Step 0 queries LLM for tissue-specific markers at runtime. No hardcoding.

### ❌ skip_te only filters HVG, NOT DEG raw
TE genes are removed from adata.raw before DEG computation via
`adata._raw = adata.raw[:, te_mask].copy()`.

### ❌ MiniMax rejects response_format=json_object
Fallback: retry without json_object, strip markdown code fences.

### ❌ PubMed XML parsing NoneType on some genes
`_search_pubmed` may log `'NoneType' object is not subscriptable` for some
gene names (TAGLN observed). The outer try/except catches it, so pipeline
continues, but results are lost. Root cause: missing null checks in XML
parsing loop. See `references/pubmed-query-pitfalls.md`.

### ❌ Manually setting LLM env vars when running locally
scRNAseq.py does NOT read LLM config from environment variables.
argparse defaults are empty strings — you MUST pass all four LLM flags explicitly:
`--llm-method openai --llm-model <model> --llm-api-key <key> --llm-base-url <url>`.
The env vars (LLM_API_KEY, LLM_BASE_URL, LLM_METHOD) exist in the shell but
the script ignores them. Use `"$LLM_API_KEY"` etc. in CLI to expand them.

### ❌ Assume user wants pipeline re-run when discussing quality
When the user says "annotation效果不好", they want to DISCUSS the problem
first — not immediately re-run the pipeline. Ask what specific issues
they see before proposing fixes or running tests.

### ❌ Xiaomi mimo API rate limiting after ~10 LLM calls
Each cluster annotation = 1 LLM call + 3-5 PubMed calls. With 19 clusters,
the Xiaomi API returns429 after ~10 calls. The openai client retries
automatically but subsequent clusters may still get Unknown.

**Observed** (ovaries, 2026-09-15): Clusters 10-19 all hit429 → Unknown
in the f6d3415 run. The bed1b16 run succeeded because Step 0 (tissue query)
consumed the first call, and the remaining18 calls were spaced enough.

**Mitigation**: Each LLM call takes2-3 minutes (LLM generation + PubMed
verification). Total run time ~50 minutes for19 clusters. The spacing
helps avoid429 but doesn't eliminate it.

### ❌ Env-var fallback for LLM config
scRNAseq.py does NOT implement env-var fallback. argparse defaults are
empty strings. If CLI values are empty, the LLM calls will fail with
"Missing credentials". Always pass all four LLM flags explicitly.

### ❌ PMID pre-check needed for program-confident branches
Program-scored clusters (score≥1.5) also need PubMed verification.
0 refs → confidence downgraded from "high" to "medium".

### ❌ CP dismisses over-clustering as "biological heterogeneity"
When separation_diag reports over-clustering (Jaccard > 0.3), the CP
orchestrator may dismiss it: "suggests biological heterogeneity rather
than technical over-fragmentation" and choose accept or correct_annotations
without actually fixing the over-clustered types.

Jaccard > 0.3 = clusters share most markers = same cell type mislabeled.
Clustering is fine (clusters are well-separated); annotation is wrong.

Fix: prompt rewritten to say over-clustering → correct_annotations (NOT
adjust_resolution). Plus `_auto_correct_overclustered()` as safety net.

### ❌ PubMed 429 rate limiting cascades into confidence errors
PubMed search interval is only 0.35s between requests. For 18 clusters ×
5 markers each = 90 requests in ~30s → HTTP 429 Too Many Requests.

**Observed** (macaque ovary/uterus, 2026-09-13):
- 429 errors on COL1A1, VWF, RGS5, ACTA2, PECAM1, etc.
- Failed verification → confidence incorrectly downgraded
- Some clusters lost ALL marker verification

**Impact**: confidence=high → medium/downgraded for well-annotated clusters.

**Fix needed**: Add exponential backoff retry (1s→2s→4s) in
`_search_pubmed`, increase base interval to 1.0s. Current code:
```python
time.sleep(0.35)  # too aggressive
```

### ❌ Anthropic max_tokens=4096 truncates long responses
`_call_anthropic` sets `max_tokens=4096`. Long annotation prompts with
29+ tissue cell types produce responses that hit this limit mid-JSON.

**Observed** (macaque ovary/uterus, 2026-09-13):
- `Anthropic API call failed: Unterminated string starting at: line 3 column 19`
- `Expecting value: line 1 column 1 (char 0)`
- Clusters 2,3 in Uterus → Unknown due to API failure (6603 cells affected)

**Fix needed**: Increase `max_tokens` to 8192 in `_call_anthropic`
(line ~888). Add retry on JSON parse failure before giving up.

### ❌ Step 2.5 scoring uses only top 10 DEGs — fails for similar types
`_resolve_unknown_clusters` passes `n_top=len(markers)` where markers is
the cluster's top 10 key_markers. For biologically similar cell types
(Theca vs Granulosa, Stromal vs Fibroblast), unique markers may not
appear until rank 20-40 in the DEG list.

**Observed** (ovaries Cluster 10):
- Top 10 DEG: PLA2G1B,GJA1,DSP,CTSD,GAS6,NR4A2,NR4A3,IFI27,IFI27L2,CYCS
- Theca_Cell unique markers (STAR,CYP11A1,LHCGR) are at rank 15-30
- Step 2.5 scored Theca=0.48, Granulosa=0.48 → ambiguous
- With top 30 DEG, Theca would score much higher due to unique markers

**Fix needed**: Change `n_top=len(markers)` to `n_top=30` in the
Step 2.5 call, matching the main scoring pass.

### ❌ Separation check runs AFTER annotation — CP never fires when clean
The separation_diag check runs after Step 2 annotation. If iteration 2
has no flagged clusters and no over-clustering, the CP checkpoint is
skipped ("All clusters clean. Saving final results.") and misannotations
from iteration 1 are never corrected.

**Observed** (ovaries): Cluster 10 was misannotated as Granulosa_Cell
(LPM) but refined to Theca_Cell by Step 2.5 scoring (score=0.48).
However, CP never got a chance to evaluate this — iteration 2 ended
with "All clusters clean" and the run completed.

**Implication**: The orchestrator CP only fires when sensors detect
problems. If sensors miss an issue (low score but not flagged), the
pipeline accepts the result silently.

### ❌ Over-clustering detection drops resolution too aggressively
Jaccard>0.3 on Smooth_Muscle_Cell (4 clusters) triggers resolution
0.8→0.3. This can merge real biological subtypes (pericyte vs vascular
smooth muscle vs myometrial smooth muscle).

**Observed** (ovaries iteration 1): 4 Smooth_Muscle_Cell clusters with
Jaccard=0.45, max_dist=10.29. Resolution dropped to 0.3. After
re-clustering at 0.3, only 11 clusters remained — some real subtypes
may have been lost.

**Better heuristic**: Only drop resolution if ALL over-clustered types
have Jaccard>0.5 (strong evidence of true duplication). Jaccard 0.3-0.5
may indicate related but distinct subtypes — use correct_annotations
instead.

### ❌ CP says correct_annotations but returns empty annotation_corrections
LLM mentions corrections in reasoning text but `annotation_corrections` JSON
is empty `{}`. Log: "CP decision: correct_annotations" but NO "CP applied:".

Fix: strengthened prompt JSON template + auto-correct fallback when empty.

## Output Files

- `<output>.h5ad` — annotated AnnData
- `<output>_reports/annotation_report.tsv` — per-cluster annotations
- `<output>_reports/references.tsv` — PubMed references per marker
- `<output>_reports/audit_report.md` — Chinese markdown audit summary
- `<output>_run.log` — full execution log
- `<plot_dir>/` — UMAP, dotplot, HVG, PCA variance plots

## Reference Files

- `references/step0-cascade-failure.md` — **CRITICAL**: Step 0 empty-result cascade failure (diagnosis, log signatures, proposed fixes)
- `references/architecture-evolution.md` — v3→v14 design history
- `references/spatial-detection-lessons.md` — boundary sharpness, isolation, discontinuity
- `references/orchestrator-prompt-lessons-2026-09.md` — prompt design pitfalls and fixes
- `references/iteration-history.md` — v7→v14 bug progression
- `references/over-clustering-correction.md` — auto-correct algorithm for over-clustered types
- `references/whole-cluster-filter.md` — ambient-RNA artifact handling
- `references/name-normalization.md` — cross-tissue cell type name normalization
- `references/mixed-identity-detection.md` — holistic marker evaluation
- `references/scte-auto-npcs-fix.md` — auto-n-pcs returns 10-14 on scTE data (diagnosis, workarounds, proposed fixes)

## Rules

- **No fallback logic** — if a value is wrong, fail loudly
- **No hardcoding** — tissue/cell-type knowledge comes from LLM at runtime
- **Step 0 must not silently fail** — empty tissue_cell_types = pipeline failure. Validate and raise.
- **PMID gate mandatory** — all non-trivial annotations need PubMed evidence
- **General-purpose script** — no tissue-specific modifications to the module
