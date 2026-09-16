---
name: bioinformatics
description: Bioinformatics tools and genomics pipelines — RNA-seq quantification, coverage analysis, tool output summarization, SV visualization, expression clustering, and post-processing scripts.
tags: [genomics, rna-seq, stringtie, quantification, bioinformatics, coverage-analysis, oncoprint, sv-visualization, summary-report, python, matplotlib, typing, argparse, docstrings, plotting, significance-brackets, clustering, expression-matrix, distance-metrics]
triggers:
  - StringTie, featureCounts, HTSeq, or other RNA-seq quantification
  - Gene abundance merging, TPM/FPKM/Coverage calculations
  - GTF/GFF annotation parsing and manipulation
  - Duplicate gene_id handling in quantification output
  - RNA-seq pipeline design or debugging
  - Gene body coverage, transcript coverage curves, RSeQC-style analysis
  - BAM coverage extraction, BED loading, coverage normalization
  - Summarize bioinformatics tool output across samples
  - OncoPrint, SV comparison plots, significance brackets
  - Build report script for pipeline output
---

# Bioinformatics Tools & Genomics Pipelines

Class-level skill for bioinformatics workflows: RNA-seq quantification, coverage analysis, tool output summarization, structural variant visualization, and expression matrix clustering.

---

## Section A: StringTie Gene Abundance Quantification

Recurring patterns for RNA-seq analysis, quantification, and post-processing.

## StringTie Gene Abundance Quantification

### Output Format

StringTie `-e -B -A` produces gene_abundance.tsv with columns:

| Column    | Type  | Description |
|-----------|-------|-------------|
| Gene ID   | str   | Ensembl gene ID (e.g. ENSG00000158623) |
| Gene Name | str   | HGNC symbol |
| Reference | str   | Chromosome |
| Strand    | str   | + or - |
| Start     | int   | 1-based start coordinate |
| End       | int   | End coordinate |
| Coverage  | float | Mean coverage depth |
| FPKM      | float | Fragments Per Kilobase per Million |
| TPM       | float | Transcripts Per Million |

### Duplicate Gene_id Problem

**Root cause**: StringTie clusters transcripts by genomic overlap, NOT by reference gene_id. If a gene has transcripts in non-overlapping loci (e.g. COPG2 with a ~147kb gap), StringTie outputs multiple rows with the same gene_id.

**Why only some samples**: Read coverage across the inter-locus gap varies by sample depth and fragment length. Higher coverage may bridge the gap; low coverage leaves it split.

**Why `-g` parameter won't fix it**: The `-g` (minimum locus gap) parameter controls clustering of read clusters with reads present. If there are zero reads in the gap, increasing `-g` has no effect — there's nothing to bridge.

### Merging Duplicate Gene Rows

TPM, FPKM, and Coverage are normalized metrics and cannot be simply summed. Correct merging rules:

1. **TPM**: Direct sum is mathematically valid. TPM is per-million normalized; same-sample sums preserve correct relative proportions.
2. **FPKM**: Direct sum is valid for the same reason (per-gene normalization).
3. **Coverage**: Must be length-weighted average:
   ```
   Coverage_merged = sum(Cov_i * L_i) / sum(L_i)
   where L_i = End_i - Start_i
   ```
4. **Start/End**: min(Start) / max(End). Must remain **int type** — do not convert to float.
5. **Output order**: Preserve original row order (first occurrence position), do NOT sort by gene_id.

### Pitfalls

- Do NOT sort merged output by gene_id — preserve original file order.
- Start and End must stay int, not float. Use `int()` conversion explicitly.
- Coverage weighted average needs length as weight, not raw coverage sum.
- Adjusting StringTie `-g` parameter is NOT a fix for disconnected loci — downstream merging is the correct approach.
- prepDE.py3 `-g` flag handles transcript-to-gene aggregation but still won't merge disconnected regions in the same way.

