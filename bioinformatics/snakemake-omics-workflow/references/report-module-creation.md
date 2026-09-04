# Report Module Creation Pattern

Report modules generate PPTX + XLSX from pipeline output. They are the final
stage of a workflow, collecting QC statistics and producing a visual summary.

## Module structure

```
modules/<workflow>_report/
├── <workflow>_report.smk        # Snakemake rules: generate_report + report_result
├── <workflow>_report.json       # Config schema
├── <workflow>_report.yaml       # Conda env (python-pptx, matplotlib, pandas, openpyxl)
├── <workflow>_report.def        # Apptainer SIF build
├── <workflow>_report.dockerfile # Docker build
└── bin/generate_report.py       # Main report generator script
```

## Reference implementations

Only `RNAseq_report` and `ncRNAseq_report` are standard report modules.
`PeakCalling_report` and `CoCulture_report` exist but use non-standard patterns
(different rule names, no XLSX output, etc.) -- do NOT use them as templates.

- `modules/RNAseq_report/` -- TE-chimeric, DESeq2, fusion, GO/KEGG/GSEA reports
- `modules/ncRNAseq_report/` -- Read flow, trimming, STAR 3-pass, per-gene, Tailer

The report module pattern is also documented in `modules/modules.md` under
"报告模块（_report）" -- keep that doc section in sync when updating the pattern.

## .smk rule pattern

Two rules: `generate_report` (produces PPTX + XLSX) and `report_result`
(aggregates outputs for `rule all`).

```python
rule generate_report:
    input:
        # All upstream outputs the report depends on
        per_sample_bams = expand(outdir + "/path/{sample}/{sample}.bam", sample=samples),
    output:
        report = outdir + "/<workflow>_report.pptx",
        file_inventory = outdir + "/<workflow>_report_files.xlsx",
    log: logdir + "/<workflow>_report.log"
    conda: "<workflow>_report.yaml"
    container: sif("<workflow>_report.yaml")
    params:
        samples = samples,
        title = config.get("Params", {}).get("report", {}).get("title") or "Default Title",
        # ... subtitle, pipeline, genome, date, lang, img_dir, script
    run:
        # Build cmd list, write shell script, execute via shell()
```

## generate_report.py structure

1. **I18N dict** with `zh` and `en` translations
2. **Data collection functions** -- parse logs, TSVs, CSVs from analysis dir
3. **Chart generators** -- matplotlib figures saved as temp PNGs via TempImageStore
4. **Slide builders** -- each builds one slide using python-pptx helpers
5. **Excel inventory** -- write all result data to multi-sheet XLSX
6. **main()** -- argparse CLI, auto-detect samples if not provided

### Key python-pptx helpers (reusable from RNAseq_report)

- `_header(slide, text)` -- navy bar with white title
- `_textbox(slide, ...)` -- positioned text box
- `_bullets(slide, ...)` -- bulleted list
- `_table(slide, ...)` -- formatted table with header row
- `_add_picture(slide, path, ...)` -- aspect-ratio-preserving image placement

### Slide dimensions (4:3 format)

```python
SLIDE_W = 10.0   # inches
SLIDE_H = 5.625
HEADER_H = 0.65
CONTENT_TOP = HEADER_H + 0.18  # = 0.83
CONTENT_H = SLIDE_H - CONTENT_TOP - 0.22  # = 4.575
```

### TempImageStore pattern

Charts are generated as temp PNGs, optionally copied to `--img-dir` for
persistence, then cleaned up after `prs.save()`:

```python
img_store = TempImageStore(args.img_dir)
# ... build slides, generate charts ...
prs.save(output)
img_store.cleanup()
```

## Data collection patterns

### Parsing STAR Log.final.out

```python
def parse_star_log(path):
    text = Path(path).read_text()
    # Use regex with pattern: "Label | Value"
    input_reads = int(re.search(r"Number of input reads\s+\|\s+(\d+)", text).group(1))
```

### Parsing trim_galore statistics

`trimming_statistics_1.txt` and `_2.txt` contain adapter% and pairs removed%.
Parse with regex: `r"Reads with adapters:\s+([\d.]+)\s*\("`

### Counting FASTQ reads

```python
def count_fastq_reads(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as fh:
        return sum(1 for _ in fh) // 4
```

### samtools view -c for BAM read counts

```python
import subprocess
r = subprocess.run(["samtools", "view", "-c", bam_path],
                   capture_output=True, text=True, timeout=30)
count = int(r.stdout.strip())
```

## Subworkflow integration

Add at the end of `subworkflow/<workflow>.smk`:

```python
<workflow>_report_config = {
    "ROOT_DIR": ROOT_DIR,
    "env": config.get("env", {}),
    "outdir": outdir,
    "logdir": logdir,
    "samples": all_samples,
    "paired_samples": paired_samples,
    "single_samples": single_samples,
    "Params": {"report": config.get("Params", {}).get("report", {})},
}
module <workflow>_report:
    snakefile: "../modules/<workflow>_report/<workflow>_report.smk"
    config: <workflow>_report_config
use rule generate_report from <workflow>_report as <workflow>_generate_report
use rule report_result from <workflow>_report as <workflow>_report_result
```

