# MSI / bMSI Detection Pipeline Patterns

## Overview

MSI (Microsatellite Instability) detection from NGS data. Two modes:
- **tMSI** (tissue): direct detection from tumor tissue BAMs
- **bMSI** (blood-based): ctDNA liquid biopsy, requires higher sensitivity

## Microsatellite Biology

- **Repeat unit**: 1-6 bp (mono- to hexa-nucleotide)
- **Repeat count**: ≥5-10× to be considered microsatellite
- Classic NCI panel: BAT-25, BAT-26, D2S123, D5S346, D17S250 (10-30 repeats)
- Mono/di-nucleotide repeats most informative for MSI (higher slippage rate)

## Feature Engineering from Repeat-Length Distributions

### Input Format

Per-sample per-site file (`*site.txt`), columns include:
- Chromosome, position, repeat unit, repeat count, flanking sequences
- Last two columns: repeat-length distribution string (`"3:100,4:20"`), total depth

### Core Features

1. **Normalized distribution** (0 to mss-1): frequency of each repeat length
2. **msimssRatio** = msiPatternCount / msi2mssPatternCount
3. **msiRatio** = msiPatternCount / (msi2mssPatternCount + msiPatternCount)
4. **remainderRatio** = (msi2mssPatternCount + msiPatternCount) / Depth

### Weighted Entropy

```
alt_ratio = non_ref_reads / total_reads
entropy = Shannon(base2) of non-ref distribution
weighted_entropy = alt_ratio * entropy
```

Used as the primary discriminant feature between MSS and MSI-H.

## Baseline Construction

### BASELINE_HEADER Columns (23 total)

**Locus identity (cols 0-9)**: from site file template
`chromosome`, `location`, `repeat_unit_length`, `repeat_unit_binary`, `repeat_times`, `left_flank_binary`, `right_flank_binary`, `repeat_unit_bases`, `left_flank_bases`, `right_flank_bases`

**Sample statistics (cols 10-14)**:
`mss_spnum` (MSS sample count), `msih_spnum` (MSI-H sample count), `mu_mss` (MSS mean), `sigma_mss` (MSS std), `mu_msih` (MSI-H mean)

**Discrimination metrics (cols 15-18)**:
`sb` (between-class scatter), `sw_mss` (within-class scatter MSS), `maxacc_thr` (threshold at max accuracy), `auc` (ROC AUC)

**Scoring (cols 19-22)**:
`max_accuracy`, `accuracy`, `threshold` (MSS mu + 3*sigma), `weight` (normalized, 0 = filtered)

### Weight Calculation (3-step)

1. If AUC < 0.7 or max_accuracy < 0.7 → weight = 0 (filtered)
2. Otherwise → weight = accuracy (classification accuracy at threshold)
3. Merge: if either MSI-H or MSS has weight=0 → final=0
4. Normalize: `weight *= n_pass / sum(weights)` so all weights sum to pass count

### QC Chain (cascading filters)

1. **Sample QC**: mean depth ≥ 100 across all sites
2. **Site QC**: reference repeat length in [5, 50]
3. **Sample-site QC**: per-site depth ≥ 100
4. **Baseline site QC**: valid samples ≥ 50 per site
5. **Discrimination QC**: AUC ≥ 0.7 AND max accuracy ≥ 0.7

### Weight Assignment

Per-locus weight computed from multiple metrics:
- `distance` (default): Sb / Sw_mss (Fisher-like ratio)
- `auc`: ROC AUC
- `sb`: between-class scatter only
- `sw_mss`: within-class scatter only
- `accuracy`, `specificity`, `sensitivity`: threshold-based

Weight normalization: `weight *= n_pass / sum(weights)`

### Scatter Metrics

```python
# Between-class scatter (Sb)
Sb = (p * (M1 - M)² + q * (M2 - M)²) / (p + q)

# Within-class scatter (Sw_mss) — MSS cluster only
S1 = Σ(xi - M1)²
```

## Prediction (MSI Status Determination)

### Scoring Algorithm

For a new sample against the baseline:

1. **Load baseline**: filter to loci with `weight > 0`
2. **Per-locus scoring**: compute weighted entropy from sample's repeat distribution
3. **Instability flag**: `unstable = (weighted_entropy > threshold)` where `threshold = mean(MSS_trimmed) + 3 * std(MSS_trimmed)`
4. **MSI score**: weighted fraction of unstable loci
   ```
   MSI_score = Σ(weight[i] × I(entropy[i] > threshold[i])) / Σ(weight[i])
   ```
5. **Classification**: `MSI-H if MSI_score > cutoff else MSS` (default cutoff = 0.2)

### Locus ID Convention

Locus identifier (pos) = `chromosome_location_repeatTimes_repeatUnitBases`

Must be consistent between baseline construction and prediction. When loading baseline TSV, reconstruct pos from columns to match sample site file parsing.

### Prediction Output

| Column | Description |
|--------|-------------|
| sample | Sample name (basename minus `_sort.*` suffix) |
| msi_score | Weighted MSI score (0–1) |
| unstable_loci | Count of loci with entropy > threshold |
| total_loci | Total loci evaluated (excluding missing/low-depth) |
| msi_status | `MSI-H` or `MSS` |