See `references/stringtie-gene-merging.md` for the working aggregation script.

---

## Section B: Gene Body / Transcript Coverage Analysis

Compute gene body coverage curves from BAM files with BED annotations. Covers BED loading, BAM coverage extraction, binning, normalization, and plotting. Use for: gene body coverage, transcript coverage curves, coverage QC, RSeQC-style analysis.

**Key technique**: Use `bam.fetch()` + `read.get_blocks()` instead of `pysam.pileup()` for 10-50x speedup. Normalize per-gene by max to compare distribution shapes across samples.

**Common pitfall**: "Batman ears" curve (high at ends, low in middle) caused by not excluding UTR/IVS regions. Fix: `--exclude-region UTR IVS`.

See `references/coverage-analysis.md` for the full algorithm, CLI interface, and performance benchmarks.

See `references/gene-body-coverage-script.md` for the specific `geneBody_coverage_advanced.py` script with detailed arguments and usage.

---

## Section C: Bioinformatics Tool Summary Scripts

Build Python scripts that parse bioinformatics tool output (TSV/VCF/BED), aggregate across samples, and produce TSV tables, HTML reports, and publication-quality figures with data-driven conclusions.

**Pattern**: CLI with mutually exclusive `--indir` (scan directory) vs `-p/-d` (comma-separated file lists) modes. Pure analysis functions → three output channels (TSV, HTML, figures). Snakemake integration via `-p/-d` mode.

**Key principle**: Always group figures under section headers with data-driven conclusions (real numbers, not hardcoded). Compute stats from actual data.

See `references/tool-summary-scripts.md` for the complete workflow, Snakemake integration patterns, and standard figure set.

---

## Section D: Structural Variant Visualization

Build Python CLI tools that produce publication-quality plots from genomics SV data — OncoPrint, comparison bar charts, significance brackets, multi-format output.

**Key patterns**:
- `PlotFormat` type alias with `Literal` constraint on function parameters
- N-group comparison bar charts with auto-generated colors
- OncoPrint with FIXED gridspec ratios (`[1, 4]`), never raw data dimensions
- Significance brackets as single polyline (not 3 separate lines)
- `ProcessPoolExecutor` for parallel plotting (never `ThreadPoolExecutor` due to SQLite)

See `references/sv-visualization.md` for the complete visualization patterns, OncoPrint layout, and pitfall catalog.

---

## Section F: CNC STA Report Merger

Merge gene detection reports (QC, SNV, CNV, SV, etc.) from multiple samples into consolidated Excel/TSV files.

### Location

```
workflow/gene/report/cnc_sta.py
```

### Supported Report Types

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

### Chip Types

- `we7v` - We7V chip
- `RNA` - RNA chip
- `OncoCapFusion` - OncoCapFusion chip
- `derRNA` - derRNA chip
- `""` - Default/empty

### Main Entry Points

#### 1. `run_sta()` - Online mode with reference matching

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

#### 2. `run_sta_offline()` - Offline mode from directories

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

#### 3. `merge_reports()` - Direct merge from paths

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

#### 4. `split_task()` - Split by task ID

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

### Excel Export Features

#### Size Management

- `estimate_df_size_mb()` - Estimate DataFrame size using sampling
- `will_exceed_excel_limits()` - Check if data exceeds Excel limits
- `shard_data_frames_atomic()` - Split data into multiple files if needed

Excel limits:
- Max rows: 1,048,576
- Max columns: 16,384
- Max file size: 200 MB (configurable)

#### Export Functions

```python
from cnc_sta import export_to_excel, export_to_excel_advanced, export_to_tsv

# Basic export (single file)
export_to_excel(data_frames, selected_types, outprefix, chip)

# Advanced export (auto-sharding if needed)
export_to_excel_advanced(data_frames, selected_types, outprefix, chip)

# TSV export (one file per type)
export_to_tsv(data_frames, selected_types, outprefix, chip)
```

