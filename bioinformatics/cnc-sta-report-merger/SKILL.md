---
name: cnc-sta-report-merger
description: Merge and export gene detection reports (QC, SNV, CNV, SV, etc.) from multiple samples into consolidated Excel/TSV files.
tags: [genomics, report, excel, merge, bioinformatics]
triggers:
  - "merge reports"
  - "cnc_sta"
  - "gene report export"
  - "sample report consolidation"
---

# CNC STA Report Merger

Merge gene detection reports from multiple samples into consolidated Excel or TSV files.

## Location

```
workflow/gene/report/cnc_sta.py
```

## Supported Report Types

| Type | Description |
|------|-------------|
| QC | Quality control metrics |
| MSI | Microsatellite instability |
| SNV | Small nucleotide variations |
| CNV | Copy number variations |
| SV | Structural variations |
| N | Normal sample data (sub-sheets) |
| HRD | Homologous recombination deficiency |
| TMB | Tumor mutation burden |
| ALL | All report sheets (sub-sheets) |
| OncoH | OncoH report |
| Fusion | Gene fusions |
| ARV7 | AR-V7 detection |
| EGFR VIII | EGFR variant III |
| MET_14 | MET exon 14 skipping |
| DRneo | DRneo report (sub-sheets) |
| TPM | Gene expression (merged & normalized) |

## Chip Types

- `we7v` - We7V chip
- `RNA` - RNA chip
- `OncoCapFusion` - OncoCapFusion chip
- `derRNA` - derRNA chip
- `""` - Default/empty

## Main Entry Points

### 1. `run_sta()` - Online mode with reference matching

Match sample/task IDs against a reference path list, then merge reports.

```python
from cnc_sta import run_sta

run_sta(
    in_file="input.tsv",           # TSV with sample_id, task_id columns
    ref_file="/path/to/all.list",  # Reference path list
    outprefix="output/prefix",
    selected_types=["QC", "SNV", "CNV", "SV"],
    mode="task_sample",            # or "single"
    chip="",
    save_mode="xlsx"               # or "tsv"
)
```

**Input formats:**
- `task_sample` mode: TSV with `sample_id` and `task_id` columns
- `single` mode: Text file with one ID per line

### 2. `run_sta_offline()` - Offline mode from directories

Collect report paths from directories, optionally filter, then merge.

```python
from cnc_sta import run_sta_offline

run_sta_offline(
    dirs=["/path/to/dir1", "/path/to/dir2"],
    outprefix="output/prefix",
    filter_file="sample_list.tsv",  # Optional
    mode="single",                  # Required if filter_file given
    selected_types=["ALL"],
    chip="",
    save_mode="xlsx",
    dry_run=False                   # True to skip actual merging
)
```

### 3. `merge_reports()` - Direct merge from paths

Merge reports directly from a list of sample paths.

```python
from cnc_sta import merge_reports

merge_reports(
    sample_paths=["/path/to/sample1", "/path/to/sample2"],
    outprefix="output/prefix",
    chip="",
    selected_types=["QC", "SNV"],
    save_mode="xlsx",
    sample_cols=["sampleID", "Sample"]  # Column names to identify samples
)
```

### 4. `split_task()` - Split by task ID

Generate separate reports per task ID.

```python
from cnc_sta import split_task

split_task(
    in_file="input.tsv",
    ref_file="/path/to/all.list",
    outdir="output/dir",
    selected_types=["QC", "SNV", "SV"],
    chip="",
    save_mode="xlsx",
    mode="task_sample"
)
```

## Excel Export Features

### Size Management

- `estimate_df_size_mb()` - Estimate DataFrame size using sampling
- `will_exceed_excel_limits()` - Check if data exceeds Excel limits
- `shard_data_frames_atomic()` - Split data into multiple files if needed

Excel limits:
- Max rows: 1,048,576
- Max columns: 16,384
- Max file size: 200 MB (configurable)

### Export Functions

```python
from cnc_sta import export_to_excel, export_to_excel_advanced, export_to_tsv

# Basic export (single file)
export_to_excel(data_frames, selected_types, outprefix, chip)

# Advanced export (auto-sharding if needed)
export_to_excel_advanced(data_frames, selected_types, outprefix, chip)

# TSV export (one file per type)
export_to_tsv(data_frames, selected_types, outprefix, chip)
```

## Data Filtering

### Gene Filter (for TPM)

```python
from cnc_sta import apply_gene_filter

filtered_tpm = apply_gene_filter(tpm_frame, "filter_gene.tsv")
# filter_gene.tsv must have "geneid" column
```

### Mutation Filter (for SNV)

