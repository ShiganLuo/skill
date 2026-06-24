# TopMSI: Baseline Construction & Prediction Workflow

Source: `workflow/gene/ML/MSI/TopMSI/TopMSI.py`

## CLI

```bash
# Build baseline from labeled samples
python TopMSI.py build \
    --infile TopMSI_BaselineSample_addpath.tsv \
    --cancertype 结直肠癌 \
    --output baseline.tsv \
    --keep-filtered   # optional: include filtered loci

# Predict MSI status for new samples
python TopMSI.py predict \
    --baseline baseline.tsv \
    --samples <dir_or_files> \
    --output predictions.tsv \
    --cutoff 0.2    # optional, default MSI_SCORE_CUTOFF=0.2
```

## BASELINE_HEADER (23 columns)

### Locus identity (cols 0-9, from site file template)
| Column | Name | Description |
|--------|------|-------------|
| 0 | chromosome | Chromosome |
| 1 | location | Genomic position |
| 2 | repeat_unit_length | Repeat unit length (bp) |
| 3 | repeat_unit_binary | Binary-encoded repeat unit |
| 4 | repeat_times | Reference repeat count |
| 5 | left_flank_binary | Binary left flank |
| 6 | right_flank_binary | Binary right flank |
| 7 | repeat_unit_bases | Repeat unit sequence |
| 8 | left_flank_bases | Left flank sequence |
| 9 | right_flank_bases | Right flank sequence |

### Sample statistics (cols 10-14)
| Column | Name | Description |
|--------|------|-------------|
| 10 | mss_spnum | Number of MSS samples at this locus |
| 11 | msih_spnum | Number of MSI-H samples at this locus |
| 12 | mu_mss | Mean weighted entropy of MSS samples |
| 13 | sigma_mss | Std of weighted entropy of MSS samples |
| 14 | mu_msih | Mean weighted entropy of MSI-H samples |

### Discrimination metrics (cols 15-19)
| Column | Name | Description |
|--------|------|-------------|
| 15 | sb | Between-class scatter (Fisher discriminant numerator) |
| 16 | sw_mss | Within-class scatter (MSS group) |
| 17 | maxacc_thr | Threshold at maximum accuracy (from ROC) |
| 18 | auc | Per-locus ROC AUC |
| 19 | max_accuracy | Maximum classification accuracy |

### Scoring (cols 20-22)
| Column | Name | Description |
|--------|------|-------------|
| 20 | accuracy | Classification accuracy (used as raw weight) |
| 21 | threshold | Detection threshold for repeat count deviation |
| 22 | weight | Normalized weight (0 = filtered out) |

## Weight Calculation

**Step 1: QC filter → zero**
- `determine_qc()`: if auc < 0.7 or max_accuracy < 0.7 → weight = 0
- If passes: weight = accuracy (initial)

**Step 2: Merge MSI-H and MSS weight maps**
- If either dataset has weight=0 for a locus → final weight = 0

**Step 3: Normalize**
```
total_weight = sum(all weights)
wnorm = pass_pos / total_weight
each weight *= wnorm
```
Result: sum of all weights = number of passing loci.

## Per-Locus Accuracy Calculation

```python
# get_weight(method='accuracy'):
pos_thr = detect_thr(remove_outliers(MSS_data))  # mean + 3*sigma of trimmed MSS
correct_mss = sum(scluster <= pos_thr)
correct_msi = sum(hcluster > pos_thr)
accuracy = (correct_mss + correct_msi) / (len(scluster) + len(hcluster))
```

## Threshold (col 21) Calculation

`detect_thr(v)` computes: `mean(trimmed_MSS) + N_SIGMA * std(trimmed_MSS)` where N_SIGMA=3.

Outlier removal uses IQR method (1.5 × IQR beyond Q1/Q3).

## Weighted Entropy (per sample per locus)

```python
alt_ratio = non_ref_reads / total_reads
entropy = Shannon_entropy(non_ref_repeat_distribution)
weighted_entropy = alt_ratio * entropy
```

## Prediction Logic

For each new sample:
1. Read site file → extract per-locus (ref_rep_leng, rep_count, depth)
2. For each baseline locus with weight > 0:
   - Skip if locus missing or depth < 100
   - Compute weighted_entropy
   - If weighted_entropy > baseline threshold → unstable
3. MSI score = Σ(unstable_loci_weight) / Σ(all_valid_loci_weight)
4. MSI score > 0.2 → MSI-H, else MSS

## Key Thresholds

| Constant | Value | Purpose |
|----------|-------|---------|
| AUC_THR | 0.7 | Minimum AUC to keep a locus |
| MAX_ACC_THR | 0.7 | Minimum max_accuracy to keep a locus |
| DEP_THR | 100 | Minimum depth per site per sample |
| LEAST_SAMP_NUM | 50 | Minimum valid samples per locus |
| N_SIGMA | 3 | Std devs for detection threshold |
| MSI_SCORE_CUTOFF | 0.2 | MSI-H vs MSS boundary |

## Pitfalls

1. **weight=0 loci are filtered by default** in predict — they don't contribute to MSI score
2. **Missing or low-depth loci** in a new sample are skipped (not counted as unstable)
3. **detect_thr uses trimmed MSS data** — outlier removal is critical to avoid inflated thresholds
4. **Accuracy and AUC thresholds (0.7) are fixed** — not cancer-type-specific in current implementation