### Data Filtering

#### Gene Filter (for TPM)

```python
from cnc_sta import apply_gene_filter

filtered_tpm = apply_gene_filter(tpm_frame, "filter_gene.tsv")
# filter_gene.tsv must have "geneid" column
```

#### Mutation Filter (for SNV)

```python
from cnc_sta import apply_mutation_filter

filtered_snv = apply_mutation_filter(snv_frame, "mutation_filter.tsv", sample_dir="/path")
# Adds IGV URLs if sample_dir provided
```

### TPM Processing

```python
from cnc_sta import merge_and_normalize_tpm

merged_tpm = merge_and_normalize_tpm(tpm_list)
# - Merges per-sample TPM DataFrames
# - Collapses duplicate Gene IDs by summing
# - Re-normalizes each sample to sum = 1e6
# - Output: Gene ID, Gene Name, <sample1>, <sample2>, ...
```

### Reference Files

- Beijing: `/mnt/GenePlus002/prod/path2list/all.list`
- Shenzhen: `/GeneCloud006/lims_workspace/prod/all.list`

### Pitfalls

1. **QUID results**: Detected by "QUID" in path; loads from `10_summary/{sample}.result.xlsx`
2. **FiveData reports**: Detected by "FiveData_report" or "OncoTOP0512_20260514" in path
3. **Sheet name mapping**: FiveData uses different names (e.g., "SmallVariations" -> "SNV", "call_sv" -> "SV")
4. **derRNA chip**: Appends "_derRNA" suffix to sample names and column names
5. **MSI sheet**: Written with `index=True` unlike other sheets
6. **Empty SV**: Creates a row with just sampleID if SV file is empty

---

## Section G: NCBI Entrez API (BioPython)

Patterns for querying NCBI GEO/SRA databases via BioPython's Entrez module.

### SOCKS5 Proxy with BioPython urllib

BioPython's Entrez uses `urllib` internally. urllib does NOT natively support SOCKS5 proxies. When environment variables (`http_proxy`, `all_proxy`, etc.) contain `socks5://...` URLs, urllib raises `unknown url type: socks5`.

**Fix**: Two-part approach:
1. Use PySocks to monkey-patch `socket.socket` so all TCP connections route through SOCKS5
2. Clear proxy environment variables so urllib doesn't try to parse the `socks5://` scheme

```python
import socket
import re
import os

try:
    import socks as _socks
except ImportError:
    _socks = None

_PROXY_KEYS = [
    "all_proxy", "http_proxy", "https_proxy",
    "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY",
]

def _enable_socks_for_urllib():
    """Monkey-patch socket for SOCKS5. Returns original socket for restoration."""
    if _socks is None:
        return None
    proxy_url = os.environ.get("all_proxy") or os.environ.get("http_proxy") or ""
    match = re.match(r"socks[45]h?://([^:]+):(\d+)", proxy_url)
    if not match:
        return None
    host, port = match.group(1), int(match.group(2))
    original_socket = socket.socket
    _socks.set_default_proxy(_socks.SOCKS5, host, port)
    socket.socket = _socks.socksocket
    return original_socket

def _clear_proxy_env():
    """Remove proxy env vars. Returns saved values for restoration."""
    return {k: os.environ.pop(k, None) for k in _PROXY_KEYS}

def _restore_proxy_env(saved):
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v

# Usage pattern:
_orig_sock = _enable_socks_for_urllib()
_saved_env = _clear_proxy_env()
try:
    # ... Entrez calls ...
    pass
finally:
    if _orig_sock:
        socket.socket = _orig_sock
    _restore_proxy_env(_saved_env)
```

**Why both steps are needed**: PySocks replaces the socket layer (TCP connections go through SOCKS5), but urllib's proxy handler still reads env vars and tries to interpret them as proxy URLs. Without clearing env vars, urllib fails on the `socks5://` scheme.

