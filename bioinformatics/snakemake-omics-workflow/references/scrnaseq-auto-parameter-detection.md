# scRNA-seq Auto-Parameter Detection

Techniques for automatically detecting optimal `n_pcs` and `n_top_genes` in scanpy clustering.

## PCA Elbow Detection (n_pcs)

Uses the **second derivative** (curvature) method on the variance ratio curve.

```python
def detect_n_pcs(variance_ratio, min_pcs=10, max_pcs=100):
    """Find elbow: maximum deceleration point in variance ratio curve."""
    n = len(variance_ratio)
    if n <= min_pcs:
        return n
    d2 = np.diff(variance_ratio, n=2)
    if len(d2) == 0:
        return min(max_pcs, n)
    search_start = max(0, min_pcs - 2)
    if search_start >= len(d2):
        return min(max_pcs, n)
    sub_d2 = d2[search_start:]
    elbow = int(np.argmax(sub_d2)) + search_start + 2
    return max(min_pcs, min(elbow, max_pcs, n))
```

**Why second derivative?** The elbow is where the curve transitions from steep to flat. The second derivative measures the rate of change of the slope — its maximum is the point of maximum deceleration.

**Key detail:** Skip the first `min_pcs` PCs (they always carry high variance). The `+2` offset accounts for the two `np.diff` operations shifting indices.

## HVG Elbow Detection (n_top_genes)

Same second derivative approach on **sorted normalized dispersions** (descending).

```python
def detect_n_top_genes(dispersions_norm, min_genes=500, max_genes=5000):
    """Find elbow in sorted dispersion curve."""
    valid = dispersions_norm[np.isfinite(dispersions_norm)]
    sorted_disp = np.sort(valid)[::-1]
    # ... same d2 logic as detect_n_pcs ...
```

## Critical Fix: HVG Plot Must Show ALL Genes

**Bug:** If `sc.pp.highly_variable_genes(subset=True)` is called before plotting, the HVG plot shows only HVG genes — all appear as "highly variable", making the plot useless.

**Fix:** Call with `subset=False`, plot all genes (HVG highlighted in blue, non-HVG in grey), THEN subset:

```python
sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, subset=False)
# plot here — all genes visible
adata = adata[:, adata.var.highly_variable].copy()
# continue with scaling, PCA, etc.
```

## Visualization

### HVG Plot (two panels)
- **Left:** Scatter of mean expression vs normalized dispersion (grey=non-HVG, blue=HVG)
- **Right:** Sorted dispersion elbow curve with vertical line at recommended cutoff

### PCA Variance Plot (two panels)
- **Left:** Variance ratio bar chart with vertical line at elbow
- **Right:** Cumulative variance with elbow marker + percentage annotation

## CLI Integration

```python
# In argparse:
parser.add_argument("--auto-n-pcs", action="store_true")
parser.add_argument("--auto-n-top-genes", action="store_true")

# In mode_cluster:
pca_comps = max(n_pcs, 100) if auto_n_pcs else n_pcs  # run PCA with more components
sc.tl.pca(adata, n_comps=pca_comps)
if auto_n_pcs:
    n_pcs = detect_n_pcs(adata.uns["pca"]["variance_ratio"])
```

When `auto_n_pcs=True`, run PCA with `max(n_pcs, 100)` components to give the elbow detection enough data points, then use the detected value for downstream neighbors computation.
