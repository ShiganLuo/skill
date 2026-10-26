# Prompt Structure Evolution (2026-09-18 Session)

## Old Structure (DEGs first, specificity as tie-breaker)

```
1. Cluster info + Top 50 DEGs
2. Other clusters
3. Tissue cell types
4. Specificity table (at the END, labeled "tie-breaker")
5. Task + Rules
```

**Problem**: LLM sees 50 cell cycle genes (MKI67, TOP2A, CENPF...) in DEGs
and 0 oocyte genes. The specificity table at the end gets ignored because
the LLM thinks "this isn't a tie — 50 vs 0 is a clear winner."

**Result**: Oocyte → Proliferating_Cell (wrong)

## New Structure (Specificity first, DEGs as secondary)

```
1. Cluster info (cells, genes, counts, MT%)
2. PRIMARY EVIDENCE: Specificity table ← LLM sees this FIRST
   "Use these as your MAIN basis for cell type identification"
3. SECONDARY EVIDENCE: Top 50 DEGs
   "NOTE: DEGs ranked by statistical significance, NOT specificity"
4. Other clusters + Tissue cell types
5. Task (explicitly says "cite specificity markers in reasoning")
6. Rules:
   - SPECIFICITY FIRST rule
   - Generic marker warning (cell cycle, stress, ECM genes)
```

**Result**: Oocyte → Oocyte (high confidence) ✓

## Key Rules Added

### SPECIFICITY FIRST
"Base your cell type identification on the specificity markers
(PRIMARY EVIDENCE), not on the DEG list. The DEG list contains
many generic genes that do not define cell types."

### Generic Marker Warning
"Cell cycle genes (MKI67, TOP2A, CENPF, CDK1, CCNB2, PCNA),
stress response genes (FOS, JUN, EGR1, HSP), and ECM genes
(COL1A1, COL1A2, DCN) appear across many cell types. If these
dominate the DEGs but the specificity table shows tissue-specific
markers (even with low DEG rank), annotate based on the
tissue-specific markers."

### Marker Priority (in Task section)
"PRIORITIZE high-specificity markers over generic DEGs."

### Reasoning Citation
"Why this cell type? Cite the specificity markers that support
your decision."

## Validation (macaque ovaries v10)

- Oocyte (Cluster 18): NLRP5 8.3x, LHX8 7.4x → Oocyte (high) ✓
- Myofibroblast (Cluster 2): detected (was Smooth_Muscle_Cell before)
- 56 cell types queried (was 40 before improved Step 0 prompt)
- 19 clusters, 15 cell types, 112 unique markers

## Remaining Issue: LLM Returning Fewer Markers

Oocyte only got 2 key_markers (NLRP5, LHX8) instead of 5-10.
This is because oocyte markers have very low expression (2-4% cells)
and the LLM is being conservative. Don't pad with non-specific markers.