### GDS Database: Use esummary, Not efetch

`Entrez.efetch(db="gds", rettype="xml")` returns **plain text**, not proper XML. The GDS database does not support XML output via efetch.

**Correct approach**: Use `Entrez.esummary(db="gds", id=uid)` to get structured data as Python dicts.

### GDS esearch Returns All Related UIDs

When searching `GSM922266[Accession]` in GDS, esearch returns UIDs for the GSE series, GPL platform, AND all GSM samples — not just the matching record.

**Pattern**: Get all UIDs, fetch summaries, filter by accession:

```python
handle = Entrez.esearch(db="gds", term=f"{acc}[Accession]")
results = Entrez.read(handle)
handle.close()
all_uids = results.get("IdList", [])

# Fetch summaries and find the matching UID
sum_handle = Entrez.esummary(db="gds", id=",".join(all_uids))
summaries = Entrez.read(sum_handle)
sum_handle.close()

target_uid = None
for summary in summaries:
    if summary.get("Accession", "") == acc:
        target_uid = summary.get("Id")
        break
```

### elink Does NOT Find GSM Under GSE

`Entrez.elink(dbfrom="gds", db="gds", id=gse_uid, term="GSM[Accession]")` returns 0 results. Do not use elink to discover GSM samples under a GSE series.

**Correct approach**: Use esearch with `"{gse_id}[Accession]"` which returns all related UIDs (GSE + GPL + GSM), then filter for GSM accessions via esummary.

### BioPython IntegerElement

`summary.get("n_samples")` returns an `IntegerElement` object, not a plain int. `str()` gives `"IntegerElement(0, attributes={})"`.

**Fix**: Convert explicitly:
```python
def _extract_int(value) -> str:
    if hasattr(value, "attributes"):
        return str(int(value))
    return str(value)
```

### Pitfalls

- **Never use `efetch` with `db="gds"`** — it returns plain text, not XML. Always use `esummary`.
- **elink with GDS database** — does not discover related GSM samples. Use esearch + esummary instead.
- **SOCKS5 proxy requires TWO fixes** — PySocks socket patch AND env var clearing. Missing either fails.
- **IntegerElement from esummary** — `n_samples` and similar numeric fields return BioPython wrapper objects, not plain ints.
- **Entrez rate limiting** — NCBI limits to 3 requests/second without API key, 10/second with. Always add `time.sleep(0.35)` between calls.
- **429 Too Many Requests** — implement exponential backoff retry (2^attempt seconds).

---

## Section H: Expression Matrix Clustering

Three-class architecture for gene expression clustering with batch correction.

### Classes

1. **ExpressionPreprocessor** — load, filter, log2, batch correct, z-score
2. **DistanceCalculator** — pairwise distances + clustering (hierarchical/kmeans/leiden)
3. **ClusterPlotter** — heatmap, UMAP, dendrogram, elbow

### Preprocessing Pipeline

`filter (min_mean) → log2(x+1) → batch_correction → z-score per gene`

### Distance Metrics

Supported: euclidean, maximum, manhattan, canberra, binary, minkowski, cosine.

- `pdist` uses `cityblock` for manhattan; minkowski needs `p=` kwarg
- KMeans only supports euclidean; non-euclidean falls back to hierarchical (average)
- Leiden passes metric to `scanpy.pp.neighbors`
- Ward linkage requires euclidean (auto-overrides with warning)

### ComBat Batch Correction

Pure numpy/pandas implementation (no scanpy dependency). Algorithm (Johnson et al. 2007):

1. OLS: `B_hat = lstsq(batch_design, data.T)` → batch means
2. Standardize: `gamma_hat = B_hat - grand_mean`, `delta_hat = batch_std`
3. EB shrinkage (method of moments): estimate prior params from all genes, compute posterior
4. Apply: `y_corrected = (y - gamma_star) / delta_star * sqrt(var_pooled) + grand_mean`

