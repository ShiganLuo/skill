# QC Filtering Strategies for scRNA-seq

## Hard Filters vs MAD-based Detection

### Hard Filters (Default)
Fixed thresholds applied directly:
- `min_genes`: Minimum genes per cell (default 200)
- `max_genes`: Maximum genes per cell (default 6000)
- `max_pct_mt`: Maximum mitochondrial percentage (default 20%)

**Pros**: Simple, reproducible, interpretable
**Cons**: May miss subtle outliers, tissue-dependent thresholds

### MAD-based Detection (Optional)
Median Absolute Deviation: cell is outlier if value > median ± N × MAD
- Typically N=5 for counts/genes, N=3 for mt%
- Adaptive to data distribution

**Pros**: Adapts to dataset-specific distributions
**Cons**: Can be too aggressive, removes real biology

## Order Matters: Which is More Strict?

### Scenario: n_genes_by_counts, max_genes=6000

**MAD first → hard filter (more permissive)**:
```
Full data: median=2000, MAD=500 (with extremes, high variance)
Threshold: 2000 + 5×500 = 4500
MAD removes n_genes > 4500
Hard filter (6000) removes nothing extra
Result: keep n_genes < 4500
```

**Hard filter first → MAD (more strict)**:
```
After hard filter: n_genes 100-6000
New data: median=1800, MAD=400 (no extremes, low variance)
Threshold: 1800 + 5×400 = 3800
MAD removes n_genes > 3800
Result: keep n_genes < 3800
```

**Conclusion**: Hard filter first → MAD is MORE STRICT (MAD on cleaner data has smaller variance → tighter threshold)

## Nature Paper Practices

### Standard approach (most common)
Hard thresholds as primary filter:
- min_genes: 100-200
- max_genes: 2500-6000 (tissue-dependent)
- mt%: 5-20% (tissue-dependent)

### Scanpy official tutorial (permissive)
```python
sc.pp.filter_cells(adata, min_genes=100)
sc.pp.filter_genes(adata, min_cells=3)
# Later: adata = adata[adata.obs.n_genes < 2500, :]
# Later: adata = adata[adata.obs.percent_mito < 0.05, :]
```

Recommendation: "start with a very permissive filtering strategy and revisiting it at a later point"

### Recent Nature paper (scQCenrich, 2026)
- Hard thresholds may remove real biology
- Suggests integrating more metrics: intronic fraction, MALAT1, stress signatures
- Cancer studies: mt% threshold often 15%, some studies skip mt% entirely

## Tissue-Specific Recommendations

| Tissue Type | max_genes | max_pct_mt | Notes |
|-------------|-----------|------------|-------|
| Normal tissue | 6000 | 20% | Standard |
| Cancer/tumor | 6000-8000 | 15-25% | Higher baseline mt% |
| Cardiomyocytes | 8000-10000 | 20% | High gene counts |
| Neurons | 8000-10000 | 20% | High gene counts |
| PBMC/immune | 2500-4000 | 15% | Lower gene counts |
| Metabolically active | 6000 | 25% | High mt% is normal |

## Implementation in Omics Workflow

Default: hard filters only (no MAD)
Optional: `--use-mad` flag enables MAD before hard filters

```python
def mode_qc(adata, ..., use_mad=False, ...):
    # MAD optional (more permissive when enabled)
    if use_mad:
        # MAD on full data (more permissive)
        adata.obs["outlier"] = (
            is_outlier(adata, "log1p_total_counts", 5)
            | is_outlier(adata, "log1p_n_genes_by_counts", 5)
            | is_outlier(adata, "pct_counts_in_top_20_genes", 5)
        )
        adata = adata[~adata.obs["outlier"]].copy()
    
    # Hard filters (always applied)
    adata = adata[
        (adata.obs["n_genes_by_counts"] >= min_genes)
        & (adata.obs["n_genes_by_counts"] <= max_genes)
        & (adata.obs["pct_counts_mt"] <= max_pct_mt)
    ].copy()
```
