---
name: msi-detection-pipeline
description: >
  Microsatellite Instability (MSI) detection from NGS data — baseline construction,
  threshold determination, result aggregation, and cancer-type-stratified analysis.
  Covers msisensor-pro and custom TopMSI pipelines.
category: bioinformatics
tags: [msi, microsatellite, bioinformatics, oncology, liquid-biopsy, ctDNA]
---

# MSI Detection Pipeline

Build, evaluate, and deploy MSI detection workflows for cancer genomics.

## When to use

- User asks about MSI detection, microsatellite instability, or related analysis
- Working with msisensor-pro or TopMSI tools
- Building MSI baselines, thresholds, or evaluation pipelines
- Analyzing MSI results across cancer types or sample types (tissue vs blood)
- Working with somatic mutation QC (contamination, index matching, pair verification)

## Core Concepts

### MSI Biology
- Microsatellites: short tandem repeats (1-6 bp units), repeated 5-50+ times
- MSI occurs when mismatch repair (MMR) is deficient → repeat length changes
- MSI-H (high instability) is a biomarker for immunotherapy response

### Two Detection Paradigms

**Paired mode** (tumor + normal):
- Compare length distributions between tumor and normal at each locus
- Chi-squared test + BH-FDR correction
- MSI score = unstable loci / total loci × 100%
- Threshold: typically ≥10% → MSI-H

**Tumor-only mode** (no matched normal):
- Compute pro_p = deletion_signal / total_signal per locus (Hunter method)
- Compare against baseline thresholds (mean + 3σ from normal population)
- Requires pre-built baseline from multiple normal samples

### Key Metrics per Locus
- `weighted_entropy` = alt_ratio × Shannon_entropy(non-ref distribution)
- `pro_p` = delValue / (normalValue + delValue + insertValue)
- `threshold` = mean(MSS_trimmed) + 3 × std(MSS_trimmed)

## Pipeline Stages

### 1. Reference Scan
Scan genome for microsatellite loci (repeat unit 1-6bp, repeat count ≥5-50).
Output: locus list with chromosome, position, repeat_unit, repeat_count, flanking sequences.

### 2. Baseline Construction
From labeled MSI-H and MSS samples:
- Compute per-locus weighted entropy or pro_p
- Filter loci: depth ≥100, sample count ≥50, AUC ≥0.7, accuracy ≥0.7
- Threshold = mean(MSS trimmed) + 3σ
- Weight calculation (3 steps):
  1. QC filter: if determine_qc fails → weight=0; else weight=accuracy
  2. Merge MSI-H/MSS: either side zeroed → stays zero; else take MSS weight
  3. Normalize: wnorm = pass_pos / Σweight; each weight *= wnorm → Σweight = pass_pos

### 3. Prediction
For each new sample:
- Compute entropy/pro_p at each baseline locus
- Compare against threshold → unstable or stable
- MSI_score = Σ(weight[i] × unstable[i]) / Σ(weight[i])
- MSI-H if score > cutoff (default 0.2)

### 4. Evaluation
- Split by cancer type (CRITICAL — see pitfalls)
- ROC analysis, Youden's J for optimal threshold
- Per-cancer metrics: sensitivity, specificity, AUC

## Pitfalls

### Cancer type has massive impact on MSI detection
- CRC MSI-H mean ~14%, MSS ~6.5% → AUC 0.97
- Endometrial MSI-H mean ~9.5%, MSS ~6.5% → AUC 0.91
- **Always stratify by cancer type** when building baselines or determining thresholds
- One-size-fits-all thresholds perform poorly across cancer types

### Blood (ctDNA) vs Tissue
- Blood MSI signal is much weaker (low tumor fraction)
- MSI-H and MSS distributions overlap heavily in blood
- Tissue-based thresholds do NOT transfer to blood samples
- Consider separate baseline per sample type

### Reagent/Panel effects
- Different capture kits have different efficiency at microsatellite regions
- Sequencing depth varies by panel design
- Build baselines per assay system, not across systems

### Logging format pitfall (Python)
- `%(logger_name)s` is NOT a valid logging format field
- Correct field: `%(name)s` for logger name
- Common bug in custom LogUtil modules

### Bam path resolution
- Different sample types (BL, PCR, renqun) may have different path structures
- Use modular resolver functions with clear prefix matching
- Always verify bam existence (os.path.isfile), return None if missing