**Critical limitation**: When batches = studies (only 2 batches, each from a different study), ComBat cannot distinguish batch effects from biological differences. The correction removes ALL between-study variation, which may include the biology you want to compare.

### Sample Clustering (transposed)

For clustering samples (not genes): preprocess on genes×samples orientation, then transpose `prep.scaled.T` for distance calculation. Gene-level filtering must happen on the correct axis.

### Pitfalls

- **ComBat formula**: `y_corrected = (y - gamma_star) / delta_star * sqrt(var_pooled) + grand_mean`. Not `(y - gamma) / scale_ratio + grand_mean` — wrong formula gives additive-only correction.
- **Quantile normalization with duplicate ranks**: Use numpy sort + rank-means approach, not pandas stack/unstack which fails on duplicate indices.
- **2-batch ComBat is degenerate**: shrinkage has almost no effect with only 2 batches; effectively a simple mean/variance alignment. Consider marker-gene approach instead when comparing across studies.
- **Ward + non-euclidean**: auto-override to euclidean with warning, not an error.
- **KMeans + non-euclidean**: silently falls back to hierarchical (average) with warning.

### Location

```
workflow/Omics/src/cluster/expression_cluster.py
```

---

## Section E: Python Scientific Plotting Scripts

Patterns for authoring and refactoring Python scripts that produce publication-quality plots in bioinformatics/genomics pipelines.

### Multi-Format Image Output

Define a `PlotFormat` type alias at module level and use `Optional[List[PlotFormat]]` for function parameters:

```python
from typing import Dict, List, Literal, Optional

PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]

def my_plot_func(
    data: pd.DataFrame,
    out_prefix: str,
    image_formats: Optional[List[PlotFormat]] = None,
) -> None:
    if image_formats is None:
        image_formats = ["png"]
    for fmt in image_formats:
        plt.savefig(f"{out_prefix}.{fmt}", dpi=300)
```

**CLI pattern** — use `action="append"` so users pass `-f png -f pdf`:

```python
parser.add_argument(
    "-f", "--format",
    action="append",
    dest="formats",
    metavar="FMT",
    help="Image output format. Can be specified multiple times. Default: png.",
)
```

#### Pitfalls

- **Short-flag collision when retrofitting** — when adding `-f/--format` to an existing script that already uses `-f` for another arg (e.g. `--figsize`), reassign the old arg's short flag first (e.g. `-f/--figsize` → `-s/--figsize`) before adding `-f/--format`. Always grep for existing `-f` short flags before adding the format arg.
- **Never use bare `list`** — always `List[X]` with typing.
- **int values in subprocess command lists** — `subprocess.run()` and similar require ALL list items to be `str`. Always wrap non-string values: `str(ins_bin_size)`. This is a silent bug that only manifests at runtime.
- **Mutable default arguments** — always `None` + if-check, never `list = []`.
- **String concatenation for multi-format** — use `os.path.splitext(out)[0]` to strip existing extension before appending format.
- **output parameter semantics change** — when adding multi-format support to a function that previously took `output="gene_model.png"` (full path with extension), change it to `output="gene_model"` (base path without extension) and update all callers. The function loop appends `.{fmt}` internally. Don't forget CLI callers and batch `run()` functions.

### Optional Dependency Guard

When a script has optional dependencies (e.g. matplotlib), wrap the import in a try/except at the call site rather than at module level. This lets the core logic run even without plotting:

```python
# In main():
try:
    generate_figures(data, outdir, fmts)
except ImportError as exc:
    logger.warning(f"Skipping figures: {exc}. Install matplotlib to enable plotting.")
```

Inside the plotting module, use `matplotlib.use("Agg")` before any pyplot import for headless environments:

```python
def _setup_matplotlib(fmt: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ...
```

#### Pitfalls

