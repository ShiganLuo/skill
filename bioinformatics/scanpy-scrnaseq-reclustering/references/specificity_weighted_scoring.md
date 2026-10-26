# Specificity-Weighted Scoring for LLM Auto-Annotation

## Problem

Pure LLM annotation (top50 DEG → LLM → cell_type) produces imprecise labels:
- LLM uses generic names ("Fibroblast" vs "Ovarian_stroma_fibroblast")
- LLM misses tissue-specific subtypes (Cumulus, Luteal, Pericyte, Mesothelial)
- No quantitative scoring — LLM confidence is subjective

Manual annotation (annotate_all.py) uses pre-defined marker dictionaries with specificity-weighted scoring, achieving higher precision. But pre-defined markers don't work for automation because tissue sources are diverse.

## Solution: LLM-Provided Canonical Markers + Specificity Scoring

The key insight: **let LLM provide the canonical markers itself**, then apply the same specificity-weighted scoring algorithm used in annotate_all.py.

### Step 1: Prompt Modification

Add `canonical_markers` to the JSON output requirement:

```
- "canonical_markers": list of 6-10 canonical marker genes for this cell type
  from published literature. These should be the STANDARD markers used to
  identify this cell type, NOT limited to the DEGs provided. For example,
  for Granulosa cells: ["FOXL2", "CYP19A1", "FSHR", "AMH", "HSD17B1", "INHA"].
  For Endothelial: ["PECAM1", "VWF", "CDH5", "KDR", "FLT1"].
  This is critical for specificity-weighted scoring.
```

### Step 2: Collect Canonical Markers

After all clusters are annotated by LLM, collect canonical_markers into a temporary marker dictionary:

```python
temp_marker_dict: Dict[str, List[str]] = {}
for cl, ann in annotations.items():
    ct = ann["cell_type"]
    canonical = ann.get("canonical_markers", [])
    if canonical and ct not in ("Unknown", "Unverified_TE", "Unannotated"):
        if ct not in temp_marker_dict:
            temp_marker_dict[ct] = []
        for g in canonical:
            if g not in temp_marker_dict[ct]:
                temp_marker_dict[ct].append(g)
```

### Step 3: Specificity-Weighted Scoring

Apply the same algorithm from annotate_all.py:

```python
# Gene specificity: 1 / (number of cell types it appears in)
gene_specificity: Dict[str, float] = {}
for ct, markers in temp_marker_dict.items():
    for g in markers:
        gene_specificity[g] = gene_specificity.get(g, 0) + 1
for g in gene_specificity:
    gene_specificity[g] = 1.0 / gene_specificity[g]

# Re-score each cluster
for clust, top_genes in cluster_markers.items():
    top_set = set(top_genes)
    best_ct = annotations[clust]["cell_type"]  # default to LLM label
    best_score = 0.0
    for ct, markers in valid_markers.items():
        matched = top_set & markers
        score = 0.0
        for g in matched:
            rank = top_genes.index(g)
            rank_weight = 1.0 / (1.0 + rank * 0.1)  # rank0=1.0, rank10=0.5, rank49=0.17
            score += gene_specificity.get(g, 0) * rank_weight
        if score > best_score:
            best_score = score
            best_ct = ct
    cluster_to_ct_refined[clust] = best_ct
```

### Step 4: Apply Refined Labels

Overwrite LLM labels with scoring-refined labels. Preserve original LLM labels in `llm_label` column for comparison:

```python
for clust in annotations:
    annotations[clust]["cell_type_refined"] = cluster_to_ct_refined.get(clust, annotations[clust]["cell_type"])
    annotations[clust]["cell_type"] = annotations[clust]["cell_type_refined"]

adata.obs["cell_type"] = adata.obs["leiden"].map(cluster_to_ct).astype("category")
adata.obs["llm_label"] = adata.obs["leiden"].map(original_llm_labels).astype("category")
```

## Why This Works

1. **LLM provides domain knowledge** — it "knows" what canonical markers each cell type should have, across any tissue
2. **Specificity scoring provides precision** — genes unique to one cell type score higher than shared genes
3. **Rank weighting** — top DEGs matter more than lower-ranked ones
4. **No pre-defined markers** — works for any tissue automatically

## Results (Tested on Macaque Ovary scTE Data)

| Metric | Before (LLM only) | After (LLM + Scoring) |
|--------|-------------------|----------------------|
| Cell types identified | 9 | 10 |
| Pericyte | ❌ missed | ✅ identified |
| Ovarian_surface_epithelium | ❌ missed | ✅ identified |
| Theca_lutein | ❌ missed | ✅ identified |
| Label precision | Generic | Tissue-specific |

## Code Location

Modified in `scRNAseq.py`:
- Prompt: `_build_auto_annotation_prompt()` — added canonical_markers field
- Parser: `_ai_annotate_cluster()` — parses canonical_markers from LLM response
- Scoring: `mode_auto()` Step 2.5 — specificity-weighted scoring refinement

## Key Rules

1. **Never pre-define markers for automation** — tissue sources are diverse
2. **LLM provides markers, scoring provides precision** — two-stage approach
3. **Preserve both labels** — `cell_type` (refined) and `llm_label` (original) for audit
4. **Skip Unknown/Unverified_TE** — these don't have meaningful canonical markers
5. **Log all label changes** — when refined != LLM, log the change for transparency
