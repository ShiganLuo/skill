---
name: msi-detection
description: Microsatellite Instability (MSI) detection workflows — msisensor-pro usage, baseline construction, threshold determination, anomaly detection, cancer-type stratification.
tags: [msi, microsatellite, cancer, bioinformatics, msisensor-pro, anomaly-detection]
triggers:
  - MSI detection or analysis
  - msisensor-pro usage or results
  - microsatellite instability
  - MSI-H / MSS classification
  - MSI threshold determination
---

# MSI Detection

Microsatellite Instability (MSI) detection from NGS data. Covers msisensor-pro tool usage, result collection, threshold studies, and alternative detection approaches.

## Background

MSI is caused by defects in DNA mismatch repair (MMR). Microsatellite regions (short tandem repeats) accumulate length changes when MMR is deficient. MSI-H status is clinically relevant for immunotherapy response prediction.

### PCR Gold Standard (5 loci)
NCI recommends 5 loci: BAT-25, BAT-26, D2S123, D5S346, D17S250.
- ≥2 unstable → MSI-H
- 1 unstable → MSI-L
- 0 unstable → MSS

Why these work: long single-nucleotide repeats (BAT-25/26) have near-100% instability rate in MMR-deficient tumors. Direct length measurement via capillary electrophoresis, no statistical inference needed.

### msisensor-pro
Source: C++ tool from xjtu-omics (Peng Jia, Kai Ye).

Subcommands:
- `scan` — scan reference genome for microsatellite loci
- `msi` — paired tumor-normal detection (chi-squared test + BH-FDR)
- `baseline` — build baseline from normal samples for tumor-only mode
- `pro` — tumor-only detection using Hunter method

**Hunter method** (pro mode): computes `pro_p = delValue / (normalValue + delValue + insertValue)` per locus. Higher pro_p = more length deviation = more likely unstable.

Baseline threshold: `mean + 3*sigma` of pro_p across normal samples per locus.

Output files per sample:
- `.msi` — summary (Total_Sites, Unstable_Sites, MSI%)
- `.msi_all` — all valid loci with pro_p, pro_q, coverage, threshold
- `.msi_unstable` — unstable loci only
- `.msi_dis` — full distribution data

## Typical Workflow

```
1. scan → reference genome → locus list
2. baseline → normal samples → per-locus thresholds
3. pro → tumor BAM + baseline → MSI status
4. collect results → merge with metadata → analysis
```

## Data Processing Patterns

### Collecting msisensor-pro Results
Use `os.scandir()` (not `glob.glob()`) for large directories — much faster on NFS with thousands of subdirectories.

```python
def collect_results(result_dir):
    rows = []
    for entry in os.scandir(result_dir):
        if entry.is_dir():
            sample_id = entry.name
            msi_file = os.path.join(entry.path, f"{sample_id}.msi")
            if os.path.isfile(msi_file):
                # parse 2-line file: header + data
                ...
```

### Extracting Sample IDs
Common pattern: extract from bam_path by splitting on `_cancer`:
```python
sample_id = os.path.basename(bam_path).split("_cancer")[0]
```

### Threshold Study
Split data by origin:
- **BL** (tissue): training set with reliable labels
- **PCR**: independent validation (small n)
- **renqun** (blood): prediction only (labels may be unreliable)

Per-cancer-type analysis is critical — MSI-H signal strength varies dramatically:
- CRC: MSI-H mean ~14%, AUC ~0.97
- Endometrial: MSI-H mean ~9%, AUC ~0.91

## Key Metrics

| Metric | Formula | Use |
|--------|---------|-----|
| MSI% | unstable_sites / total_sites * 100 | Primary score |
| pro_p | del_signal / total_signal | Per-locus instability |
| AUC | ROC curve area | Discrimination power |
| Youden's J | sensitivity + specificity - 1 | Optimal threshold |

## site.txt Format (TopMSI)

Column indices (0-based):
```
0: chromosome
1: location
2: repeat_unit_length
3: repeat_unit_binary
4: repeat_times        ← reference repeat count
5: left_flank_binary
6: right_flank_binary
7: repeat_unit_bases
8: left_flank_bases
9: right_flank_bases
10: repeat_dict        ← distribution "repeat:count,repeat:count,..."
11: depth              ← total reads
```