- **Never import matplotlib at module top-level** in scripts that also run without plotting — it forces the dependency even for non-plot tasks.
- **Mutually exclusive input modes** — use `argparse.add_mutually_exclusive_group(required=True)` when a script supports two alternative input methods (e.g. `--indir` for directory scanning vs `-p` for explicit file lists). This gives clear error messages without manual validation:

```python
input_group = parser.add_mutually_exclusive_group(required=True)
input_group.add_argument("--indir", help="Scan directory for sample subdirs.")
input_group.add_argument("-p", "--passed", help="Comma-separated file list.")
```

### Unified CLI Argument Style

When a project has multiple entry-point scripts, keep argument names consistent:

| Purpose | Short | Long | Style |
|---------|-------|------|-------|
| Image format | `-f` | `--format` | `action="append", dest="formats"` |
| Output dir | `-o` | `--outdir` | single string |
| Groups | `-g` | `--group` | `action="append", metavar="NAME:VCF"` |
| File mappings | | `--tab_files` | `nargs="+", metavar="NAME=PATH"` |

### Dict-Based File Mapping Pattern

When multiple files are paired with names/conditions, use a single `nargs="+"` argument with `name=path` format instead of two parallel lists:

```python
# CLI
parser.add_argument("--deseq2_files", nargs="+", help="format: condition=path")

# Parsing
condition_files = {}
for item in args.deseq2_files:
    if "=" not in item:
        parser.error(f"Invalid format '{item}', expected 'condition=path'")
    name, path = item.split("=", 1)  # split on first = only
    condition_files[name] = path

# Function signature
def Deseq2_oncoprint_data(
    condition_files: Dict[str, str],  # NOT two parallel lists
    ...
):
    for condition, file in condition_files.items():
        ...
```

This eliminates length-mismatch errors and makes the interface self-documenting.

### Typing Conventions

Use modern type hints with full parameterization:

```python
# Good
def run(group_vcf: Dict[str, str], image_formats: Optional[List[PlotFormat]] = None) -> None:

# Bad
def run(group_vcf: dict, image_formats: list = None):
```

Import from `typing`: `Dict`, `List`, `Optional`, `Literal`, `Tuple`, `Union`.

### NumPy Docstring Style

Every function must have a NumPy-style docstring. Template:

```python
def my_func(param1: str, param2: int = 10) -> pd.DataFrame:
    """
    Short summary line (imperative mood).

    Extended description if needed.

    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int, optional
        Description of param2. Default is ``10``.

    Returns
    -------
    pd.DataFrame
        Description of return value.

    Raises
    ------
    ValueError
        When something is wrong.
    """
```

#### Pitfalls

- **Docstring placement** — the `"""` block must be the FIRST statement after `def`. If-checks for default args go AFTER the docstring, not before.
- **Batch docstring addition** — use `delegate_task` with 2-3 parallel subagents for projects with 10+ functions across multiple files.

### Graceful Statistical Testing

When using `chi2_contingency` on contingency tables that may have zeros:

```python
table = np.array([...])
# Pre-check for degenerate tables
if table.min() < 0 or table.sum() == 0 or (table.sum(axis=0) == 0).any() or (table.sum(axis=1) == 0).any():
    return None
try:
    _, p, _, _ = chi2_contingency(table)
except ValueError:
    return None
```

### Parallel Plotting (ProcessPoolExecutor)

When a CLI tool plots multiple genes/samples/regions, parallelism speeds things up — but **only with processes, never threads**.

#### Why threading fails

1. **GIL**: matplotlib is CPU-bound Python. Threads cannot execute Python bytecode in parallel, so `ThreadPoolExecutor` gives zero speedup (often slower due to context-switch overhead).
2. **SQLite thread safety**: gffutils uses SQLite under the hood. SQLite objects created in one thread cannot be used in another — raises `sqlite3.ProgrammingError`.

#### Correct pattern

