# MACS3 Cutoff Analysis Guide

## cutoff_analysis.txt Format

When `Params.macs3.cutoff_analysis: true`, MACS3 generates `{sample}_cutoff_analysis.txt` with columns:

| Column    | Meaning                                                                 |
|-----------|-------------------------------------------------------------------------|
| pscore    | -log10(p-value) threshold. Higher = more significant signal             |
| qscore    | -log10(q-value) threshold (BH/FDR corrected). Higher = fewer false positives |
| npeaks    | Number of peaks passing this threshold                                  |
| lpeaks    | Total length of all peaks (bp)                                          |
| avelpeak  | Average peak length (bp) = lpeaks / npeaks                              |

## Interpreting the Data

### Healthy Signal Pattern
```
pscore=6.6:  ~230 peaks, avelpeak~430bp  ← High confidence, stable
pscore=5.0:  ~410 peaks, avelpeak~370bp  ← Balanced (default threshold)
pscore=4.8:  ~831 peaks, avelpeak~261bp  ← Elbow point (noise starts)
pscore=2.7: 339K peaks, avelpeak~157bp   ← Noise flood
pscore=0.3: 332 peaks, avelpeak~6Mb      ← Meaningless mega-regions
```

### Red Flags
1. **Elbow point too early** (pscore>6.0): Weak enrichment, consider re-sequencing
2. **No clear elbow**: Sample may be noisy or antibody failed
3. **avelpeak >1000bp at high thresholds**: Possible broad marks (H3K27me3) or failed IP

## Determining Optimal Threshold

### Method 1: Elbow Point Analysis
The "elbow" is where npeaks increases sharply as threshold decreases.

Quantitative approach:
```python
import numpy as np
log_peaks = np.log10(npeaks)
second_deriv = np.diff(log_peaks, n=2)
elbow_idx = np.argmax(second_deriv) + 1
```

### Method 2: Default Thresholds
MACS3 defaults work well for most ChIP-seq:
- `--qvalue 0.05` (qscore=1.3) — standard FDR control
- `--pvalue 1e-5` (pscore=5.0) — stricter, fewer peaks

### Threshold Selection Guide
| Use Case                      | Threshold              | When to Use                     |
|-------------------------------|------------------------|---------------------------------|
| Conservative (strict)         | qscore=2.0 (q=0.01)   | Validation, few high-confidence |
| Balanced (default)            | qscore=1.3 (q=0.05)   | Most analyses                   |
| Liberal (sensitive)           | qscore=1.0 (q=0.10)   | Exploratory, may miss signals   |

## Visualization

Use `plot_cutoff_analysis.py` to visualize peak count trends:
```bash
python3 workflow/Omics/modules/macs3/bin/plot_cutoff_analysis.py \
  --input-files sample1_cutoff.txt sample2_cutoff.txt \
  --sample-names Sample1 Sample2 \
  --output cutoff_trends.png
```

The script plots:
- Left: Peak count vs -log10(p-value) (pscore)
- Right: Peak count vs -log10(q-value) (qscore)
- Y-axis log scale, X-axis inverted (high threshold left, low right)
