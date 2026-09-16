# Orchestrator Prompt Patterns (Tested on mimo-v2.5-pro)

## Key Principles

1. **Minimal prompt**: LLM must parse prompt AND produce JSON. Don't fill context with rules.
2. **Data over instructions**: Show Jaccard/max_distance as data, don't instruct LLM to compute them.
3. **Current resolution in header**: LLM needs to know what to change FROM.
4. **JSON schema example**: Always include a template JSON in the prompt.
5. **No rules_block**: Rules overwhelm small models. Inline key rules in action descriptions.

## Working Prompt Template

```
You are the orchestrator of an scRNA-seq annotation pipeline.
Decide: accept, correct, filter, or recluster.

Round {recluster_round}/{max_recluster_rounds}.
Current resolution: {resolution}.
{ct_summary}
{sep_summary}

## Available actions (choose EXACTLY ONE)

1. "accept" — good enough. Use when most clusters trust=high/medium AND no over_clustering AND no misannotated.

2. "correct_annotations" — relabel clusters with trust=low + alternative!=null. Also merge synonyms (Fibroblasts/Stromal etc). REQUIRES: annotation_corrections.

3. "filter_and_recluster" — drop bad cells. whole_cluster_removals for should_drop=true; cell_level_clusters for lq_pct>30. REQUIRES: filter_plan.

4. "adjust_resolution_and_recluster" — merge over-fragmented clusters. Use when over_clustering Jaccard>0.3 OR many trust=low without alternatives. Lower resolution by ~0.15-0.2. REQUIRES: new_resolution.

Output ONLY valid JSON:
{"action": "accept|correct_annotations|filter_and_recluster|adjust_resolution_and_recluster", "reasoning": "why", "filter_plan": {"whole_cluster_removals": [], "cell_level_clusters": []}, "new_resolution": null, "annotation_corrections": {}}

## STATE
{state_json}
```

## What NOT to Do

### Verbose action descriptions (causes empty action)
```
# BAD — 5+ lines per action, LLM gets lost
1. "accept" — translations AND structure are good enough. Pipeline saves and exits.
   ONLY when ALL of these are true:
   - Most clusters have trust=high or trust=medium
   - NO same cell_type appears in >2 clusters (no over-clustering)
   - NO synonym pairs (e.g. Fibroblasts + Stromal)
   - Any trust=low clusters are genuinely uncertain
```

### rules_block (causes empty action)
```
# BAD — separate rules section adds too much context
rules_block = """## Rules
- TWO kinds of problems need fixing...
- STRUCTURAL CHECK (mandatory before accepting):
  1. Count how many distinct cell_types appear...
  2. Look for synonym pairs...
  ...
"""
```

### Counting clusters instead of using Jaccard
```
# BAD — biologically wrong, same cell type can legitimately be in multiple clusters
"If any cell_type has 3+ clusters -> prefer adjust_resolution_and_recluster"

# GOOD — use separation_diag metrics
"Use when over_clustering Jaccard>0.3"
```

## Resolution Enforcement

The orchestrator sometimes sets `new_resolution` to the same value as current. Always validate:

```python
if float(new_res) == resolution:
    resolution = max(0.05, resolution - 0.2)
    logging.warning("CP set same resolution — forcing decrease to %.2f", resolution)
```

## State Fields (what orchestrator sees per cluster)

```python
clusters_payload[cluster] = {
    "cell_type": str,
    "top_markers": list[str],  # top 10 DEG
    "trust": "high" | "medium" | "low",
    "alternative": str | null,
    "should_drop": bool,
    "low_quality_cell_pct": float,  # 0-100
    "score": float,  # program specificity-weighted score
    "n_matched": int,  # number of matched markers
    "n_cells": int,
    "mean_genes": float,
    "mean_counts": float,
    "pct_mt": float,
    "qc_flags": list[str],
}
```

## Structural Summary (injected into prompt header)

```python
# ct_summary: cell types with multiple clusters
ct_summary = "\nCell types with MULTIPLE clusters:\n  - Smooth_muscle_cell: 4 clusters (2, 8, 9, 10)"

# sep_summary: from separation_diag
sep_summary = """
Over-clustered types (Jaccard > 0.3):
  - Smooth_muscle_cell: 4 clusters, max_dist=10.59, Jaccard=0.758
Misannotated candidates (Jaccard <= 0.3):
  - Endothelial_cell: 4 clusters, Jaccard=0.170, flagged cluster 1
"""
```