```python
import concurrent.futures

parser.add_argument("-j", "--threads", type=int, default=1,
                    help="Number of parallel workers (default: 1)")

def _plot_one(gene_name: str) -> None:
    db = create_db(args.gtf)  # Each process gets its own SQLite connection
    transcripts, gene = get_gene_structure_by_transcript(db, gene_name)
    plot_gene_model_all_transcripts(gene, transcripts, ...)

with concurrent.futures.ProcessPoolExecutor(max_workers=args.threads) as executor:
    list(executor.map(_plot_one, args.genes))
```

#### Pitfalls

- **`create_db()` must be inside the worker function**, not in the parent process. Each process needs its own SQLite connection. The `.db` file is reused (not re-created) so concurrent `create_db` calls are safe.
- **Don't exceed CPU core count** — `max_workers` > cores causes process thrashing.
- **Parameter is named `--threads` for CLI consistency** (matches other scripts), but the implementation uses `ProcessPoolExecutor`. This is intentional — the user-facing concept is "parallelism level", not the implementation detail.

### Multi-Value Gene/Item Arguments

When a CLI needs to accept multiple genes, samples, or items:

```python
parser.add_argument("-g", "--gene", action="append", dest="genes", required=True,
                    help="Gene symbol. Repeatable: -g TP53 -g BRCA1")
```

Then loop (or submit to process pool):

```python
for gene_name in args.genes:
    _plot_one(gene_name)
```

**Never** use `nargs="+"` for this — `action="append"` is more explicit and matches the `-f`/`--format` pattern used across the project.

### Significance Brackets on Bar Charts (宝盖头 Style)

Draw pairwise significance annotations on grouped bar charts. Supports N groups, broken axis, and the 宝盖头 (roof radical) bracket style with outward diagonal ticks.

#### Core Pattern: Multi-Group Bar Width

```python
n_groups = len(group_order)
total_width = 0.8
bar_width = total_width / n_groups
offsets = [bar_width * (i - (n_groups - 1) / 2) for i in range(n_groups)]

for i, g in enumerate(group_order):
    ax.bar(x + offsets[i], pivot[g], bar_width, color=colors[g])
```

#### Pairwise Chi2 with Degenerate Table Guard

```python
all_pairs: Dict[str, List[tuple]] = {}
for sv in pivot.index:
    pairs = []
    for i, g1 in enumerate(group_order):
        for g2 in group_order[i + 1:]:
            idx1 = list(group_order).index(g1)
            idx2 = list(group_order).index(g2)
            table = np.array([
                [pivot.loc[sv, g1], pivot[g1].sum() - pivot.loc[sv, g1]],
                [pivot.loc[sv, g2], pivot[g2].sum() - pivot.loc[sv, g2]],
            ])
            if table.min() < 0 or table.sum() == 0 \
               or (table.sum(axis=0) == 0).any() \
               or (table.sum(axis=1) == 0).any():
                continue
            try:
                _, p, _, _ = chi2_contingency(table)
            except ValueError:
                continue
            pairs.append((idx1, idx2, p_to_star(p)))
    all_pairs[sv] = pairs
```

#### Auto-Detect Broken Axis

Don't always use broken axis. Only enable when the tallest bar is significantly higher than the rest:

```python
global_max = pivot.values.max()
sig_sv_list = [sv for sv, pairs in all_pairs.items()
               if any(s != "ns" for _, _, s in pairs)]
sig_max = pivot.loc[sig_sv_list].values.max() if sig_sv_list else np.median(pivot.values)

need_broken = use_broken_axis and (global_max > sig_max * 2.0)
```

When `need_broken=False`, fall back to a single axes — avoids bracket clipping issues.

#### 宝盖头 Bracket Style (CORRECT)

User preference: horizontal line from bar1 center to bar2 center, with OUTWARD diagonal ticks `\` and `/` pointing at bar centers. NO vertical lines crossing through bars. ns labels SAME color (black) as stars, distinguished by font size/weight only.

```python
LEG_PT = 8    # initial gap from bar top to first bracket (display points)
TEXT_PT = 3   # text offset above bracket line (display points)

