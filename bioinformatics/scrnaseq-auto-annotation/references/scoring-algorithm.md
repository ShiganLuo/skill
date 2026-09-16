# Specificity-Weighted Scoring Algorithm (v14+)

## Purpose
Score each cluster's top DEGs against `tissue_cell_types` (from Step 0)
using specificity weighting. Saves 80-90% of LLM calls — only ambiguous
clusters go to LLM disambiguation.

## Algorithm

```python
# Source: tissue_cell_types dict from Step 0 (LLM query, not hardcoded)
# Each cell_type -> list of canonical marker genes

# 1. Compute gene specificity: 1 / (number of cell types it appears in)
gene_specificity = {}
for ct, markers in tissue_cell_types.items():
    for g in markers:
        gene_specificity[g] = gene_specificity.get(g, 0) + 1
for g in gene_specificity:
    gene_specificity[g] = 1.0 / gene_specificity[g]

# 2. Score each cluster against all cell types
for ct, markers in tissue_cell_types.items():
    ct_set = set(markers)
    matched = top_set & ct_set
    score = 0.0
    for g in matched:
        rank = top_genes.index(g)  # 0-based rank from DEG
        rank_weight = 1.0 / (1.0 + rank * 0.05)  # v15: was 0.1
        score += gene_specificity.get(g, 0) * rank_weight
    # Higher score = better match
```

## Key Properties
- Unique markers (only in one cell type) score 1.0 per match
- Shared markers (in N cell types) score 1/N per match
- Higher-ranked DEGs (smaller index) get more weight
- Combines specificity + rank for robust matching

## Rank Weight (v15 change)
Coefficient changed from 0.1 to 0.05 for flatter decay:
- rank 0: 1.00 (unchanged)
- rank 5: 0.80 (was 0.67)
- rank 10: 0.67 (was 0.50)
- rank 20: 0.50 (was 0.33)
- rank 30: 0.40 (was 0.25)

Rationale: top DEG weight was too dominant. If top 2 DEGs are shared
markers, score was suppressed even when 6 unique markers follow.

## Three Score Regimes (in `_run_one_annotation_pass`)

| Regime | Condition | Action |
|--------|-----------|--------|
| Program confident | score >= 1.5 AND margin >= 0.3 | Program decides, no LLM. PMID pre-check: 0 refs → "medium" |
| Ambiguous | 0.5 <= score < 1.5 OR small margin | LLM disambiguation (top-3 candidates + PMID requirement) |
| No match | score < 0.5 OR no matches | LLM free annotation (still with PMID requirement) |

## PMID Pre-Check for Program-Confident Branch (v15)

Previously, program_confident clusters skipped LLM entirely and got
confidence="high" unconditionally. Now:
1. Search PubMed for 3 key markers × cell_type
2. If 0 refs found → confidence downgraded to "medium"
3. Reasoning gets `[PMID pre-check: 0 refs for program-chosen type; medium confidence.]`

This catches cases where Step 0 `tissue_cell_types` contains hallucinated
markers that happen to match the DEGs by coincidence.

## Example
If FOXL2 appears in both "Granulosa" and "Ovarian_stromal":
- FOXL2 specificity = 1/2 = 0.5
- If FOXL2 is rank 0 in DEGs: score contribution = 0.5 * 1.0 = 0.5
- If FOXL2 is rank 10: score contribution = 0.5 * 0.67 = 0.335

## Source
`_score_cluster_against_tissue_types(top_genes, tissue_cell_types, n_top=30)`
in `workflow/Omics/modules/scanpy/bin/scRNAseq.py`.
