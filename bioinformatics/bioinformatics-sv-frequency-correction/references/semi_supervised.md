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
- Filters `extra_keep_cols` against input TSV header before calling `parser_table()` (see SP6)
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
Internally:
```python
available_groups = [c for c in group_cols if c in df.columns]
groups = df[available_groups[0]].astype(str)
for col in available_groups[1:]:
    groups = groups + "__" + df[col].astype(str)
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
raises `KeyError: "['ddPCR_AF'] not in index"`.

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