for i_sv, sv in enumerate(pivot.index):
    pairs = all_pairs.get(sv, [])
    if not pairs:
        continue
    y_base = max(pivot.loc[sv, g] for g in group_order)
    bracket_offset = 0.0

    for idx1, idx2, star in pairs:
        ax = ax_bottom if (need_broken and y_base <= low_max) else ax_top

        trans = ax.transData
        inv = ax.transData.inverted()

        _, y_disp = trans.transform((0, y_base))
        y_hat_disp = y_disp + LEG_PT + bracket_offset
        y_text_disp = y_hat_disp + TEXT_PT
        _, y_hat = inv.transform((0, y_hat_disp))
        _, y_text = inv.transform((0, y_text_disp))

        x1 = x[i_sv] + offsets[idx1]
        x2 = x[i_sv] + offsets[idx2]

        is_sig = star != "ns"
        fs = 12 if is_sig else 9
        fw = "bold" if is_sig else "normal"

        # 宝盖头 bracket as SINGLE POLYLINE (avoids line-cap overlap at junctions)
        tick_x = bar_width * 0.25
        _, y_tick = inv.transform((0, y_hat_disp - tick_depth))

        ax.plot(
            [x1 - tick_x, x1, x2, x2 + tick_x],
            [y_tick, y_hat, y_hat, y_tick],
            lw=bracket_lw, c="black",
        )

        ax.text((x1 + x2) / 2, y_text, star,
                ha="center", va="bottom",
                fontsize=fs, fontweight=fw, color="black")

        # Stack brackets within same SV type
        bracket_offset += tick_depth + TEXT_PT + bracket_gap
```

#### Visual Result

```
   \──────────/     \──────/
     ****              ns
  [bar1] [bar2]   [bar3] [bar4]
```

#### Bracket Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bracket_gap` | 10.0 | Vertical gap (display pts) between stacked bracket units |
| `tick_depth` | 6.0 | Depth of diagonal ticks (display pts). Larger = steeper angle |
| `bracket_lw` | 0.8 | Line width for bracket lines and ticks |
| `use_broken_axis` | True | Enable broken axis; auto-disabled if data doesn't need it |
| `test_method` | "chi2" | Statistical test: `"chi2"` or `"fisher"` (for small samples) |

#### Significance Bracket Pitfalls

- **ns color MUST be same as stars (black)** — user explicitly rejected gray. Distinguish by fontsize (12 vs 9) and weight (bold vs normal) only.
- **Diagonal ticks must be OUTWARD** — `\` goes down-LEFT from bar1, `/` goes down-RIGHT from bar2. NOT inward toward each other.
- **Horizontal line goes from bar center to bar center** — NOT from extended bracket ends. The ticks extend outward from the bar centers.
- **Reset `bracket_offset` per SV type** — NOT globally across all types. Each SV type's brackets start fresh from its own `y_base`.
- **`bracket_offset` increment** — use `tick_depth + TEXT_PT + bracket_gap`, NOT `LEG_PT + TEXT_PT + bracket_gap`. LEG_PT is only for the initial gap from bars.
- **Auto-detect broken axis** — when all bars are similar height, `need_broken=False` avoids bracket clipping by the broken axis junction.
- **Store ALL pairs including ns** — so every comparison gets a bracket annotation, not just significant ones.
- **Draw bracket as SINGLE POLYLINE** — never 3 separate `ax.plot()` calls. Three separate lines cause line-cap overlap at junction points, creating visible protrusions. One `ax.plot()` with 4 x-points and 4 y-points draws the entire 宝盖头 cleanly.
- **`bracket_lw` default 0.8** — thicker lines (1.2+) look heavy. 0.8 is clean and publication-ready.
