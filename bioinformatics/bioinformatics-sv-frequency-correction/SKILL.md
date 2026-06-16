---
name: bioinformatics-sv-frequency-correction
description: ML pipeline for correcting structural variant (SV) detection frequencies using ddPCR ground truth. Covers feature engineering (BAM-based read evidence, probe sequences, SV type encoding), calibration modeling for small-label scenarios, and data preprocessing pitfalls.
trigger:
  - SV frequency correction or calibration
  - ddPCR vs detection software comparison
  - Structural variant feature extraction from BAM files
  - Small-label regression in genomics
  - One-hot encoding for SV types (FusionType)
  - Semi-supervised SV frequency correction with unlabeled data
  - Pseudo-label self-training for SV calibration
  - Denoising autoencoder for feature learning in genomics
  - Consistency regularization for small-label regression
  - parser_table feature cache sharing across scripts
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

## Semi-Supervised Learning with Unlabeled Data

When large unlabeled pools exist (e.g. 22K unlabeled vs 936 labeled rows), three approaches
can leverage the unlabeled data. All are implemented as standalone scripts alongside train.py.

See `references/semi_supervised.md` for implementation details, CLI usage, and pitfalls.

| Method | Script | Idea |
|--------|--------|------|
| Self-Training | `self_training.py` | Iterative pseudo-label generation → confidence filter → merge → retrain |
| Autoencoder | `semi_supervised_ae.py` | Denoising AE on all data → latent features → supervised regression |
| Consistency Reg | `consistency_reg.py` | Neural net with MSE + consistency loss (PyTorch) or ensemble-consistency (numpy fallback) |

### Shared data loading (`_data.py`)

`load_combined_features(labeled_tsv, unlabeled_tsv, outdir, feature_cache_dir=None)`
extracts BAM features for both datasets via `parser_table()`, combines them, runs
`preprocess_features()` on the merged matrix, and returns
`(labeled_df, combined_df, feature_columns, no_scale_columns)`. BAM extraction
results are cached to avoid re-processing. Pass `feature_cache_dir` to share the
cache across multiple scripts (see `references/semi_supervised.md` SP7).

### Key design decisions
- Pseudo-label weight = 0.5x labeled weight (conservative)
- Confidence filtering: combined strategy (range + residual + top-k) is safest
- Autoencoder uses denoising (Gaussian noise → reconstruct clean) for robustness
- Consistency regularization: PyTorch mode for gradient-level λ*con_loss; numpy fallback uses ensemble agreement
- All methods compare against a labeled-only baseline using the same train/test split
- Grouped train/test split via `--group-cols` (default, repeatable for composite keys)
- **Hyperparameter search**: `_fit_model_with_cv` uses `RandomizedSearchCV(n_iter=50)` for large grids (>50 combos), falling back to `GridSearchCV` for small grids. Default param grids are kept lean to avoid combinatorial explosion. See `references/semi_supervised.md` SP15.

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

### P6: `diagnostics` dict does NOT contain `processed_feature_columns`

`preprocess_features()` returns a `diagnostics` dict with keys:
`cond_before`, `min_sv_before`, `removed_by_variance`, `dropped_correlated`,
`correlation_clusters`, `cond_after`, `min_sv_after`.

The key `processed_feature_columns` is written to `preprocessing_metadata.json`
on disk but is **not** in the returned diagnostics dict. Using
`diagnostics.get("processed_feature_columns", [])` silently returns `[]`,
causing all numeric BAM features to be dropped (only sv_type one-hot survives).

**Fix**: Compute feature columns directly from the processed DataFrame:
```python
combined_processed, diagnostics = preprocess_features(combined, numeric_cols, ...)
# WRONG: diagnostics.get("processed_feature_columns", [])  → empty list
# RIGHT: read columns from the returned DataFrame
non_feature = set(META_COLUMNS) | {"_is_labeled"}
final_features = [c for c in combined_processed.columns
                  if c not in non_feature and pd.api.types.is_numeric_dtype(combined_processed[c])]
```

### P7: `parser_table(outdir=...)` creates duplicate files

`parser_table()` always writes to `{outdir}/raw_extracted_features.tsv` when `outdir`
is set. If the caller also saves the returned DataFrame to a separate cache path
(e.g. `labeled_raw_features.tsv`), you end up with two identical files in the same
directory.