## site.txt Format (CRITICAL)

### Columns (0-indexed)
| Index | Name | Description |
|-------|------|-------------|
| 0 | chromosome | Chromosome |
| 1 | location | Genomic position |
| 2 | repeat_unit_length | 1=homopolymer, 2-6=microsatellite |
| 3 | repeat_unit_binary | Binary encoding |
| 4 | repeat_times | **REFERENCE** repeat count |
| 5 | left_flank_binary | Left flank binary |
| 6 | right_flank_binary | Right flank binary |
| 7 | repeat_unit_bases | e.g., "AC", "GAA" |
| 8 | left_flank_bases | Left flank sequence |
| 9 | right_flank_bases | Right flank sequence |
| 10 | repeat_dict | "obs_count:reads,obs_count:reads,..." |
| 11 | depth | Total read depth |

### CRITICAL PITFALL: Column Index
- `repeat_times` (col 4) is the **REFERENCE** count, NOT observed!
- `repeat_dict` (col 10) has **OBSERVED** counts
- alt_ratio = 1 - counts.get(repeat_times, 0) / depth
- **DO NOT** confuse col 3 (unit_binary) with repeat_times!
- **DO NOT** use col 4 as observed count — it's the reference!
- Bug: using wrong column → AUC=0.5 (random). Correct columns → AUC=0.97

### Feature Extraction
```python
# Correct feature extraction
repeat_times = int(row[4])      # col 4 = reference repeat count
dist_str = str(row[10])         # col 10 = observed distribution
depth = int(row[11])            # col 11 = depth

counts = {}
for item in dist_str.split(','):
    k, v = item.split(':')
    counts[int(k)] = int(v)

ref_count = counts.get(repeat_times, 0)  # reference count in observed dist
alt_ratio = 1 - ref_count / depth
```

## Anomaly Detection

### Approach
- Train on MSS samples only (normal distribution)
- Mahalanobis distance: d = sqrt((x-μ)ᵀ Σ⁻¹ (x-μ))
- Threshold: mean + n_sigma × std

### Features (19 total)
- Overall: mean_alt, max_alt, mean_entropy, max_entropy, mean_shift, max_shift, high_alt_ratio
- By unit length (1,2,3): alt_unit1/2/3, entropy_unit1/2/3

### Pitfalls
1. **Remove coverage features** — they dominate and measure sample quality, not MSI signal
2. **High-dimensional curse** — 15+ features with only 200-300 MSS → poor estimation
3. **Single-feature often beats multi-feature** — msi_pct alone AUC=0.969 vs anomaly AUC=0.94
4. **Wrong column indices** → AUC=0.5 (random). Always verify with a few samples first!

### Performance (this dataset)
- msi_pct threshold: AUC=0.969 (CRC), 0.912 (Endometrial)
- Anomaly detection: AUC=0.945 (BL), worse than single feature
- **Conclusion**: msi_pct is already a very good feature; multi-feature doesn't help much

## Code Patterns

### Threshold determination (ROC-based)
```python
# Manual ROC (no sklearn dependency)
sorted_idx = np.argsort(-y_score)
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = tps / tps[-1]
fpr = fps / fps[-1]
# Youden's J
j = tpr - fpr
best_threshold = thresholds[np.argmax(j)]
```

### Result aggregation pattern
```python
# Collect per-sample results from directory structure
for entry in os.scandir(result_dir):
    if entry.is_dir():
        sample_id = entry.name
        result_file = os.path.join(entry.path, f"{sample_id}.msi")
        # parse and collect
```

### Sample ID extraction from bam path
```python
def extract_sample_id(bam_path):
    basename = os.path.basename(bam_path)
    if "_cancer" in basename:
        return basename.split("_cancer")[0]
    return None
```

## References

- `references/msisensor_pro_source.md` — msisensor-pro v1.3.0 source code analysis, algorithms, data structures
- `references/topmsi_pipeline.md` — TopMSI baseline building, prediction, weight calculation, and cancer type threshold study results
- `references/somatic_qc_modules.md` — OncoWESuper QC modules: HomConsistency (index mismatch), PairCheck21 (pair verification), ContEstWES (cross-contamination)
- `references/feature_engineering.md` — bMSI data simulation, feature engineering, model training, BAM path resolution
