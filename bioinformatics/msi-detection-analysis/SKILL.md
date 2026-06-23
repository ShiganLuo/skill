---
name: msi-detection-analysis
description: >
  MSI (Microsatellite Instability) detection analysis pipeline — collecting results from
  msisensor-pro/TopMSI, threshold determination, per-cancer stratification, ROC evaluation,
  and prediction on unlabeled cohorts.
tags: [msi, microsatellite, bioinformatics, cancer, threshold, roc, msisensor-pro]
triggers:
  - MSI detection or analysis
  - msisensor-pro results processing
  - microsatellite instability threshold
  - cancer-type stratified analysis
  - ROC threshold optimization
---

# MSI Detection Analysis

End-to-end pipeline for MSI detection using sequencing data, covering result collection,
threshold determination, cancer-type stratification, and cohort prediction.

## Workflow Overview

```
1. Collect results (msisensor-pro .msi files / TopMSI site files)
2. Merge with sample metadata (MSI_status, cancer type, origin)
3. Threshold study on labeled training set (e.g. BL tissue samples)
4. Per-cancer stratification (different cancers need different thresholds)
5. Validate on independent labeled set (e.g. PCR)
6. Predict on unlabeled cohorts (e.g. renqun / blood samples)
```

## Key Concepts

### MSI%
MSI% = unstable loci / total valid loci × 100%. This is the primary score from msisensor-pro
and similar tools. It measures the fraction of microsatellite loci showing length instability.

### Cancer Type Matters
MSI signal strength varies dramatically by cancer type:
- **CRC**: MSI-H mean ~14%, MSS mean ~6.5%, AUC ~0.97 (excellent separation)
- **Endometrial**: MSI-H mean ~9.5%, MSS mean ~6.5%, AUC ~0.91 (moderate separation)
- MSS baseline is similar across cancer types (~6-7%); MSI-H mean varies widely
- **Always stratify by cancer type** — a single threshold across cancers is suboptimal

### Threshold Determination
Use Youden's J statistic (sensitivity + specificity - 1) from ROC curve on labeled training data.
For each cancer type separately:
1. Compute ROC: sort by score descending, accumulate TP/FP rates
2. Find threshold maximizing J = TPR - FPR
3. Evaluate at that threshold: sensitivity, specificity, accuracy, PPV, NPV

### msisensor-pro Architecture
- **scan**: enumerate microsatellite loci in reference genome
- **msi**: paired tumor-normal mode (chi-squared test + BH-FDR)
- **baseline**: build per-locus threshold from normal samples (mean + 3σ of pro_p)
- **pro**: tumor-only mode using Hunter method (pro_p = deletion_signal / total_signal)

Hunter method: `pro_p = delValue / (normalValue + delValue + insertValue)`
- pro_p quantifies what fraction of reads show length deviation from reference
- Unstable if pro_p > threshold (from baseline or hard cutoff)

## Data Structure

### msisensor-pro output per sample
```
<sample>.msi          # MSI score: total_sites, unstable_sites, MSI%
<sample>.msi_all      # All loci with details
<sample>.msi_unstable # Unstable loci only
<sample>.msi_dis      # Length distributions
```

### TopMSI output per sample
Site file (TSV) with columns: chromosome, location, repeat_unit_length,
repeat_unit_binary, repeat_times, flanks, depth, repeat distribution...

## Pitfalls

1. **Do NOT use one threshold across cancer types** — CRC and Endometrial need different
   thresholds (8.4% vs 7.2% in tested data). MSS baseline is similar but MSI-H signal varies.

2. **matplotlib CJK font issue** — On servers without CJK fonts, Chinese characters in
   plot labels/titles render as boxes. Always use English labels for figures.

3. **Large directory scanning** — `glob.glob()` is extremely slow on NFS with 5000+
   subdirectories (minutes). Use `os.scandir()` instead — it's 10-100x faster.

4. **ROC without sklearn** — If sklearn is not available, implement manually:
   ```python
   sorted_idx = np.argsort(-y_score)
   tps = np.cumsum(y_true[sorted_idx])
   fps = np.cumsum(1 - y_true[sorted_idx])
   tpr = np.concatenate([[0], tps / tps[-1]])
   fpr = np.concatenate([[0], fps / fps[-1]])
   thresholds = np.concatenate([[y_score[sorted_idx][0] + 1], y_score[sorted_idx]])
   ```

5. **conda activation in terminal** — `source conda.sh && conda activate` may fail silently
   in background processes. Use full path to python binary instead:
   `/path/to/miniforge3/envs/ENV/bin/python script.py`

6. **Renqun (blood) samples** — labels may be unreliable. Use labeled tissue samples (BL)
   for training, PCR for validation, renqun only for prediction.

## Script Templates

### collect_results.py pattern
```python
# Efficient directory scanning
for entry in os.scandir(result_dir):
    if entry.is_dir():
        sample_id = entry.name
        msi_file = os.path.join(entry.path, f"{sample_id}.msi")
        # parse...
```

### Sample ID extraction from bam_path
```python
def extract_sample_id(bam_path):
    basename = os.path.basename(bam_path)
    if "_cancer" in basename:
        return basename.split("_cancer")[0]
    return None
```

### Merge pattern
```python
meta["sample_id"] = meta["bam_path"].apply(extract_sample_id)
merged = pd.merge(msi_df, meta, on="sample_id", how="inner")
```
