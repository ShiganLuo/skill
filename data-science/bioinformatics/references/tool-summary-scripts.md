# Bioinformatics Tool Summary Scripts

Build Python scripts that parse bioinformatics tool output (TSV/VCF/BED), aggregate across samples, and produce TSV tables, HTML reports, and publication-quality figures with data-driven conclusions.

## Trigger conditions

- User asks to summarize/aggregate results from a bioinformatics tool across multiple samples
- Pipeline output directories contain per-sample result files that need cross-sample analysis
- User wants a report combining tables, figures, and textual conclusions

## Step-by-step workflow

### 1. Inspect tool output format

- Read 1-2 example output files to understand columns, comment prefixes, and data types
- Read the pipeline rule (Snakemake `.smk`, Nextflow `.nf`, shell script) to understand how output was generated
- Identify: file naming convention, per-sample directory structure, which files are primary vs supplementary

### 2. Design CLI with two input modes (mutually exclusive)

Support both interactive and pipeline-driven usage:

```
input_group = parser.add_mutually_exclusive_group(required=True)
input_group.add_argument("--indir", help="Scan directory for sample subdirectories")
input_group.add_argument("-p", "--passed", help="Comma-separated list of primary result files")
parser.add_argument("-d", "--discarded", help="Comma-separated list of secondary files (optional)")
parser.add_argument("-o", "--outdir", required=True, help="Output directory")
parser.add_argument("-f", "--format", nargs="+", default=["png"], help="Figure format(s)")
```

- `--indir` mode: walk directories, discover files by naming convention
- `-p/-d` mode: extract sample_id from filename (e.g., `{sample_id}_passed_fusions.tsv` → strip suffix)
- `-f` validates against `VALID_FORMATS = ("png", "pdf", "svg", "tiff", "eps", "jpg")`

### 3. Structure the analysis layer

Keep analysis functions pure (input: list of row dicts, output: computed stats):

```python
def per_sample_stats(rows: List[Dict]) -> Dict:
    """Total counts, category breakdowns, support read distributions."""

def find_recurrent_events(all_sample_data: Dict[str, List[Dict]]) -> List[Dict]:
    """Events appearing in ≥2 samples — higher confidence."""

def find_functional_events(all_sample_data: Dict[str, List[Dict]]) -> List[Dict]:
    """Domain-specific filter (e.g., in-frame fusions, pathogenic variants)."""
```

### 4. Output generation — three channels

| Channel | Content | Format |
|---------|---------|--------|
| TSV tables | Per-sample summary, filtered event lists, cross-sample recurrence | Tab-delimited |
| HTML report | Self-contained, all tables + conclusions, styled with CSS | Single `.html` |
| Figures | Stacked bars, heatmaps, horizontal bar charts | `matplotlib`, Agg backend |

### 5. Figure conclusions — grouped, data-driven

**Always group figures under section headers**, not a flat list. Compute real numbers (counts, percentages, top-N) — never hardcode.

```python
def generate_figure_conclusions(per_sample, recurrent, functional) -> List[str]:
    # Compute actual stats from data
    # Return one conclusion string per figure

sections = [
    ("Section Title A", [("Fig1 name", conclusions[0]), ("Fig2 name", conclusions[1])]),
    ("Section Title B", [("Fig3 name", conclusions[2]), ("Fig4 name", conclusions[3])]),
]
```

Console output:
```
══════════════════════════════════════════
  FIGURE CONCLUSIONS / 图表结论
══════════════════════════════════════════

  ── Section Title A ─────────────────────
  Fig1 ...
    conclusion text

  ── Section Title B ─────────────────────
  Fig3 ...
    conclusion text
```

HTML: use `<th colspan='2'>` for section headers in the conclusions table.

### 6. Snakemake integration

When the summary script is called from a Snakemake rule:

- Rule uses `-p`/`-d` mode (comma-joined `input.passed_fusions`)
- `output:` points to the main summary TSV (e.g., `outdir + "/report/per_sample_summary.tsv"`)
- Script path stored in `params.summary_script`
- Generate a timestamped `.sh` wrapper for reproducibility

```python
rule tool_report:
    input:
        primary = expand(outdir + "/{sid}/{sid}_passed.tsv", sid=samples),
        secondary = expand(outdir + "/{sid}/{sid}_discarded.tsv", sid=samples)
    output:
        report = outdir + "/report/per_sample_summary.tsv"
    params:
        script = os.path.join(ROOT_DIR, "modules/tool/bin/summarize.py")
    run:
        cmd = ["python", params.script,
               "-p", ",".join(input.primary),
               "-d", ",".join(input.secondary),
               "-o", outdir + "/report"]
        # ... write .sh, shell()
```

**Pitfall**: When updating the CLI interface, the Snakemake rule and the Python script must be updated in sync. Check both files after any CLI change.

### 7. Matplotlib setup for headless environments

```python
def _setup_matplotlib(fmt: str):
    import matplotlib
    matplotlib.use("Agg")  # MUST be before pyplot import
    import matplotlib.pyplot as plt
    dpi = {"png": 300, "tiff": 300}.get(fmt, 300)
    plt.rcParams.update({...})
    return plt
```

Wrap figure generation in try/except for graceful degradation:

```python
try:
    generate_figures(data, outdir, fmts)
except ImportError:
    logger.warning("Skipping figures: install matplotlib to enable plotting.")
```

### 8. Standard figure set for multi-sample tool output

| Fig | Content | Type |
|-----|---------|------|
| 1 | Per-sample event counts by confidence/category | Stacked bar |
| 2 | Event type distribution (all samples) | Horizontal bar |
| 3 | Type composition per sample | Stacked bar |
| 4 | Functional category distribution | Grouped bar |
| 5 | Cross-sample recurrence heatmap | Binary heatmap (✓/blank) |
| 6 | Top functional events by support | Horizontal bar with color-coded confidence |

## Pitfalls

- **Don't install packages without asking.** If matplotlib/pandas is missing, wrap in try/except and log a warning. User will install themselves.
- **Chinese for conversation, English for code.** Docstrings and comments in English, user-facing conclusions can be Chinese if user prefers.
- **Arriba-specific**: gene names can contain aliases like `Gm43566(174),AI506816(22572)` — strip with `.split("(")[0].split(",")[0]` for canonical keys.
- **ITD (internal tandem duplication)** shows up as `gene::gene` self-fusions with `in-frame` reading frame — these are gene-internal duplications, not true inter-gene fusions. Note this in conclusions.
- **read-through fusions** between adjacent genes are transcriptional noise, not structural variants. Flag them but don't treat as high-priority findings.

## Verification

```bash
# Test with --indir mode
python summarize.py --indir /path/to/output -o /tmp/test_report

# Test with -p/-d mode (as Snakemake would call)
python summarize.py -p s1_passed.tsv,s2_passed.tsv -d s1_disc.tsv,s2_disc.tsv -o /tmp/test_report -f png

# Verify outputs exist
ls /tmp/test_report/*.tsv /tmp/test_report/*.html /tmp/test_report/figures/
```
