# ChIP-seq Report Module (Python-based)

Python-based report generator using `python-pptx` + `matplotlib` + `openpyxl`. Generates PPT + Excel.

## Module Structure

```
modules/PeakCalling_report/
├── PeakCalling_report.smk   # Snakemake rules (run: block + shlex.quote)
├── PeakCalling_report.yaml  # Conda env (python-pptx, matplotlib, openpyxl, numpy)
└── bin/
    └── generate_report.py   # Data loading + plotting + PPT + Excel generation
```

## report.yaml

```yaml
name: report
channels:
  - conda-forge
  - defaults
dependencies:
  - python>=3.9
  - python-pptx>=0.6.21
  - matplotlib>=3.5.0
  - openpyxl>=3.0.0
  - numpy>=1.21.0
```

## report.smk — configurable input directories

Input directories are configurable through config (not hardcoded from outdir) to support subworkflow import where paths may differ (e.g., peaks under `results/peaks/` not `peaks/`):

```python
include: "../common/common.smk"
import shlex
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")

# Configurable input directories (allow override for subworkflow import)
peaks_dir = config.get("peaks_dir", outdir + "/peaks")
annotation_dir = config.get("annotation_dir", outdir + "/annotation")
qc_dir = config.get("qc_dir", outdir + "/QC/3_frip_score")
log_sample_dir = config.get("log_sample_dir", logdir)
markdup_dir = config.get("markdup_dir", outdir + "/common/4_markdup_bam")
```

Subworkflow passes explicit paths:
```python
report_config = {
    "outdir": outdir,
    "logdir": f"{logdir}/sample",
    "peaks_dir": f"{outdir}/results/peaks",
    "annotation_dir": f"{outdir}/results/annotation",
    "qc_dir": f"{outdir}/QC/3_frip_score",
    "log_sample_dir": f"{logdir}/sample",
    "markdup_dir": f"{outdir}/common/4_markdup_bam",
    "Params": {"report": config.get("Params", {}).get("report", {})}
}
```

## Excel Output

The report script generates both PPT and Excel. Excel uses openpyxl with 20+ sheets covering every module:

1. **Overview** — sample counts, sample lists
2. **TrimGalore** — R1/R2 total, adapters, passed, quality cutoff (all samples)
3. **Bowtie2 Alignment** — total reads, paired%, concordant rates, overall%
4. **Bowtie2 Metrics** — detailed per-alignment stats (120+ columns)
5. **MarkDuplicates** — read pairs, dup pairs, dup rate, optical dups, unmapped, est lib size
6. **MACS3 Info** — tags treatment/control, fragment length
7. **Peak Count** — narrow/broad peaks, FRiP score
8. **narrowPeak** — all peak data (chr, start, end, score, signalValue, pvalue, qvalue)
9. **broadPeak** — broad peak data
10. **MACS3 xls** — fold enrichment, pileup, pvalue, qvalue
11. **Summits** — summit positions with scores
12. **Cutoff Analysis** — pvalue/qvalue thresholds vs peak counts
13. **FRiP** — per-sample FRiP scores
14. **HOMER Annotation** — full annotation (peak_id, chr, start, end, annotation, gene_name, etc.)
15. **Region Distribution** — promoter/exon/intron/intergenic/tts/other per sample
16. **Top Genes** — gene, position, score, distance to TSS
17. **TSS Distance** — within 1kb/5kb/10kb counts and percentages
18. **TE Overlap Counts** — TE class, peak count, total peaks, overlap ratio
19. **TE Subfamily Overlap** — per-locus overlap fraction, read counts
20. **TE Family Overlap** — combined cross-sample TE family data
21. **Peak-Centric TE** — per-peak TE count, TE types, TE coverage fraction
22. **QC Summary** — combined table with status column

Pass `--excel-output` from smk rule via cmd list + shlex.quote:
```python
cmd = [
    "python3", params.script,
    "--output", output.report,
    "--excel-output", output.excel,
    ...
]
```

Output: `outdir/PeakCalling_report.xlsx` (alongside the PPT).

## Report Snakefile input completeness

The report rule must list ALL module outputs as explicit `input:` dependencies to ensure proper DAG tracking. Missing inputs cause stale reports.

