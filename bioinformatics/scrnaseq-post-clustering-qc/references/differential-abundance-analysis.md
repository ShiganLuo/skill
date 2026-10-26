# Differential Abundance Analysis for scRNA-seq

## Overview

When comparing cell type proportions between samples (e.g., different treatments, timepoints, or conditions), simple percentage comparison is insufficient. Statistical tests are needed to determine if observed differences are significant.

## Recommended Methods

### 1. Chi-square Test + Standardized Residuals (Simple, Good for Most Cases)

**When to use:** Quick analysis, comparing2 samples, publication-ready results.

```python
import numpy as np
from scipy import stats

def perform_da_analysis(adata, sample1, sample2):
    """Perform differential abundance analysis between two samples."""
    samples = [sample1, sample2]
    cell_types = sorted(adata.obs["cell_type"].unique())
    
    # Create contingency table
    contingency = []
    valid_cts = []
    for ct in cell_types:
        row = []
        for sample in samples:
            n = ((adata.obs["cell_type"] == ct) & (adata.obs["sample_id"] == sample)).sum()
            row.append(n)
        if sum(row) > 0:  # Only include cell types present in at least one sample
            contingency.append(row)
            valid_cts.append(ct)
    
    contingency = np.array(contingency)
    contingency = contingency + 0.5  # Pseudocount to avoid zeros
    
    # Chi-square test
    chi2, p_chi2, dof, expected = stats.chi2_contingency(contingency)
    
    # Calculate metrics for each cell type
    results = []
    for i, ct in enumerate(valid_cts):
        n1 = contingency[i, 0]
        n2 = contingency[i, 1]
        total1 = contingency[:, 0].sum()
        total2 = contingency[:, 1].sum()
        
        p1 = n1 / total1 if total1 > 0 else 0
        p2 = n2 / total2 if total2 > 0 else 0
        
        # Fold change
        if p1 > 0 and p2 > 0:
            fc = p2 / p1
            log2fc = np.log2(fc)
        else:
            fc = float("inf") if p2 > 0 else 0
            log2fc = float("inf") if p2 > 0 else float("-inf")
        
        # Fisher's exact test
        table = np.array([[n1, total1 - n1], [n2, total2 - n2]])
        _, pval = stats.fisher_exact(table)
        
        results.append({
            "cell_type": ct,
            "n_sample1": int(n1 - 0.5),
            "n_sample2": int(n2 - 0.5),
            "pct_sample1": p1 * 100,
            "pct_sample2": p2 * 100,
            "fc": fc,
            "log2fc": log2fc,
            "pvalue": pval,
        })
    
    return pd.DataFrame(results), chi2, p_chi2
```

### 2. Milo (Gold Standard, R Package)

**When to use:** Publication-quality analysis, comparing conditions/treatments, detecting subtle composition changes.

**Reference:** Dann E, Henderson NC, Teichmann SA, et al. Differential abundance testing on single-cell data using k-nearest neighbor graphs. Nature Biotechnology. 2022;40(2):245-253.

**R package:** `miloR`

**Advantages:**
- Considers cell transcriptomic similarity (not just cell type labels)
- Higher statistical power
- Can detect new cell states

### 3. propeller/speckle (Python-friendly)

**When to use:** Simple analysis, Python environment, already annotated data.

## Visualization

### Volcano Plot

```python
def plot_volcano(df, sample1, sample2, output_path):
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = []
    for _, row in df.iterrows():
        if row["pvalue"] < 0.001 and abs(row["log2fc"]) > 1:
            colors.append("#E64B35")  # Highly significant
        elif row["pvalue"] < 0.05 and abs(row["log2fc"]) > 0.5:
            colors.append("#F39B7F")  # Significant
        else:
            colors.append("#8491B4")  # Not significant
    
    ax.scatter(df["log2fc"], df["neg_log10p"], c=colors, s=100, alpha=0.7)
    
    # Add labels for significant cell types
    for _, row in df.iterrows():
        if row["pvalue"] < 0.001 and abs(row["log2fc"]) > 0.5:
            ax.annotate(row["cell_type"], (row["log2fc"], row["neg_log10p"]))
    
    ax.axhline(-np.log10(0.001), color="gray", linestyle="--", alpha=0.5)
    ax.axvline(-1, color="gray", linestyle="--", alpha=0.5)
    ax.axvline(1, color="gray", linestyle="--", alpha=0.5)
    
    ax.set_xlabel("log2(Fold Change)")
    ax.set_ylabel("-log10(p-value)")
    ax.set_title(f"Volcano Plot: {sample2} vs {sample1}")
```

### Heatmap of Changes

```python
def plot_heatmap(comparisons_data, title, output_path):
    all_cts = set()
    for comp_name, ct1, ct2 in comparisons_data:
        all_cts.update(ct1.index)
        all_cts.update(ct2.index)
    all_cts = sorted(all_cts)
    
    changes = []
    comp_names = []
    for comp_name, ct1, ct2 in comparisons_data:
        changes.append([ct2.get(ct, 0) - ct1.get(ct, 0) for ct in all_cts])
        comp_names.append(comp_name)
    
    changes = np.array(changes)
    fig, ax = plt.subplots(figsize=(14, 5))
    im = ax.imshow(changes, cmap="RdBu_r", aspect="auto", vmin=-30, vmax=30)
    # Add annotations, labels, colorbar
```

## Key Metrics to Report

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Chi-square p-value | Overall composition difference | < 0.05 |
| Standardized residual | Which cell types contribute most | \|z\| > 2 |
| Fold change | Magnitude of change per cell type | > 2 or < 0.5 |
| Fisher's exact p-value | Significance per cell type | < 0.001 |

## Example Results Format

```
Chi-square: 2284.30, p-value: 0.00e+00

Significant cell types (p < 0.001):
  ERVK_high           : FC=3.19, log2FC=1.67, p=3.49e-262 ↑
  Cumulus             : FC=2.91, log2FC=1.55, p=7.50e-39 ↑
  Smooth_muscle       : FC=0.29, log2FC=-1.80, p=1.25e-125 ↓
  Epithelial          : FC=0.01, log2FC=-6.41, p=5.84e-60 ↓
```