```python
from cnc_sta import apply_mutation_filter

filtered_snv = apply_mutation_filter(snv_frame, "mutation_filter.tsv", sample_dir="/path")
# Adds IGV URLs if sample_dir provided
```

## TPM Processing

```python
from cnc_sta import merge_and_normalize_tpm

merged_tpm = merge_and_normalize_tpm(tpm_list)
# - Merges per-sample TPM DataFrames
# - Collapses duplicate Gene IDs by summing
# - Re-normalizes each sample to sum = 1e6
# - Output: Gene ID, Gene Name, <sample1>, <sample2>, ...
```

## Reference Files

- Beijing: `/mnt/GenePlus002/prod/path2list/all.list`
- Shenzhen: `/GeneCloud006/lims_workspace/prod/all.list`

## Pitfalls

1. **QUID results**: Detected by "QUID" in path; loads from `10_summary/{sample}.result.xlsx`
2. **FiveData reports**: Detected by "FiveData_report" or "OncoTOP0512_20260514" in path
3. **Sheet name mapping**: FiveData uses different names (e.g., "SmallVariations" -> "SNV", "call_sv" -> "SV")
4. **derRNA chip**: Appends "_derRNA" suffix to sample names and column names
5. **MSI sheet**: Written with `index=True` unlike other sheets
6. **Empty SV**: Creates a row with just sampleID if SV file is empty

## Command Line Interface

The script supports CLI via argparse with subcommands.

### Usage

```bash
python cnc_sta.py <command> [options]
```

### Commands

#### `run` - Online mode with reference matching

```bash
python cnc_sta.py run \
    --in-file input.tsv \
    --ref-file /path/to/all.list \
    --outprefix output/prefix \
    --types QC SNV CNV SV \
    --mode task_sample \
    --chip we7v \
    --save-mode xlsx
```

Required arguments:
- `--in-file, -i` : Input TSV with sample_id/task_id (or text file for single mode)
- `--ref-file, -r` : Reference file with paths
- `--outprefix, -o` : Output file prefix

Optional arguments:
- `--types, -t` : Report types (default: all). Choices: QC, MSI, SNV, CNV, SV, N, HRD, TMB, ALL, OncoH, Fusion, ARV7, EGFR VIII, MET_14, DRneo, TPM
- `--mode, -m` : Matching mode: task_sample or single (default: task_sample)
- `--chip, -c` : Chip type: we7v, RNA, OncoCapFusion, derRNA (default: empty)
- `--save-mode, -s` : Output format: xlsx or tsv (default: xlsx)

#### `offline` - Collect from directories

```bash
python cnc_sta.py offline \
    --dirs /path/to/dir1 /path/to/dir2 \
    --outprefix output/prefix \
    --filter-file samples.tsv \
    --mode single \
    --types ALL \
    --dry-run
```

Required arguments:
- `--dirs, -d` : One or more directories to scan
- `--outprefix, -o` : Output file prefix

Optional arguments:
- `--filter-file, -f` : TSV file to filter samples (requires --mode)
- `--mode, -m` : Matching mode for filter_file
- `--dry-run` : Only collect paths, skip merging
- `--types, -t` : Report types (default: all)
- `--chip, -c` : Chip type (default: empty)
- `--save-mode, -s` : Output format (default: xlsx)

#### `split` - Split by task ID

```bash
python cnc_sta.py split \
    --in-file input.tsv \
    --ref-file /path/to/all.list \
    --outdir output/dir \
    --types QC SNV SV \
    --mode task_sample
```

Required arguments:
- `--in-file, -i` : Input file with sample/task IDs
- `--ref-file, -r` : Reference file with paths
- `--outdir, -o` : Output directory

Optional arguments:
- `--mode, -m` : Matching mode (default: task_sample)
- `--types, -t` : Report types (default: all)
- `--chip, -c` : Chip type (default: empty)
- `--save-mode, -s` : Output format (default: xlsx)

### Examples

```bash
# Merge QC and SNV for samples in task_sample mode
python cnc_sta.py run -i samples.tsv -r /mnt/GenePlus002/prod/path2list/all.list -o output/report -t QC SNV

# Offline mode with filter
python cnc_sta.py offline -d /path/to/dir1 /path/to/dir2 -o output/report -f filter.tsv -m single -t ALL

# Split reports by task
python cnc_sta.py split -i tasks.tsv -r /path/to/all.list -o output/split -t QC SNV CNV

# Dry run to check paths without merging
python cnc_sta.py offline -d /path/to/dir -o output/report --dry-run
```

## Dependencies

- pandas
- xlsxwriter
- pathlib
- argparse (stdlib)
- common.MatchUtil (task_sample_match, single_id_match)
- utils.common (load_excel_with_sample)
