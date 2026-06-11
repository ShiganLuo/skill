# Semi-Supervised SV Frequency Correction

## Data Layout

Labeled (ddPCR): `SV_processed_ddPCR.tsv` — 936 rows, 26 unique `原始编号` labels.
Each 原始编号 has a single `ddPCR_AF` value; multiple rows represent different samples
measuring the same ground truth.

Unlabeled: `SV_processed_no_ddPCR.tsv` — 22,506 rows. Same columns but `原始编号` empty
and `ddPCR_AF` absent. Ratio: ~4% labeled.

## Scripts

All in `workflow/gene/sv/sv_freq_correction/`:

### `_data.py` — Shared data loading
```python
from _data import load_combined_features, extract_xy

labeled_df, combined_df, feature_columns, no_scale_columns = load_combined_features(
    labeled_tsv="path/to/SV_processed_ddPCR.tsv",
    unlabeled_tsv="path/to/SV_processed_no_ddPCR.tsv",
    outdir="output/semi_supervised/features",
    feature_cache_dir=None,  # set to share BAM cache across scripts
)
```
- Calls `parser_table()` for BAM feature extraction (cached to `{outdir}/labeled/` and `{outdir}/unlabeled/`)
- Filters `extra_keep_cols` against input TSV header before calling `parser_table()` (see SP7)
- Combines labeled+unlabeled, runs `preprocess_features()` on merged matrix
- Returns processed DataFrames + feature column lists
- `extract_xy(df, feature_columns)` → `(X, y, index)` dropping NaN-label rows

### `self_training.py` — Pseudo-Label Iteration
```bash
python self_training.py \
  --labeled-tsv SV_processed_ddPCR.tsv \
  --unlabeled-tsv SV_processed_no_ddPCR.tsv \
  -o output/self_training \
  --model-name gradient_boosting \
  --n-iterations 3 \
  --filter-strategy combined \
  --group-cols 原始编号  # default, repeatable for multi-col grouping
```
- Filter strategies: `residual` (|pred-Freq|<quantile), `range` (pred∈(ε,1-ε)), `top_k` (top-k% by confidence), `combined` (intersection)
- Pseudo-label weight = 0.5x labeled weight
- `--max-pseudo-fraction 0.5` caps pseudo-label count
- Convergence plots: `convergence.png`, `training_set_growth.png`

### `semi_supervised_ae.py` — Denoising Autoencoder
```bash
python semi_supervised_ae.py \
  --labeled-tsv SV_processed_ddPCR.tsv \
  --unlabeled-tsv SV_processed_no_ddPCR.tsv \
  -o output/semi_ae \
  --latent-dim 8 \
  --noise-std 0.1
```
- Architecture: `n_features → [encoder_hidden] → latent_dim → [decoder_hidden] → n_features`
- Trained on ALL data (labeled+unlabeled) with Gaussian noise input → clean reconstruction
- Encoder extracts latent via manual weight forward-pass (ReLU activation)
- Regression trained only on labeled latent features
- Visualizes latent space (first 2 dims colored by ddPCR_AF)

### `consistency_reg.py` — Consistency Regularization
```bash
python consistency_reg.py \
  --labeled-tsv SV_processed_ddPCR.tsv \
  --unlabeled-tsv SV_processed_no_ddPCR.tsv \
  -o output/consistency_reg \
  --consistency-weight 1.0
```
- **PyTorch mode** (auto-detected): `loss = MSE(pred, y) + λ * MSE(pred(x), pred(x+noise))`
  - Neural net: Linear→ReLU→Dropout layers, Adam optimizer, ReduceLROnPlateau
  - Best model saved by test MSE
- **Numpy fallback**: Ensemble of models trained on perturbed features
  - Consistency = ensemble agreement (low std = high confidence)
  - Uses prediction disagreement to filter pseudo-labels from unlabeled data

### Shared feature extraction via `--feature-dir`

All three scripts accept `--feature-dir <path>` to share BAM feature cache.
Without it, each script extracts features into its own `outdir/features/` —
22K+ rows of BAM extraction is very slow and should only happen once.