**Fix**: Pass `outdir=None` to `parser_table()` so it only returns the DataFrame
without writing. Handle file writing yourself:
```python
df = parser_table(infile=tsv_path, outdir=None, extra_keep_cols=valid_keep, ...)
df.to_csv(cache_path, sep="\t", index=False)
```

### P8: `parser_table()` crashes on missing `extra_keep_cols`

`parser_table()` does `df = df[bam_columns + extra_keep_cols]` without checking
column existence. When the input TSV lacks a column listed in `extra_keep_cols`
(e.g. `ddPCR_AF` is absent from unlabeled data), this raises `KeyError`.

**Fix**: Filter `extra_keep_cols` against the input file's header before calling
`parser_table()`. Add missing columns as NaN after extraction. See
`references/semi_supervised.md` SP8 for the code pattern.

### P9: NaN group keys corrupt grouped splits

When `原始编号` (or other group column) has NaN values, `groups.astype(str)` converts
them to the string `"nan"`, which groups all NaN rows together as if they were one sample.
This corrupts both GroupShuffleSplit and GroupKFold.

**Fix**: Use `grouped_train_test_split()` from `_data.py` which handles NaN groups
automatically — rows with NaN group keys are excluded from the split and added to
the training set (they still have valid labels):

```python
from _data import grouped_train_test_split

train_idx, test_idx, train_groups = grouped_train_test_split(
    X=X_labeled, y=y_labeled, df=labeled_df.loc[labeled_idx],
    group_cols=group_cols, test_size=test_size, random_state=random_state,
)
# train_groups is None when no group columns available (falls back to KFold)
```

### P10: Running all semi-supervised scripts concurrently thrashes CPU

Each script uses `n_jobs=-1` in GridSearchCV, spawning ~10 loky workers.
Running all 3 scripts simultaneously creates 30+ processes competing for CPU,
causing severe contention — each worker gets only a fraction of a core.

**Fix**: Run scripts sequentially, not in parallel:
```bash
python self_training.py ...       # wait for completion
python semi_supervised_ae.py ...  # then this
python consistency_reg.py ...     # then this
```

### P11: `_fit_model_with_cv(groups=None)` causes CV data leakage

When train/test split uses GroupShuffleSplit, the same groups must be passed to
`_fit_model_with_cv()` for the inner CV. With `groups=None`, `KFold` is used
instead of `GroupKFold`, allowing the same sample to appear in both train and
validation folds during hyperparameter search.

**Fix**: Save train groups after the outer split and pass them through:
```python
train_groups = groups.to_numpy()[train_idx]  # after GroupShuffleSplit
model, params = _fit_model_with_cv(..., groups=train_groups, ...)
```

## Data Collection

See `references/literature.md` for curated SV frequency correction literature (gnomAD SV, PGG.SV, benchmarking papers).

## Plotting Utilities

`question.py` provides publication-quality plots: `single_violin_plot`, `single_bar_plot`,
`paired_violin_plot`, `violin_plot`. All support threshold lines with percentage legends.
See `references/plotting_utilities.md` for API details and usage examples.

Key matplotlib/seaborn parameters to remember:
- `inner="box"` shows box plot inside violin; `inner=None` is empty (only custom median line)
- `cut=0` clips violin at data range (no extension beyond min/max); `cut=1` extends 1 bandwidth
- X-axis labels should use `rotation=45, ha="right"` to avoid overlap
- `xtick_fontsize` default 10 (not 12 — too large for category labels)

## User Preferences

- **All imports at module top level.** Never use inline `from X import Y` inside functions.
  The user uses conda (not uv), so deferred imports don't help with install friction.
- **Numpy-style English docstrings on all functions.** Parameters/Returns/Raises sections.
  Chinese conversation, English code and docstrings.
- **Diagnostic-first debugging.** When something goes wrong, search logs and inspect
  intermediate files before assuming a root cause. Don't jump to conclusions — trace the
  actual data flow (e.g. check if raw features have BAM columns before assuming extraction failed).

`collect_data.py` handles:
- `collect_OncoTop_sv()`: Extract SV sheet from OncoTop Excel/TSV
- `collect_ddPCR_data()`: Map ddPCR sample IDs to sequence/task IDs via mapping table
- `judge_ddPCR_data()`: Compare ddPCR labels with SV detection results via merge on `[原始编号, FusionGene, FusionExon]`. Saves two files:
  - `{outprefix}_SV_comparison.tsv` — matched records (ddPCR left join SV)
  - `{outprefix}_SV_no_ddPCR.tsv` — SV records with no ddPCR entry (anti-join)