```python
rule generate_report:
    input:
        # MACS3 peaks
        narrow_peaks = expand(peaks_dir + "/{sample}/{sample}_peaks.narrowPeak", sample=ip_samples),
        broad_peaks = expand(peaks_dir + "/{sample}/{sample}_broad_peaks.broadPeak", sample=ip_samples),
        xls_peaks = expand(peaks_dir + "/{sample}/{sample}_peaks.xls", sample=ip_samples),
        summits = expand(peaks_dir + "/{sample}/{sample}_summits.bed", sample=ip_samples),
        cutoff = expand(peaks_dir + "/{sample}/{sample}_cutoff_analysis.txt", sample=ip_samples),
        # FRiP QC
        frip = expand(qc_dir + "/{sample}/{sample}.FRiP.txt", sample=ip_samples),
        # HOMER annotation
        annotations = expand(annotation_dir + "/{sample}/{sample}_peaks.annotatePeaks.txt", sample=ip_samples),
        # Bowtie2 (logs + metrics for ALL samples)
        bowtie2_logs = expand(log_sample_dir + "/{sample}/bowtie2_align.log", sample=all_samples),
        bowtie2_metrics = expand(metrics_dir + "/{sample}/{sample}_bowtie2_metrics.txt", sample=all_samples),
        # MarkDuplicates (ALL samples)
        markdup_metrics = expand(markdup_dir + "/{sample}/{sample}.Markdup-metrics.txt", sample=all_samples),
        # TrimGalore (ALL samples, R1 + R2)
        trim_stats_r1 = expand(trim_dir + "/{sample}/trimming_statistics_1.txt", sample=all_samples),
        trim_stats_r2 = expand(trim_dir + "/{sample}/trimming_statistics_2.txt", sample=all_samples),
        # TE overlap
        te_overlap_counts = expand(te_dir + "/{sample}/{sample}_te_overlap_counts.tsv", sample=ip_samples),
        te_subfamily = expand(te_dir + "/{sample}/{sample}_te_subfamily_overlap.tsv", sample=ip_samples),
        te_family = te_dir + "/te_family_overlap.tsv",
        peak_centric_te = expand(te_dir + "/{sample}/{sample}_peak_centric_te.tsv", sample=ip_samples),
        te_enrichment = expand(te_dir + "/{sample}_vs_{input}_enrichment.png",
                               zip, sample=ip_samples,
                               input=[sample_ip_input_map.get(s, "") for s in ip_samples]),
    ...
```

## argparse: use action="append" for repeated flags

When Snakefile builds cmd with `for s in samples: cmd += ["--samples", s]`, the script MUST use `action="append"` not `nargs="+"`. With `nargs="+"`, repeated flags overwrite — `--samples A --samples B` gives `['B']` not `['A', 'B']`.

## PPT slide design (ChIP-seq)

Standard 13-15 slide deck:
1. Title slide
2. Workflow overview (pipeline steps + sample table)
3. TrimGalore QC (adapter rate + passed reads charts + table)
4. Bowtie2 Alignment (alignment rate bar + concordant table)
5. MarkDuplicates (dup rate bar + table)
6. Peak Calling + FRiP (peak count + FRiP dual chart + table)
7. Peak Annotation (region distribution grouped bar)
8. TSS Distance (histogram + within 1kb/5kb/10kb table)
9. Top Target Genes (per-sample bullet list)
10. TE Enrichment (IP vs Input enrichment PNGs)
11. Peak-TE Overlap (family overlap bar + top TE table)
12. Peak-Centric TE (coverage distribution + TE count histogram + top TE-rich peaks + stats)
13. Summary & QC Assessment (combined status table)

## i18n (Chinese/English) Support

Define `I18N` dict with all user-facing strings keyed by language code. `t(key, lang)` helper. Chart titles always in English (matplotlib CJK font issue). PPT text follows `--lang`.

## Data Loading Functions

Each returns None/default on missing file:
- `load_bowtie2(log_dir, sample)` → float|None (alignment rate %)
- `load_markdup(metrics_dir, sample)` → dict|None (read_pairs, dup_rate, etc.)
- `load_frip(qc_dir, sample)` → float|None (FRiP fraction)
- `load_peak_count(peaks_dir, sample)` → int (0 if missing)
- `load_annotation(annotation_dir, sample)` → dict|None (category→count)
- `load_top_genes(annotation_dir, sample, n=5)` → list[dict]

## Plotting

All use DPI=300, English labels only. Returns temp PNG path.
- `plot_alignment(rates)` — bar chart with 80% threshold
- `plot_peak_and_frip(samples, peaks, frips)` — dual bar chart with 20% FRiP threshold
- `plot_cutoff(cutoffs)` — peak score distribution
- `plot_annotation(anns, lang)` — grouped bar by region type
- `plot_tss_distance(annotation_dir, samples)` — histogram with 1kb/5kb lines

## Pitfalls

1. Matplotlib CJK fonts → use English for chart labels
2. Every `load_*` must return None on missing file
3. Use `run:` block + `shlex.quote()` (project convention), not `shell:`
4. Save scripts in `bin/`, not as throwaway /tmp scripts
5. Cleanup temp PNGs after PPT is saved
6. Generic design — parameterize everything from CLI args
7. HOMER column: Gene Name at index 15, Distance to TTS at index 9
8. `tf.auto_size = None` on textboxes to prevent overflow