```bash
# Step 1: extract once (first script caches to its features/ dir)
python self_training.py --labeled-tsv ... --unlabeled-tsv ... -o output/self_training

# Step 2: reuse cache for subsequent scripts
python semi_supervised_ae.py ... -o output/semi_ae \
  --feature-dir output/self_training/features
python consistency_reg.py ... -o output/consistency_reg \
  --feature-dir output/self_training/features
```

## Pitfalls (Semi-Supervised Specific)

### SP1: Pseudo-label bias amplification
Self-training can amplify initial model biases. Mitigations:
- Use `combined` filter strategy (intersection of range+residual+top_k)
- Cap pseudo-labels at 50% of labeled data size
- Weight pseudo-labels at 0.5x labeled weight
- Stop early if 0 pseudo-labels accepted

### SP2: Autoencoder encoder extraction
sklearn `MLPRegressor` does not expose intermediate activations. Encoder output is
computed by manually forwarding through `mlp_.coefs_[0:n_encoder_layers]` with ReLU.
This only works when `hidden_encoder` and `hidden_decoder` are symmetric or known.

### SP3: Consistency loss scaling
The consistency weight λ must be tuned relative to supervised loss magnitude.
Start with λ=1.0; if supervised loss >> consistency loss, increase λ.
If training diverges, reduce noise_std or λ.

### SP4: Preprocessing must see all data
`preprocess_features()` (StandardScaler, VarianceThreshold, correlation filter)
must be fit on combined data, not labeled-only. Otherwise the scaler is biased
by the small labeled distribution. `_data.py` handles this automatically.

### SP5: Grouped splits (`--group-cols`)

All methods use GroupShuffleSplit to prevent data leakage — different measurements
of the same ddPCR sample must not span train/test. The grouping columns are
configurable via `--group-cols` (repeatable, `action="append"`). Default: `["原始编号"]`.

Multiple columns are concatenated with `__` into a composite key, matching train.py's
`group_cols` behavior:
```bash
python self_training.py \
  --group-cols 原始编号 --group-cols FusionGene --group-cols FusionExon \
  --labeled-tsv ... -o ...
```

**Use the shared `grouped_train_test_split()` from `_data.py`** instead of inline logic.
It handles NaN groups (NaN rows → training set, not test), composite keys, and returns
`train_groups` for passing to `_fit_model_with_cv()`:

```python
from _data import grouped_train_test_split

train_idx, test_idx, train_groups = grouped_train_test_split(
    X=X_labeled, y=y_labeled, df=labeled_df.loc[labeled_idx],
    group_cols=group_cols, test_size=test_size, random_state=random_state,
)
# train_groups: None if no group cols → falls back to KFold for CV
```

### SP6: `parser_table(outdir=...)` creates duplicate files

`parser_table()` always writes `{outdir}/raw_extracted_features.tsv` when `outdir`
is set. If the caller also writes to a cache path, you get two identical files.

**Fix in `_data.py`**: Pass `outdir=None` and write only to the cache path:
```python
df = parser_table(infile=tsv_path, outdir=None, extra_keep_cols=valid_keep, ...)
df.to_csv(cache_path, sep="\t", index=False)
```

### SP7: `parser_table()` crashes on missing `extra_keep_cols`

`parser_table()` does `df = df[bam_columns + extra_keep_cols]` without checking
column existence. When processing unlabeled data (no `ddPCR_AF` column), this
raises `KeyError`.

**Fix** (implemented in `_data.py`): Read input TSV header first, filter
`extra_keep_cols` to only columns present in the file, then add missing columns
as NaN after extraction:
```python
header = pd.read_csv(tsv_path, sep="\t", nrows=0)
available = set(header.columns)
valid_keep = [c for c in extra_keep_cols if c in available]
missing = [c for c in extra_keep_cols if c not in available]
df = parser_table(infile=tsv_path, extra_keep_cols=valid_keep, ...)
for col in missing:
    df[col] = np.nan
```

