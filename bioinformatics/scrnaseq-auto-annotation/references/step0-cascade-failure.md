# Step 0 Cascade Failure — Diagnostic Reference

## Problem (2026-09-15, macaque ovary run)

`_query_tissue_cell_types('macaque (Macaca mulatta) ovaries')` returned `{}`.
The pipeline continued without any tissue reference, causing every cluster to
score 0.0 and fall through to pure LLM disambiguation.

## Root causes (confirmed by testing)

### Primary: LLM_MODEL env var empty
`LLM_MODEL` was unset → `_call_openai` fell back to `"gpt-4o"` → Xiaomi API
returned `400 Unsupported model gpt-4o` → `_call_openai` caught exception →
returned `{}` → `_query_tissue_cell_types` got empty dict → `raw.get("cell_types", {})` = `{}`.

### Secondary: LLM non-determinism
Same model (mimo-v2.5-pro), same prompt, different results across 5 runs:

```
v1: 24 cell types, 146 markers, 0  unverified  (best)
v2: 20 cell types, 131 markers, 32 unverified
v3: 14 cell types, 100 markers, 16 unverified
v4: 14 cell types,  88 markers, 66 unverified  (quality cliff)
v5:  0 cell types                               (complete failure)
```

Temperature=0.1 is not low enough for deterministic output.

## Cascade chain

```
Step 0 returns {}
  → tissue_cell_types = {}
  → _score_cluster_against_tissue_types(top_genes, {}) = {best_score: 0.0, ...}
  → program_confident = False for ALL clusters
  → ALL clusters → _llm_disambiguate_cluster()
  → disambiguation prompt has "Available tissue types: (unknown)"
  → LLM guesses based on own knowledge, no reference grounding
  → Results vary between runs (unstable)
  → Orchestrator sees all-low trust → adjust/filter loops
  → 4 rounds × 19 clusters = ~60 LLM calls, all wasted
```

## Log signatures

```
# LLM_MODEL not set (400 error):
Unsupported model gpt-4o
Step 0 attempt N: LLM returned no 'cell_types' key. Top-level keys: []. Raw preview: {}

# LLM returned but no cell_types key:
Step 0 attempt N: LLM returned no 'cell_types' key. Top-level keys: ['some_other_key']. Raw preview: ...

# All clusters on LLM (no program scoring):
score=0.00, 0 matched, source=llm   (on EVERY cluster)
Queried 0 cell types for tissue '...'
```

## Fix implemented (2026-09-15)

In `_query_tissue_cell_types`:
1. Retry loop (MAX_RETRIES=3) around LLM call
2. On empty `raw.get("cell_types", {})`: log warning with raw response keys + first 500 chars
3. sleep(2) between retries
4. All retries exhausted → `RuntimeError` hard fail (no silent empty dict)

```python
MAX_RETRIES = 3
raw: Dict[str, Any] = {}
for attempt in range(1, MAX_RETRIES + 1):
    logging.info("  Step 0 tissue query attempt %d / %d ...", attempt, MAX_RETRIES)
    # ... LLM call ...
    raw_types = raw.get("cell_types", {})
    if raw_types:
        break
    logging.warning(
        "  Step 0 attempt %d: LLM returned no 'cell_types' key. "
        "Top-level keys: %s. Raw preview (first 500 chars): %s",
        attempt, list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__,
        str(raw)[:500],
    )
    if attempt < MAX_RETRIES:
        time.sleep(2)
else:
    raise RuntimeError(
        f"Step 0 failed after {MAX_RETRIES} attempts: LLM returned no 'cell_types' key. "
        f"Last raw response keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}. "
        f"Cannot proceed without tissue reference markers."
    )
```

## Test results (v6 run, after fix)

```
Step 0: 21 cell types, 126 markers, first attempt success
Program scoring: Smooth_muscle(3.88), Fibroblasts(1.74), Epithelial(1.79)
Only ambiguous clusters sent to LLM (score 0.5-1.5)
2 rounds (vs 4 rounds before), CP made sensible decisions
```

Note: LLM non-determinism means cell type count varies per run (21, 41, 21
observed across 3 v6-v8 runs). The retry handles total failure (0 types)
but not quality variance. Higher cell type counts → better program scoring
(more reference markers to match against).

## Caching fix (2026-09-15)

Step 0 result cached to `{output_dir}/tissue_markers_{sanitized_query}.json`.
Sanitization: spaces→underscores, parentheses removed.
Cache is in output_dir (shared across all runs in same directory).

On cache hit: `[Step 0] Loaded N cell types from cache: /path/to/file.json`
On cache miss: `[Step 0] Cached tissue markers to /path/to/file.json`

This eliminates Step 0 non-determinism for subsequent runs. First run still
varies. To manually seed cache: run once, copy cache file to shared location.

## Diagnostic commands

```bash
# Check if Step 0 succeeded
grep "Queried.*cell types" run.log

# Check retry attempts
grep "Step 0.*attempt" run.log

# Check for LLM_MODEL issue
grep "Unsupported model" run.log

# Count how many clusters fell to LLM
grep -c "source=llm" run.log

# Check score distribution
grep -oP "score=[\d.]+" run.log | sort | uniq -c | sort -rn

# Verify LLM_MODEL is set
echo "LLM_MODEL=$LLM_MODEL"
```
