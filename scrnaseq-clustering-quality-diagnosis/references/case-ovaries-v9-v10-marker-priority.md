# Case: Oocyte Loss & Stress Gene Misannotation (v8→v10, 2026-09-18)

## Timeline

| Version | Step 0 Types | Cluster 18 | Cluster 10 (stromal) | Marker Plots |
|---------|-------------|------------|---------------------|-------------|
| v8 | 40 | Oocyte ✓ | Smooth_Muscle_Cell | 43 markers, 19 clusters |
| v9 (failed) | 0 (JSON error) | N/A | N/A | N/A |
| v9 (retry) | 50 | **Proliferating_Cell** ✗ | **Activated_Stromal_Cell** ✗ | 136 markers, 17 cell types |
| v10 | 49 | **Proliferating_Cell** ✗ | **Fibroblast** | 163 markers, 18 cell types |

## Root Cause: Generic Markers Hiding Tissue-Specific

### Cluster 18 (Oocyte → Proliferating_Cell)

v8 annotations: FIGLA, NOBOX, DDX4, DPPA3, DPPA5 (oocyte-specific)
v9 annotations: MKI67, TOP2A, STMN1, HMGB2, NUSAP1, CENPF, CDK1, PRC1, BIRC5, TPX2 (ALL cell cycle)

Oocyte markers in specificity table:
- DDX4: Cluster 25 (v9) = 0.022 mean, 2.1% expressing
- NLRP5: Cluster 25 = 0.081 mean, 4.2% expressing
- FIGLA: Cluster 25 = 0.040 mean, 2.3% expressing

These ARE in the specificity table but at very low expression. The LLM saw
50 cell cycle DEGs and 3-5 oocyte markers in the specificity table → chose
Proliferating_Cell because the signal was overwhelming.

Adding Proliferating_Cell to Step 0 gave the LLM an easy out — before v9,
the LLM had to choose Oocyte (only option matching DDX4/NLRP5).

### Cluster 10 (Stromal → Activated_Stromal_Cell)

v9 markers: IGFBP5, FOSB, EGR1, FOS, JUN, NR4A1, DCN, APOE, ALDH1A1, RARRES2

Expression analysis:
| Gene | Type | C10 mean | C10 %Expr | Next best | Next % |
|------|------|----------|-----------|-----------|--------|
| FOS | stress | high | ~96% | ~96% (all clusters) | ubiquitous |
| JUN | stress | high | ~96% | ~96% (all clusters) | ubiquitous |
| EGR1 | stress | high | ~80% | ~70% (many) | ubiquitous |
| IGFBP5 | stromal | 3.804 | 99.5% | 3.245 (C5) | 97.1% |
| SFRP1 | stromal | 2.570 | 91.4% | 0.968 (C5) | 48.4% |

FOS/JUN/EGR1 are stress response genes from tissue dissociation — expressed
in ALL clusters, NOT cell type markers. IGFBP5/DCN/APOE are stromal markers
shared with other stromal clusters (not specific to C10).

The LLM interpreted the combination as "activated" stromal cells, but none
of the markers are specific to Cluster 10.

## Code Changes Made

### 1. `_call_anthropic` retry logic (scRNAseq.py)
```python
def _call_anthropic(..., max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            # ... API call + JSON parse ...
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logging.warning("JSON parse failed (attempt %d/%d): %s",
                            attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                _time.sleep(2 * (attempt + 1))
                continue
            return {}
```

### 2. Step 0 prompt improvement (`_query_tissue_cell_types`)
Added: "Include transitional, activated, and mixed-phenotype cell types
(e.g. Myofibroblast, Activated_Stromal_Cell, Cancer-Associated_Fibroblast,
Tip_Endothelial_Cell, Proliferating_cell)."

Result: 40 → 50 cell types for macaque ovaries.

### 3. Marker priority rule (`_build_auto_annotation_prompt`)
Added to Rules section: tissue-specific markers take PRIORITY over generic
markers (cell cycle, stress, ECM). When both present, annotate based on
tissue-specific.

### 4. `plot_markers` rewrite (plot.py)
- Group by cell type (not cluster)
- Plot ALL markers (not top 3)
- Title: `{CellType}  [C4, C12, C14]`
- Highlight all clusters belonging to the cell type

## Unresolved: Marker Priority Rule Insufficient

The prompt-level fix was added but v10 STILL annotated Cluster 18 as
Proliferating_Cell. The LLM sees 50 generic DEGs vs a few markers in
the specificity table and still chooses the generic annotation.

**Possible stronger fixes** (not yet implemented):
1. Pre-flag clusters where generic markers dominate top DEGs but tissue-specific
   markers exist in specificity table → inject explicit warning into prompt
2. Post-hoc correction: if LLM annotates as Proliferating_Cell but specificity
   table shows tissue-specific markers (DDX4, NLRP5) → override annotation
3. Remove Proliferating_Cell from Step 0 cell types (loses ability to detect
   real proliferating populations)

## Lesson: Step 0 Cell Type List Has Side Effects

Adding generic cell types (Proliferating_Cell, Activated_Stromal_Cell) to
Step 0 gives the LLM more options but also more chances to misannotate.
Every new cell type in the list is a potential "attractor" that can steal
annotations from the correct tissue-specific type.

Trade-off: include generic types for real populations, but enforce marker
priority rules to prevent them from overriding tissue-specific annotations.