### SP8: `preprocess_features()` diagnostics dict missing `processed_feature_columns`

The `diagnostics` dict returned by `preprocess_features()` does NOT contain the
key `processed_feature_columns`. That key is only written to
`preprocessing_metadata.json` on disk. Using `diagnostics.get()` silently returns
`[]`, causing all numeric features to be lost (only sv_type one-hot survives).

```python
# WRONG — silently returns empty list
features = diagnostics.get("processed_feature_columns", [])

# RIGHT — read from the processed DataFrame directly
non_feature = set(META_COLUMNS) | {"_is_labeled"}
features = [c for c in combined_processed.columns
            if c not in non_feature and pd.api.types.is_numeric_dtype(combined_processed[c])]
```

### SP9: `_fit_model_with_cv(groups=None)` — CV data leakage

When using GroupShuffleSplit for train/test, the same groups must be passed to
`_fit_model_with_cv()` for inner CV. Otherwise KFold is used and the same
sample can appear in both train and validation folds during hyperparameter search.

```python
# Using grouped_train_test_split (recommended — handles NaN groups):
train_idx, test_idx, train_groups = grouped_train_test_split(
    X=X_labeled, y=y_labeled, df=labeled_df.loc[labeled_idx],
    group_cols=group_cols, test_size=test_size, random_state=random_state,
)
model, params = _fit_model_with_cv(..., groups=train_groups, ...)
```

All three semi-supervised scripts had this bug (groups=None). Fixed by using
`grouped_train_test_split()` which returns `train_groups` automatically.

### SP10: All imports must be at module top level

The user uses conda (not uv). Inline `from X import Y` inside functions provides
no benefit and makes dependency tracking harder. Move all imports to the file header.
Exception: `try/except` blocks for optional dependencies (e.g. PyTorch) are acceptable.

### SP11: `--group-cols` uses `action="append"` not `nargs="+"`

Per user preference, multi-value CLI args use `action="append"` (repeatable flag)
rather than `nargs="+"` (space-separated list). This matches the pattern in train.py:
```python
parser.add_argument("--group-cols", action="append", default=None,
                    help="Column(s) for grouped split (repeatable)")
```

### SP12: BAM extraction time on remote storage

`parser_table()` opens each BAM file independently via pysam. When BAM files are on
network-mounted storage (e.g. `/GeneCloud003/`, `/mnt/GenePlus005/`), each file open
involves network I/O. With 22K+ rows and many unique BAM paths, extraction can take
24+ hours. This is a one-time cost (cached afterward), but plan accordingly.

### SP13: Do NOT run all 3 scripts concurrently

Each script uses `n_jobs=-1` in GridSearchCV (~10 loky workers). Running all 3
simultaneously creates 30+ processes fighting for CPU, causing severe contention.
Run sequentially:
```bash
python self_training.py ... && \
python semi_supervised_ae.py ... && \
python consistency_reg.py ...
```

### SP14: Numpy fallback is NOT true consistency regularization

The numpy fallback in `consistency_reg.py` (when PyTorch is unavailable) trains an
ensemble of models on noise-perturbed features and averages predictions. This is
effectively **bagging with noise injection**, not consistency regularization. True
consistency regularization requires gradient-based loss computation
(`MSE(pred(x), pred(x+noise))` in the backward pass), which only PyTorch mode provides.

## File Structure

```
sv_freq_correction/
├── features.py              # Feature extraction (parser_table) + preprocessing
├── train.py                 # Baseline supervised training (ModelRegistry, 12 regressors)
├── _data.py                 # Semi-supervised data loading + grouped_train_test_split()
├── self_training.py         # Method 1: pseudo-label self-training
├── semi_supervised_ae.py    # Method 2: denoising autoencoder
├── consistency_reg.py       # Method 3: consistency regularization
├── predict.py               # Prediction inference
├── diagnose_split.py        # Train/test split diagnostics
├── report_correlated.py     # Correlated feature report
└── README.md                # Full documentation
```
