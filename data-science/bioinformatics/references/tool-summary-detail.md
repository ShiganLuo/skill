# Tool Summary Reporting — Full Implementation Detail

## Step-by-Step Workflow

### 1. Inspect Tool Output Format

- Read 1-2 example output files to understand columns, comment prefixes, and data types
- Read the pipeline rule (Snakemake `.smk`, Nextflow `.nf`) to understand how output was generated
- Identify: file naming convention, per-sample directory structure, primary vs supplementary files

### 2. CLI Design (Two Mutually Exclusive Input Modes)

```python
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

### 3. Analysis Layer (Pure Functions)

```python
def per_sample_stats(rows: List[Dict]) -> Dict:
    """Total counts, category breakdowns, support read distributions."""

def find_recurrent_events(all_sample_data: Dict[str, List[Dict]]) -> List[Dict]:
    """Events appearing in ≥2 samples — higher confidence."""

def find_functional_events(all_sample_data: Dict[str, List[Dict]]) -> List[Dict]:
    """Domain-specific filter (e.g., in-frame fusions, pathogenic variants)."""
```

### 4. Output — Three Channels

| Channel | Content | Format |
|---------|---------|--------|
| TSV tables | Per-sample summary, filtered event lists, cross-sample recurrence | Tab-delimited |
| HTML report | Self-contained, all tables + conclusions, styled with CSS | Single `.html` |
| Figures | Stacked bars, heatmaps, horizontal bar charts | matplotlib, Agg backend |

### 5. Figure Conclusions — Grouped, Data-Driven

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
```

HTML: use `<th colspan='2'>` for section headers in the conclusions table.

### 6. Snakemake Integration

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

**Pitfall**: When updating the CLI interface, the Snakemake rule and the Python script must be updated in sync.

### 7. Matplotlib Setup for Headless Environments

```python
def _setup_matplotlib(fmt: str):
    import matplotlib
    matplotlib.use("Agg")  # MUST be before pyplot import
    import matplotlib.pyplot as plt
    dpi = {"png": 300, "tiff": 300}.get(fmt, 300)
    plt.rcParams.update({...})
    return plt
```

### 8. Verification

```bash
python summarize.py --indir /path/to/output -o /tmp/test_report
python summarize.py -p s1_passed.tsv,s2_passed.tsv -d s1_disc.tsv,s2_disc.tsv -o /tmp/test_report -f png
ls /tmp/test_report/*.tsv /tmp/test_report/*.html /tmp/test_report/figures/
```