**Critical**: `repeat_times` (col 4) is the REFERENCE count. The distribution in col 10 uses OBSERVED counts. To compute alt_ratio:
```python
ref_count = counts.get(repeat_times, 0)  # NOT the max or mode
alt_ratio = 1 - ref_count / depth
```

## Anomaly Detection Approach

Instead of fixed MSI% threshold, model "normal" distribution and detect deviations.

### Key Insight: Locus Selection > Feature Engineering

Single-feature (msi_pct) AUC can reach 0.97. Multi-feature anomaly detection often performs WORSE because:
1. Non-sensitive loci dilute the signal
2. Coverage features dominate, learning "sample quality" not "MSI signal"
3. High-dimensional space is sparse with limited training data

**Priority**: Select sensitive loci FIRST, then engineer features.

### Modular Pipeline Architecture

```python
class MSIDetectionPipeline:
    feature_extractor: FeatureExtractor   # site.txt → features
    locus_selector: LocusSelector         # select sensitive loci
    feature_selector: FeatureSelector     # select sample-level features
    sample_filter: SampleFilter           # filter low-quality samples
    detector: Detector                    # anomaly detection algorithm
```

### Locus Selection Methods

1. **AUC-based**: Compute per-locus AUC across labeled samples, keep AUC >= 0.6
2. **Unit length filter**: Only keep unit_len in [1, 2, 3]
3. **Combined**: AUC filter + unit length filter

### Feature Extraction (from site.txt)

Per-locus features:
- `alt_ratio` = 1 - ref_count/depth (key feature, AUC ~0.98)
- `entropy` = Shannon entropy of repeat distribution
- `max_shift` = max |observed - reference| repeat count

Sample-level aggregation:
- mean, max, median, quantiles of per-locus features
- Ratios by unit length (unit1, unit2, unit3)
- High-alt-ratio locus proportion

### Algorithms (no sklearn needed)

- Mahalanobis distance (assumes multivariate Gaussian)
- Z-score based (per-feature max deviation)
- PCA reconstruction error

## Cancer Type Effects

Cancer type significantly affects MSI detection performance:

| Cancer | MSI-H Rate | Signal Strength | Detection Difficulty |
|--------|-----------|----------------|---------------------|
| CRC | ~15% | Strong | Easy |
| Endometrial | ~20-30% | Medium | Moderate |
| Gastric | ~10-20% | Medium | Moderate |
| Lung | <5% | Weak | Hard |

**Implication**: Build cancer-specific thresholds, not one-size-fits-all.

## Pitfalls

1. **site.txt column indexing** — `repeat_times` (col 4) is reference, NOT observed. Using wrong column for alt_ratio calculation produces features with zero discrimination (AUC=0.5). The distribution in col 10 uses observed counts as keys.
2. **Coverage features dominating** — anomaly detection may learn "sample quality" not "MSI signal". Remove or exclude coverage-related features.
3. **Locus selection critical** — Using all ~572 loci dilutes signal. AUC-based locus selection (keep loci with AUC >= 0.6) dramatically improves performance.
4. **Single feature can beat multi-feature** — msi_pct (unstable locus ratio) AUC=0.97. Multi-feature anomaly detection often performs worse due to noise and dimensionality.
5. **Chinese characters in matplotlib** — server lacks CJK fonts, use English labels
6. **glob.glob() on large NFS directories** — extremely slow, use os.scandir() instead
7. **PCR validation with tiny n** — 7 samples cannot validate anything statistically
8. **renqun labels unreliable** — use for prediction only, not training
9. **Cancer type matters** — CRC AUC=0.97 vs Endometrial AUC=0.91. Build cancer-specific thresholds.

## Code Style Notes

- numpy-style docstrings (English)
- f-strings for formatting
- `argparse` with subcommands for CLI
- `os.scandir()` over `glob.glob()` for performance
- Avoid sklearn dependency when scipy/numpy suffices
- English labels in all plots (no Chinese on server)

## References

- `references/msisensor-pro-source-analysis.md` — msisensor-pro source code analysis
- `references/site-txt-format-and-parsing.md` — site.txt column layout and feature extraction
- `references/modular-pipeline-architecture.md` — pluggable MSI detection pipeline design
