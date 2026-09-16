# Tissue Knowledge Query (Step 0)

## Problem

Pure LLM annotation uses generic cell type names (e.g., "Fibroblast") instead of tissue-specific subtypes (e.g., "Luteal", "Cumulus", "Theca"). This happens because:
1. LLM sees only top50 DEGs — no context about what cell types exist in the tissue
2. LLM defaults to generic names when unsure
3. Tissue-specific subtypes require domain knowledge that isn't in the DEGs

**User correction**: "首先我们这是自动化注释,你上面方案肯定不行.组织来源是多样" — Pre-defined marker dictionaries don't work for automation because tissue sources are diverse. Cannot manually inject markers for every tissue.

## Solution: Two-Stage LLM Approach

### Stage 1: Query Tissue Cell Types (Step 0)

Before any clustering/annotation, ask the LLM: "What are the known cell types in {tissue}?"

```python
def _query_tissue_cell_types(tissue, llm_method, llm_model, llm_api_key, llm_base_url):
    """Query LLM for known cell types and their canonical markers in a tissue."""
    prompt = f"""You are a single-cell RNA-seq expert. List ALL known cell types 
found in {tissue} tissue from published scRNA-seq studies.

For each cell type, provide 5-8 canonical marker genes that are USED IN THE 
LITERATURE to identify that cell type.

Output a JSON object with:
- "cell_types": a dict where keys are cell type names and values are lists of 
  canonical marker genes

Rules:
- Include ALL known cell types, including rare subtypes
- Use standard nomenclature from published studies
- Include tissue-specific subtypes (e.g., for ovary: Luteal, Cumulus, Theca, Granulosa)
- Markers should be protein-coding genes commonly used in literature
- Output ONLY valid JSON, no markdown
"""
    # Call LLM...
    return cell_types  # Dict[str, List[str]]
```

### Stage 2: Inject into Annotation Prompts

The tissue cell types are injected into every cluster's annotation prompt:

```python
if tissue_context:
    prompt += f"""
## Known cell types in {tissue} (from published scRNA-seq studies)
{tissue_context}

IMPORTANT: You MUST annotate this cluster as one of the above cell types if 
the markers match. Do NOT use generic names (e.g., "Fibroblast") when a 
tissue-specific subtype exists (e.g., "Luteal", "Cumulus", "Theca").
If none of the above cell types match, you may use a new name.
"""
```

## Results (Tested on Macaque Ovary scTE Data)

| Cell Type | Before (no query) | After (with query) |
|-----------|-------------------|-------------------|
| Theca_cells | ❌ missed | ✅ identified (STAR, CYP11A1, LHCGR) |
| Mesothelial_cells | ❌ missed | ✅ identified (MSLN, KRT19, ITLN1) |
| Stromal_cells | "Fibroblast" | "Stromal_cells" |
| Smooth_muscle | "Smooth_muscle" | "Smooth_muscle_cells" |

**Still not separately identified** (due to clustering resolution or marker overlap):
- Luteal → merged into Granulosa_cells
- Cumulus → merged into Granulosa_cells
- Myofibroblast → merged into Smooth_muscle/Stromal
- Pericyte → merged into Smooth_muscle

## Code Location

Modified in `scRNAseq.py`:
- New function: `_query_tissue_cell_types()` — queries LLM for tissue cell types
- Modified: `_build_auto_annotation_prompt()` — added `tissue_cell_types` parameter
- Modified: `_ai_annotate_cluster()` — passes `tissue_cell_types` to prompt builder
- Modified: `mode_auto()` — calls `_query_tissue_cell_types()` at Step 0, passes to all annotation calls

## Design Decisions

1. **No pre-defined markers** — tissue sources are diverse, cannot maintain marker dictionaries for every tissue
2. **LLM provides knowledge, scoring provides precision** — two complementary approaches
3. **Query once, use for all clusters** — tissue knowledge is stable across iterations
4. **Injected as "reference" not "constraint"** — LLM can still identify new cell types not in the list

## Remaining Gap: scTE vs Cell Ranger Differences

Even with tissue knowledge query, some cell types are still not separately identified. Root cause analysis:

| Difference | Root Cause | Fixable? |
|------------|-----------|----------|
| Luteal not identified | Clustering resolution (0.4 vs 0.8) | Yes: increase resolution |
| Cumulus not identified | Merged into Granulosa at low resolution | Yes: increase resolution |
| Myofibroblast not identified | Markers overlap with SM (ACTA2, MYH11) | Partial: needs more specific markers |
| Pericyte not identified | Merged into SM at low resolution | Yes: increase resolution |
| Smooth_muscle 19.7% vs 6.5% | Cell Ranger splits SM+Myofibroblast+Pericyte | Not a bug: different granularity |

**Key insight**: Cell Ranger uses resolution=0.8 (22 clusters), auto mode uses 0.4 (13 clusters). Higher resolution would split more subtypes but may over-cluster.
