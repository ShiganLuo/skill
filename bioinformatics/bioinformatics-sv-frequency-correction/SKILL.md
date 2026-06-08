---
name: bioinformatics-sv-frequency-correction
description: ML pipeline for correcting structural variant (SV) detection frequencies using ddPCR ground truth. Covers feature engineering (BAM-based read evidence, probe sequences, SV type encoding), calibration modeling for small-label scenarios, and data preprocessing pitfalls.
trigger:
  - SV frequency correction or calibration
  - ddPCR vs detection software comparison
  - Structural variant feature extraction from BAM files
  - Small-label regression in genomics
  - One-hot encoding for SV types (FusionType)
---

# SV Frequency Correction Pipeline

Correct software-detected SV mutation frequencies (e.g. OncoTop) against ddPCR ground truth.

## Domain Context

- **Input**: SV detection results with breakpoints (Pos1, Pos2), detected frequency (Freq), SV type (FusionType), BAM paths
- **Output**: Calibrated frequency closer to ddPCR true value
- **Challenge**: Very few labeled samples (ddPCR), large unlabeled detection pool, many records lack sample IDs

### SV Types (FusionType one-hot categories)

```
CTX-1, CTX-2, DEL/ITX, DUP/ITX, INV
```

Encoded as `sv_type_CTX-1`, `sv_type_CTX-2`, `sv_type_DEL/ITX`, `sv_type_DUP/ITX`, `sv_type_INV` binary columns.

## Feature Engineering

Features are extracted at the **mutation level** (not read level), matching ddPCR label granularity.

### BAM-based features (per breakpoint)
- depth_left, depth_right, depth_center, depth_sum, depth_diff, depth_asymmetry
- read_total_unique, read_support_unique, read_support_fraction
- read_mapq_mean, read_mapq_max
- read_softclip_fraction, read_split_fraction, read_discordant_fraction
- read_template_mean, read_template_std, read_breakpoint_balance

### Mutation-level aggregates
- same_chrom, sv_span
- bp_support_max, bp_depth_min, bp_depth_asymmetry_mean

### Probe/sequence features
- probe_count, probe_len_mean, probe_gc_mean, probe_entropy_mean
- probe_longest_homopolymer_mean, probe_n_fraction_mean, probe_gc_std

### SV type one-hot
- Enabled by including `"FusionType"` in `infile_columns`
- Generates 5 binary columns via `encode_sv_type()`

## Calibration Modeling Strategies

When labeled data is tiny (~26 samples):

1. **Baseline**: Per-type linear calibration `log(Freq_true) = a * log(Freq_detected) + b`
2. **Tree models**: XGBoost/LightGBM with strong regularization, LOO-CV
3. **Bayesian regression**: Prior that corrected ≈ detected, posterior updated by ddPCR

**Semi-supervised approaches are NOT recommended** for this task — unlabeled data lacks ground truth so it cannot directly help learn the correction mapping. Use unlabeled data only for distribution analysis.

## Key Functions

### `parser_table()` — Feature extraction

Location: `sv_freq_correction/features.py`

```python
# With SV type one-hot encoding:
parser_table(
    infile="data.tsv",
    probe_infile="probes.bed",
    infile_columns=["BamPath", "Pos1", "Pos2", "FusionType"],  # add FusionType
    extra_keep_cols=["Original_ID", "mutation", "ddPCR_AF", "Freq"],
)
```

Default `infile_columns=["BamPath", "Pos1", "Pos2"]` — add `"FusionType"` to enable one-hot. Generated columns: `sv_type_CTX-1`, `sv_type_CTX-2`, `sv_type_DEL/ITX`, `sv_type_DUP/ITX`, `sv_type_INV`.

### `preprocess_features()` — Feature preprocessing

Location: `sv_freq_correction/features.py`

Steps: (1) Standard scaling (skip `no_scale_columns`), (2) VarianceThreshold filtering, (3) correlation-based dropping (keep highest-variance representative).

Key parameters:
- `no_scale_columns`: list of columns to skip during StandardScaler (e.g. one-hot columns). These still participate in variance filtering and correlation dropping.
- `keep_columns`: non-feature columns preserved as-is in output (e.g. labels, IDs).

### `apply_preprocessing()` — Apply saved preprocessing to new data

Loads saved scaler + metadata, applies same scaling/filtering. Respects `no_scale_columns` from metadata. Backward-compatible with old metadata (no `no_scale_columns` field → scale everything).

## Pitfalls

### P1: `pandas.isin()` with NaN

`Series.isin()` treats NaN specially: NaN in the **values list** is silently dropped, but NaN in the **calling Series** is NOT matched. This means:

```python
# If ddPCR["原始编号"] contains NaN:
df_map[df_map["原始编号"].isin(ddPCR["原始编号"])]
# NaN rows in ddPCR won't match anything → safe but silent

# If df_map["原始编号"] contains NaN:
# NaN rows in df_map are NEVER matched, even if NaN exists in the values list
# This can silently exclude valid rows
```

**Fix**: Always `dropna()` on the filter column before `.isin()`, or use explicit merge with NaN handling.

### P2: Label encoding for linear models

Do NOT use integer label encoding (DEL=0, DUP=1, ...) for linear models — it implies false ordinal relationships. Use one-hot encoding instead. Tree models can handle label encoding since they split, not combine linearly.

### P3: Collecting data — output must include source data

When filtering a mapping table using another table's IDs, ensure the output retains the actual data columns, not just the filtered mapping columns. A common bug: filtering `df_map` by `df_ddPCR` IDs but only outputting map columns, losing all ddPCR data.

### P4: Clustering-then-modeling

Splitting data by cluster → training per-cluster models adds a **cascade error** (cluster misassignment → wrong model). For small datasets, prefer adding cluster/type info as features to a single model.

### P5: One-hot features must not be standardized

`StandardScaler` on binary one-hot columns shifts and scales them, destroying their meaning (0/1 → non-integer values). Use `preprocess_features(no_scale_columns=[...])` to exclude them from scaling while keeping them in variance filtering and correlation dropping.

```python
sv_type_cols = [c for c in df.columns if c.startswith("sv_type_")]
df_feature, diagnostics = preprocess_features(
    df, feature_cols, outdir=outdir,
    keep_columns=keep_cols,
    no_scale_columns=sv_type_cols,
)
```

The metadata saves `no_scale_columns` and `scale_column_indices` so `apply_preprocessing()` respects the same split at prediction time. Backward-compatible: old metadata without these fields defaults to scaling all columns.

## Data Collection

`collect_data.py` handles:
- `collect_OncoTop_sv()`: Extract SV sheet from OncoTop Excel/TSV
- `collect_ddPCR_data()`: Map ddPCR sample IDs to sequence/task IDs via mapping table
- `judge_ddPCR_data()`: Compare ddPCR labels with SV detection results via merge on `[原始编号, FusionGene, FusionExon]`. Saves two files:
  - `{outprefix}_SV_comparison.tsv` — matched records (ddPCR left join SV)
  - `{outprefix}_SV_no_ddPCR.tsv` — SV records with no ddPCR entry (anti-join)