### Handling Missing / Low-Depth Loci

Loci absent from sample or with depth < DEP_THR are skipped (not counted in total). This prevents penalizing samples with incomplete coverage.

## bMSI Data Simulation

Real blood MSI-positive samples are scarce. Simulate by mixing tissue MSI signals:

1. For each blood sample, 40-45% probability of injection
2. Select a tissue MSI sample with matching depth range
3. Inject at AF = 0.05/0.10/0.15 (simulating tumor fraction)
4. `sim_run_site(af, blood_site, tissue_site)`: add tissue reads proportional to AF

### Per-Locus XGBoost Models

Each microsatellite site gets its own XGBoost classifier:
- Features: normalized distribution + ratio features
- Filter: only use models with AUC ≥ 0.8
- Prediction: `PredClass` = 0 (MSS) or 1 (MSI-H)

## BAM Path Resolution Patterns

When building sample metadata, BAM paths must be resolved from site paths or CRC paths. Use a modular resolver pattern:

```python
# Config-driven mapping
BL_SITE_TO_BAM_MAP = {"feature/TopMSI_BaselineSample": "baseline_bam"}
BL_SUFFIX_MAP = {".site.txt": ".bam"}
PCR_BAM_SUBDIR = "cancer/4_realign_bam"

# Per-origin resolver functions
def resolve_bam_bl(site_path): ...   # string replacement + os.path.isfile check
def resolve_bam_pcr(crc_path): ...   # glob for *.bam in subdir

# Dispatch by origin type
BAM_RESOLVERS = {"PCR": resolve_bam_pcr, "renqun": resolve_bam_pcr, "BL": resolve_bam_bl}
```

For BL type with mixed path formats, check a prefix to decide which resolver to use:
```python
if BL_PREFIX in site_path:
    return resolve_bam_bl(site_path)
return resolve_bam_pcr(site_path)  # fallback: treat as CRC path
```

Always verify `os.path.isfile(bam_path)` and return `None` for missing files.

## Code Structure Patterns

### Baseline as Dict-of-Dicts (not List)

Use `records[pos] = {header_name: value, ...}` instead of `records[pos] = [v1, v2, ...]`.
Define `BASELINE_HEADER` as a module-level list and use `_build_locus_record()` to assemble records. This avoids index-position bugs.

### Subcommand CLI

Use `argparse.add_subparsers()` for build/predict modes:
```bash
python TopMSI.py build --infile info.tsv --output baseline.tsv
python TopMSI.py predict --baseline baseline.tsv --samples dir/ --output pred.tsv --cutoff 0.2
```

`--samples` should accept files, directories (auto-glob `*.site.txt`), and glob patterns.

### collect_data Side Effects

Return `pos_weight` as a new dict instead of mutating an input parameter. Merge weight maps from MSI-H and MSS collection in the caller.

## Pitfalls

- **Repeat unit length matters**: mono-nucleotide (len=1) most informative; longer units less stable
- **MaxIndex check**: only analyze sites where MaxIndex == repeatLen - 1 (expected peak)
- **Depth threshold**: sites < 300x depth marked as low-confidence (-4)
- **Pattern info**: msi/mss boundary from baseline xlsx, not hardcoded
- **Class imbalance**: MSI-H samples << MSS; use undersampling or synthetic augmentation
- **Tissue injection AF**: if tissue_depth * AF < 20, double AF to ensure detectable signal
- **Weighted entropy sorting**: `data[pos].sort()` before percentile-based operations
- **get_thr vs detect_thr**: these were duplicate functions — merge into one `detect_thr()`
- **Triple-quote pseudo-comments**: `'''...'''` used as commented-out code is a string literal, not a comment — use `#` or delete
- **Python logging format**: `%(logger_name)s` is NOT a valid field; use `%(name)s` (standard logger name)
- **open() encoding**: always specify `encoding="utf-8"` for cross-platform compatibility

## Result Collection Pattern (msisensor-pro output)

When aggregating per-sample results from directories with 5000+ subdirectories, `glob.glob()` may timeout on NFS. Use `os.scandir()` instead:

```python
rows = []
for entry in os.scandir(result_dir):
    if entry.is_dir():
        sample_id = entry.name
        msi_file = os.path.join(entry.path, f"{sample_id}.msi")
        if os.path.isfile(msi_file):
            parsed = parse_msi_file(msi_file)
            if parsed:
                rows.append({"sample_id": sample_id, **parsed})
```

### Sample ID Extraction from BAM Path

When metadata lacks explicit sample_id, extract from bam_path by splitting on `_cancer`:
```python
def extract_sample_id(bam_path):
    basename = os.path.basename(bam_path)
    if "_cancer" in basename:
        return basename.split("_cancer")[0]
    return None
```

Then merge via `pd.merge(msi_df, meta, on="sample_id", how="inner")`.

## Common File Patterns

```
feature/
  TopMSI_BaselineSample/cancer/{sample}_cancer.site.txt
baseline_bam/{sample}_cancer.bam
pattern/{pattern_id}.xlsx          # msi/mss pattern boundaries
model/{site_name}/                 # per-locus XGBoost models
```
