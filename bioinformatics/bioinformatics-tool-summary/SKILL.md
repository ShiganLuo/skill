---
name: bioinformatics-tool-summary
description: Build summary analysis scripts for bioinformatics tool output — parse TSV/VCF/BED, aggregate across samples, generate TSV/HTML reports and matplotlib figures with data-driven conclusions.
tags: [bioinformatics, genomics, summary-report, matplotlib, snakemake]
triggers:
  - summarize bioinformatics tool output
  - aggregate fusion/variant/expression results across samples
  - build report script for pipeline output
  - arriba / STAR-fusion / deepvariant / any tool output summary
---

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

## References

- [ChIP-seq Report Structure](references/chipseq-report-structure.md) — standard PPT slide order for ChIP-seq peak calling reports, QC metrics, data sources
- [scRNA-seq Report Structure](references/scrnaseq-report-structure.md) — 15-slide PPT template for scRNA-seq analysis reports, h5ad data extraction, image fallback strategy

## Pitfalls

- **Don't install packages without asking.** If matplotlib/pandas is missing, wrap in try/except and log a warning. User will install themselves.
- **Always review existing deliverables before creating new ones.** When user asks to "make a PPT" or "generate a report" and a file already exists at the target path, READ the existing file first. Match its structure, style, slide order, and content organization. Use `python -m markitdown existing.pptx` to inspect. The user expects continuity, not a completely different report.
- **Chinese for conversation, English for code/docstrings.** User-facing plot titles default to English unless explicitly told otherwise. Do NOT hardcode Chinese in matplotlib titles - the user may say "use Chinese" then correct to "default English".
- **Use `typing` module (Dict, List, Optional, Set) not Python 3.10+ syntax** (dict[str, list[str]] | None). Codebase targets Python 3.9 compat.
- **Scripts must NOT embed environment paths** (no `~/miniconda3/envs/DNA/bin/python` in shebangs or subprocess calls). Activate env first, run with plain `python`. Scripts must be portable.
- **Reuse existing project libraries** (e.g. `venn.py` from `src/common/plot/Python/`) instead of reimplementing. Import via `sys.path.insert` + `try/except ImportError`.
- **DESeq2 output files use `{contrast}.` prefix** in filenames (e.g. `Scramble_vs_Rn7sk_sh1.TEcount_Gene.name.tsv`, `Scramble_vs_Rn7sk_sh1.cpmPCA.png`). Function output files (GO/KEGG/GSEA) do NOT use prefix. When building file paths in Python, always include the contrast prefix for DE files.
- **DESeq2.r ScreenFeature thresholds**: `padj < 0.05` (strict less-than) and `|log2FoldChange| >= 0.58` (lfc_cut default). When filtering `.name.tsv` for Venn/report, use these exact thresholds - NOT `padj <= 0.05` or `|log2FC| >= 1`. Verified: row-level counts match `updown.tsv` exactly.
- **venn.py uses `plt.figure(0)` internally** - call `plt.close("all")` before AND after each venn.py call to avoid global figure state conflicts that cause missing PPT slide images.
- **Excel sheet names**: max 31 chars. Use `_unique_sheet_name()` helper that auto-numbers conflicts (base, base1, base2...). Never let openpyxl auto-rename - it generates "Recovered_Sheet" on severe conflicts.
- **Arriba-specific**: gene names can contain aliases like `Gm43566(174),AI506816(22572)` - strip with `.split("(")[0].split(",")[0]` for canonical keys.
- **ITD (internal tandem duplication)** shows up as `gene::gene` self-fusions with `in-frame` reading frame - these are gene-internal duplications, not true inter-gene fusions. Note this in conclusions.
- **read-through fusions** between adjacent genes are transcriptional noise, not structural variants. Flag them but don't treat as high-priority findings.
- **Container vs stock package comparison**: When debugging a container-packaged tool, download the exact PyPI version with `pip download <pkg>==<ver> --no-deps`, extract with `unzip`, and `diff` against the container's installed code. This reveals what patches actually changed vs what was already built-in. Don't assume patches applied — check if the OLD text pattern exists in the stock version first.
- **Fallback code paths in bioinformatics tools**: Tools like scte-quant have fallback paths (e.g., pysam when samtools is missing) that can produce drastically different results. When a container gives different results than expected, check `_HAS_SAMTOOLS` / `_HAS_X` flags and verify which code path was taken from the log (e.g., "samtools found" vs "falling back to pysam").
- **scTE-specific**: scte-quant 1.6.1's `_bam2bed_pysam()` does NOT do UMI dedup (`awk '!x[$4$5]++'`), unlike `_bam2bed_cmd()`. With CR+UR tags, the pysam path produces ~4x more BED lines, dramatically inflating per-barcode counts and cell detection. Always ensure samtools is in PATH when running scTE outside a container.
- **`nargs="+"` with repeated flags silently keeps only the LAST value.** `--samples A --samples B --samples C` with `nargs="+"` gives `['C']`, NOT `['A', 'B', 'C']`. When Snakemake builds a command with `cmd += ["--samples", s]` in a loop, the Python script MUST use `action="append"` instead. This is the #1 cause of "only one sample in report" bugs. Verify with `python3 -c "import argparse; ..."` before committing.
- **Snakemake report rule input must list ALL module outputs.** Don't just list narrowPeak and annotation — include trimming stats, bowtie2 metrics, markdup metrics, TE overlap files, enrichment PNGs, cutoff analysis. Missing inputs mean Snakemake won't track dependencies and the report may run before upstream data is ready.
- **IP-input pair mapping for enrichment figures.** Pass via `--ip-input-pair IP:Input` (repeatable `action="append"`). Parse with `pair.split(":", 1)` to construct paths like `{te_dir}/{ip}_vs_{input}_enrichment.png`.
- **Snakemake optional inputs must return `[]` not `""`.** When an input function conditionally returns no file, return an empty list `[]`, NOT an empty string `""`. Snakemake treats `""` as a file path and raises `Empty file path encountered`. Example:
  ```python
  def _get_optional_input(wildcards):
      if condition:
          return path_to_file
      return []  # NOT ""
  ```
- **All Snakemake rules in this project use `run:` blocks, not `shell:`.** The convention is `run:` + logger + timestamped `.sh` script + `shell(f"bash {script} > {log} 2>&1")`. A rule using bare `shell:` is inconsistent and won't have logging/tracing. Convert to `run:` pattern when adding new rules.
- **Broad xls has fewer columns than narrow xls.** MACS3 broad_peaks.xls lacks `abs_summit` (9 cols vs 10). Don't use the same parser for both — check `len(parts) >= 9` for broad, `>= 10` for narrow.
- **Consolidate per-module QC sheets into one summary.** When generating Excel reports, merge TrimGalore + Bowtie2 + MarkDuplicates + MACS3 + Peak Count + FRiP into a single "QC Summary" sheet with prefixed column names (e.g., `Trim_Total_R1`, `Align_Overall_Pct`, `MarkDup_Dup_Rate`). Keep separate sheets only for detailed data (e.g., Bowtie2 Metrics 120+ columns). QC Summary should be the LAST sheet.

## Verification

```bash
# Test with --indir mode
python summarize.py --indir /path/to/output -o /tmp/test_report

# Test with -p/-d mode (as Snakemake would call)
python summarize.py -p s1_passed.tsv,s2_passed.tsv -d s1_disc.tsv,s2_disc.tsv -o /tmp/test_report -f png

# Verify outputs exist
ls /tmp/test_report/*.tsv /tmp/test_report/*.html /tmp/test_report/figures/
```