## Overflow checking (critical QA)

Table overflow is the most common PPT layout issue. Before declaring done:

1. Convert PPTX to PDF: `soffice --headless --convert-to pdf report.pptx`
2. Convert PDF to images: `pdftoppm -jpeg -r 150 report.pdf slide`
3. Check each slide's bottom margin programmatically:

```python
from PIL import Image
import numpy as np
img = Image.open(f"slide-{i}.jpg")
arr = np.array(img.convert("L"))
h = arr.shape[0]
region = arr[int(0.5*h):, :]
row_stds = np.std(region, axis=1)
rows = np.where(row_stds > 10)[0]
last_content = rows[-1] + int(0.5*h) if len(rows) > 0 else 0
margin = h - last_content  # must be > 10px
```

4. Fix overflow by: reducing font_size, reducing row_h, shrinking image height,
   or moving table start position up.

### Table sizing formula

```python
# Available space: CONTENT_TOP (0.83") to SLIDE_H - 0.22" = 5.405"
# Table at y position with N rows at row_h each:
# y + N * row_h must be < 5.405"
# Example: y=3.8, row_h=0.2, N=7 -> 3.8 + 1.4 = 5.2 < 5.405 -> OK
```

## Common pitfalls

- **Table row height too large**: 0.3" × 7 rows = 2.1" can overflow when
  starting at y=4.0. Use 0.2" or 0.22" for 6+ row tables.
- **Chart image too tall**: When a table follows a chart, limit chart height
  to leave room. Use `_add_picture` with `max_h` parameter.
- **Missing CJK font**: matplotlib needs CJK font for Chinese labels. Auto-detect
  with `matplotlib.font_manager.findfont()` across WenQuanYi/Noto/SimHei.
- **samtools not in PATH**: When running generate_report.py locally (not in
  SIF), samtools must be available. The script calls it via subprocess.
### Auto-detect samples: If `--samples` is empty, auto-detect from
  `common/4_per_gene_bam/` or `common/3_raw_bam/` directory listing.
- **Pyright type errors with python-pptx**: `Presentation()` is typed as a
  function by Pyright, causing "Expected class" errors on type hints. Use
  string annotations or `# type: ignore` -- these are false positives.

## Excel sheet conventions (critical)

### Always include sample identifier column when merging multi-sample data

When combining data from multiple samples into a single sheet, ADD a `sample_id` column as the FIRST column. Without it, peaks/reads from different samples are indistinguishable:

```python
# CORRECT — sample_id first
_write_dicts(ws, [{**r, "sample_id": s} for s in ip_samples for r in load_peaks(peaks_dir, s)],
             ["sample_id", "chr", "start", "end", "name", "score", ...])

# WRONG — no way to tell which sample each row belongs to
_write_dicts(ws, [r for s in ip_samples for r in load_peaks(peaks_dir, s)],
             ["chr", "start", "end", "name", "score", ...])
```

### Don't include redundant data sheets

narrowPeak BED and MACS3 xls contain the same peaks — xls has more columns (fold_enrichment, pileup, abs_summit). Include ONLY the xls sheet, not both. Same for broad: use broad_peaks.xls, not broadPeak BED.

### Separate narrow and broad analysis outputs into different sheets

MACS3 produces both narrow and broad cutoff analysis files. They MUST go in separate sheets ("Cutoff Narrow", "Cutoff Broad") — putting both in one "Cutoff Analysis" sheet causes data overwrite since both have the same column structure.
- **ncRNAseq_report data collection**: Parses raw FASTQ counts (gzip line count // 4),
  trimming stats (regex on `trimming_statistics_1.txt` / `_2.txt`),
  STAR Log.final.out (regex on `Number of input reads`, `Uniquely mapped reads number`, etc.),
  per-gene manifests (`genes.tsv` with `assigned_records` column),
  and Tailer CSVs (`Count`, `End_Position`, `Tail_Length`, `Tail_Sequence` columns).
  Uses `samtools view -c` via subprocess for BAM read counts.
  Group inference from sample name: "7sl" -> 7SL, "u1" -> U1.
- **ncRNAseq_report slide structure** (9 slides): title, workflow overview (5-stage card layout),
  read flow (stacked bar of raw/dedup/trim/STAR/gene counts), trimming stats,
  STAR mapping (dual chart: final BAM + pass1 breakdown), gene assignments (stacked bar by group + table),
  Tailer summary (tail% + end position), tail length distribution (by group), conclusion (stat cards).
- **Table overflow in gene assignment slide**: With 6+ samples, use row_h=0.2" and font_size=9.
  Chart image height should be limited to 2.8" to leave room for the table below.
