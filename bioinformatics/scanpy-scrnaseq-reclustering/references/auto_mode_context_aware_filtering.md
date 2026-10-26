# Auto Mode: Context-Aware Filtering & Cell Type Preservation

## Context-Aware Cell Filtering (Step 4)

`_filter_flagged_cells()` uses a 4-level strategy based on annotation quality, NOT blind QC thresholds:

```
flagged cluster
  ├─ TE-dominated → filter by TE fraction (gene_type annotation required)
  │   TE fraction > 0.5 → remove (pure TE noise)
  │   TE fraction ≤ 0.5 → keep (has real gene expression)
  │   Fallback if no gene_type: generic QC thresholds
  │
  ├─ High confidence + has PMID → SKIP (biological low QC, e.g. Oocyte)
  │
  ├─ Medium confidence / has refs → relaxed QC thresholds
  │   min_genes×0.5, min_counts×0.5, max_pct_mt×1.5
  │
  └─ Low confidence / no evidence → strict QC thresholds (original values)
```

### TE Fraction Distribution (macaque ovary, 19,816 cells)

| TE fraction | Cells | % | protein_coding % | Interpretation |
|-------------|-------|---|------------------|----------------|
| 0.0-0.2 | 2,619 | 13.2% | 67.3% | Low TE, normal |
| 0.2-0.3 | 6,638 | 33.5% | 62.7% | Normal (most cells) |
| 0.3-0.4 | 6,261 | 31.6% | 55.3% | Normal |
| 0.4-0.5 | 2,357 | 11.9% | 44.1% | Slightly high |
| 0.5-0.6 | 881 | 4.4% | 32.2% | TE-high |
| 0.6-0.7 | 643 | 3.2% | 25.1% | TE-high |
| 0.7-0.8 | 365 | 1.8% | 20.5% | TE-dominant |
| 0.8-1.0 | 52 | 0.3% | 14.3% | Near-pure TE |

**Threshold**: TE fraction > 0.5 (50%) is the cutoff for "pure TE noise". Cells below this have real protein-coding gene expression and should be preserved.

### Why Not Remove Entire TE-Dominated Clusters?

TE-dominated clusters may contain a mix of:
- Pure TE noise cells (high TE fraction, no protein-coding expression) → should be removed
- Real cells with TE expression + protein-coding genes → should be preserved

Per-cell TE fraction filtering is more accurate than entire cluster removal.

### Implementation

```python
if "te_dominated" in flags:
    if "gene_type" in adata.var.columns:
        te_genes = adata.var_names[adata.var["gene_type"] == "TE"]
        te_counts = adata[cluster_cells.index, te_genes].X.sum(axis=1)
        total = adata[cluster_cells.index].X.sum(axis=1)
        te_frac = np.nan_to_num(te_counts / total)
        high_te_mask = te_frac > 0.5
        bad_cells = cluster_cells.index[high_te_mask]
        keep_mask[bad_cells] = False
```

## Rare Cell Type Preservation (Step 2.5)

`_preserve_lost_cell_types()` detects rare cell types lost during re-clustering:

1. Compare previous iteration's cell_type labels with current
2. Identify "lost" types (present before, absent now)
3. Skip noise types (Unknown, Unverified, Unverified_TE, Unannotated)
4. For each lost type: find cells that had it, check if >50% are in one cluster
5. If concentrated → restore old label
6. If scattered → don't preserve (probably real merge)

### Critical: Categorical Handling

`cell_type` is categorical. Before assigning a new category value:
```python
if lost_type not in adata.obs["cell_type"].cat.categories:
    adata.obs["cell_type"] = adata.obs["cell_type"].cat.add_categories([lost_type])
```

Without this, pandas raises: `TypeError: Cannot setitem on a Categorical with a new category`

### Example: Oocyte Preservation

- Iteration 1: Oocyte (33 cells) identified as separate cluster, high confidence, PMID support
- Iteration 2: After filtering and re-clustering at lower resolution, Oocyte absorbed into Granulosa
- Step 2.5: `_preserve_lost_cell_types` detects Oocyte is missing, finds 30/33 cells in Granulosa cluster → restores Oocyte label

## Marker Jaccard for Misannotation Detection

When same cell_type appears in clusters far apart in UMAP (distance > 5.0):

1. Compare `key_markers` between clusters using Jaccard similarity
2. **Jaccard > 0.3** → genuine over-clustering (markers match) → suggest lower resolution
3. **Jaccard ≤ 0.3** → annotation error (markers diverge) → flag smallest cluster

This prevents the pipeline from lowering resolution when the real problem is misannotation.

## Debug Mode (`--debug`)

Saves per-iteration UMAP and annotation plots:
```
plots/auto/
  iter_1/ cluster_umap_leiden.png, annotate_umap_cell_type.png, annotate_deg_dotplot.png, ...
  iter_2/ ...
```

Default OFF. Enable for testing iterative behavior.

## Pitfalls

### Categorical crash when preserving cell types
**Symptom**: `TypeError: Cannot setitem on a Categorical with a new category (Oocyte)`
**Fix**: Add category before assignment (see above)

### TE-dominated cluster entire removal is wrong
**Symptom**: All cells in TE-dominated cluster removed, including cells with real gene expression
**Fix**: Use TE fraction per-cell filtering. Keep cells with TE < 50%.

### Blind QC thresholds destroy biologically low-QC cell types
**Symptom**: Oocyte (naturally small cells with low gene/UMI counts) filtered out as "low quality"
**Fix**: Context-aware filtering. High-confidence annotations with PMID support skip QC filtering entirely.
