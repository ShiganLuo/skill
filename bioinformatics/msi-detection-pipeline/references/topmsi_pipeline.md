# TopMSI Pipeline Reference

Custom MSI detection pipeline using weighted entropy and per-locus baselines.

## Key Differences from msisensor-pro

| Aspect | msisensor-pro | TopMSI |
|--------|---------------|--------|
| Metric | pro_p (deletion ratio) | weighted_entropy = alt_ratio × Shannon_entropy |
| Baseline | mean + 3σ of pro_p | mean + 3σ of trimmed MSS entropy |
| Locus filter | support_num ≥ 10 | AUC ≥ 0.7 AND accuracy ≥ 0.7 |
| Weighting | None (count-based) | Per-locus accuracy-based weights |
| Final score | unstable_count / total | Σ(weight × unstable) / Σ(weight) |

## BASELINE_HEADER Columns (23 total)

### Locus Identity (cols 0-9) — from site file template
| Col | Name | Description |
|-----|------|-------------|
| 0 | chromosome | Chromosome |
| 1 | location | Genomic position |
| 2 | repeat_unit_length | Repeat unit length (bp) |
| 3 | repeat_unit_binary | Binary encoding of repeat unit |
| 4 | repeat_times | Reference repeat count |
| 5 | left_flank_binary | Left flank binary encoding |
| 6 | right_flank_binary | Right flank binary encoding |
| 7 | repeat_unit_bases | Repeat unit bases (e.g. "A", "CA") |
| 8 | left_flank_bases | Left flank sequence |
| 9 | right_flank_bases | Right flank sequence |

### Sample Statistics (cols 10-14)
| Col | Name | Description |
|-----|------|-------------|
| 10 | mss_spnum | Number of MSS samples at this locus |
| 11 | msih_spnum | Number of MSI-H samples at this locus |
| 12 | mu_mss | Mean weighted entropy of MSS (after outlier removal) |
| 13 | sigma_mss | Std of weighted entropy of MSS (after outlier removal) |
| 14 | mu_msih | Mean weighted entropy of MSI-H |

### Discrimination Metrics (cols 15-19)
| Col | Name | Description |
|-----|------|-------------|
| 15 | sb | Between-class scatter (Sb) |
| 16 | sw_mss | Within-class scatter of MSS (Sw) |
| 17 | maxacc_thr | Threshold at which max accuracy is achieved (from ROC) |
| 18 | auc | ROC AUC for this locus |
| 19 | max_accuracy | Maximum classification accuracy (from ROC curve) |

### Final Scoring (cols 20-22)
| Col | Name | Description |
|-----|------|-------------|
| 20 | accuracy | Classification accuracy at detect_thr threshold |
| 21 | threshold | Detection threshold: mean(MSS_trimmed) + 3σ |
| 22 | weight | Normalized weight (0 = filtered out) |

## Baseline Construction Flow

1. collect_data(msih_files) → per-locus weighted entropy values
2. collect_data(mss_files) → per-locus weighted entropy values
3. Per locus:
   - optimal_cutoff_from_roc(scluster, hcluster) → maxacc, threshold
   - get_weight(method='auc') → w_auc
   - determine_qc(pos, w_auc, maxacc) → pass/fail (auc ≥ 0.7 AND maxacc ≥ 0.7)
   - remove_outliers(scluster) → trimmed MSS
   - detect_thr(trimmed) = mean + 3σ → threshold
4. Weight calculation (3 steps):
   a. QC filter: if determine_qc fails → weight=0; else weight=accuracy
   b. Merge MSI-H/MSS: either side zeroed → stays zero; else take MSS weight
   c. Normalize: wnorm = pass_pos / Σweight; each weight *= wnorm → Σweight = pass_pos

### Weight Calculation Detail

The `accuracy` used as raw weight is computed by `get_weight(method='accuracy')`:
```python
pos_thr = detect_thr(remove_outliers(MSS_data))   # mean + 3σ
correct_mss = count(MSS ≤ pos_thr)
correct_msi = count(MSI-H > pos_thr)
accuracy = (correct_mss + correct_msi) / total_samples
```

Other available metrics in `get_weight()`:
- `'sb'`: between-class scatter (Sb)
- `'sw_mss'`: within-class scatter of MSS (Sw)
- `'distance'`: Fisher-like ratio Sb / Sw_mss
- `'overlap'`: fraction of overlapping samples
- `'auc'`: ROC AUC
- `'sensitivity'`: MSI-H detection rate
- `'specificity'`: MSS rejection rate

### Weighted Entropy Formula

```python
def get_statistic(ref_rep_leng, rep_count):
    # Separate reference and alternative counts
    ref_count = rep_count.get(ref_rep_leng, 0)
    alt_count = {k: v for k, v in rep_count.items() if k != ref_rep_leng}
    total = max(1, ref_count + sum(alt_count.values()))

    alt_ratio = sum(alt_count.values()) / total
    entropy = scipy.stats.entropy(list(alt_count.values()), base=2)

    return alt_ratio, alt_ratio * entropy  # weighted entropy
```

## Prediction Flow

1. load_baseline() → per-locus threshold and weight (only weight > 0 kept)
2. Per sample:
   - Read site file → per-locus (ref_rep_leng, rep_count, depth)
   - Skip loci: missing or depth < 100
   - Per locus: compute weighted_entropy, compare against threshold
   - MSI_score = Σ(weight × I(entropy > threshold)) / Σ(weight)
   - MSI-H if score > MSI_SCORE_CUTOFF (default 0.2)

### CLI Usage

```bash
# Build baseline
python TopMSI.py build --infile sample_info.tsv --output baseline.tsv --cancertype 结直肠癌

# Predict
python TopMSI.py predict --baseline baseline.tsv --samples /path/to/sites/ --output pred.tsv --cutoff 0.2
```

## Cancer Type Impact (from threshold study)

| Cancer | n | MSI-H mean | MSS mean | Delta | AUC | Threshold |
|--------|---|-----------|----------|-------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 7.53 | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 3.01 | 0.912 | 7.24% |

Key insight: MSS baseline is similar across cancer types (~6.5%), but MSI-H signal varies greatly.

## Module-Level Thresholds (TopMSI.py constants)

| Constant | Value | Description |
|----------|-------|-------------|
| SAMP_MEAN_DEP_THR | 100 | Mean depth threshold for sample QC |
| MAX_REP_TIMES | 50 | Maximum repeat times |
| MIN_REP_TIMES | 5 | Minimum repeat times |
| DEP_THR | 100 | Per-site depth threshold |
| LEAST_SAMP_NUM | 50 | Minimum valid samples per locus |
| AUC_THR | 0.7 | Minimum AUC to keep a locus |
| MAX_ACC_THR | 0.7 | Minimum max-accuracy to keep a locus |
| N_SIGMA | 3 | Std deviations for detection threshold |
| MSI_SCORE_CUTOFF | 0.2 | MSI-H classification cutoff |
