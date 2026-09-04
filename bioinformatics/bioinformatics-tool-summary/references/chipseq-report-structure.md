# ChIP-seq Peak Calling Report Structure

Standard slide structure for ChIP-seq peak calling analysis PPT reports.

## Slide Order

1. **Title** — project name, sample list, genome, date, pipeline summary
2. **Workflow Overview** — numbered step diagram (FastQC → Trim → Align → MarkDup → PeakCall → Annotate → FRiP) + sample info table
3. **TrimGalore QC** — dual chart (adapter content % + passed reads M) + table (total/adapters/passed per sample, R1)
4. **Alignment Statistics** — bar chart of alignment rates per sample, QC threshold line (80%) + table with concordant 1x / >1x columns
5. **MarkDuplicates Statistics** — dup rate bar chart + table: read pairs, duplicate pairs, dup rate, unmapped, library size
6. **Peak Calling Results** — dual chart: peak counts + FRiP scores, threshold line at 20%
7. **Peak Annotation Distribution** — grouped bar chart per sample (Promoter, Exon, Intron, Intergenic, TTS, Other)
8. **TSS Distance Distribution** — density histogram + table (within 1kb/5kb/10kb counts and percentages)
9. **Top Target Genes** — per-sample top-N genes by score with position and TSS distance
10. **TE Enrichment Analysis** — IP vs Input enrichment PNGs (one per IP-input pair)
11. **Peak-Centric TE Analysis** — TE coverage fraction distribution + TE count per peak + top TE-rich peaks table
12. **Summary & QC Assessment** — combined QC table + per-sample conclusions + recommendations

## Key QC Metrics

| Metric | Threshold | Source |
|--------|-----------|--------|
| Alignment rate | >80% | bowtie2 log |
| Duplication rate | <50% | GATK MarkDuplicates metrics |
| FRiP score | ≥20% | peak reads / total mapped reads |

## Excel Sheet Order

1. Overview — analysis metadata (n_ip, n_input, sample lists)
2. MACS3 Narrow Peaks — narrowPeak xls with fold_enrichment (sample_id, chr, start, end, length, abs_summit, pileup, pvalue, fold_enrichment, qvalue, name)
3. MACS3 Broad Peaks — broadPeak xls (no abs_summit, 9 columns)
4. MACS3 Peak Summits — peak summit positions (sample_id, chr, start, end, name, score)
5. Cutoff Narrow — MACS3 narrow cutoff analysis
6. Cutoff Broad — MACS3 broad cutoff analysis
7. HOMER Annotation — full peak annotation with gene info
8. Region Distribution — promoter/exon/intron/intergenic/tts/other counts
9. Top Genes — top-N target genes by score
10. TSS Distance — distance to TSS distribution
11. TE Subfamily Overlap — per-locus TE overlap with te_class column
12. Peak-Centric TE — per-peak TE count, types, coverage fraction
13. QC Summary — consolidated QC (last sheet): Trim + Align + MarkDup + MACS3 + Peak + FRiP + Bowtie2 Metrics + Status

## Data Sources

- TrimGalore: `{trim_dir}/{sample}/trimming_statistics_1.txt`, `trimming_statistics_2.txt`
- Alignment: `{sample}_bowtie2_metrics.txt` or `bowtie2_align.log`
- Duplicates: `{sample}.Markdup-metrics.txt` (GATK format, tab-separated)
- Peaks: `{sample}_peaks.xls` (MACS3 output), `{sample}_peaks.narrowPeak`, `{sample}_broad_peaks.broadPeak`
- Annotations: `{sample}_peaks.annotatePeaks.txt` (HOMER output)
- FRiP: `{sample}.FRiP.txt`
- Cutoff analysis: `{sample}_cutoff_analysis.txt` (MACS3 --cutoff-analysis)
- **TE overlap**: `{te_dir}/{sample}/{sample}_te_subfamily_overlap.tsv` (with `te_class` column), `{sample}/{sample}_peak_centric_te.tsv`
- **TE enrichment**: `{te_dir}/{ip}_vs_{input}_enrichment.png`

## Pitfalls

- **Review existing deliverables first.** When user asks to "make a PPT" and one already exists, READ it first to match structure/style. Use `python -m markitdown existing.pptx` or `pptx` library to inspect.
- **Pop5 vs Rpp naming.** Samples may have different naming conventions (Pop5, Rpp14, Rpp21). Always check all sample directories, not just the ones mentioned in conversation.
- **FRiP interpretation.** FRiP < 20% does NOT mean the experiment failed — it depends on antibody quality and target type. Flag as "below threshold" but don't call it a failure.
- **Matplotlib CJK fonts.** Use English labels in charts if no CJK font available, or configure `rcParams["font.sans-serif"]` to include a CJK font.
- **Consolidate per-sample QC into one sheet.** Don't create separate sheets for TrimGalore, Bowtie2, MarkDuplicates, MACS3 Info, Peak Count, FRiP. Merge into "QC Summary" with `模块_指标` prefixed column names (e.g., `Trim_Total_R1`, `Align_Overall_Pct`, `MarkDup_Dup_Rate`). Include Bowtie2 metrics (120+ columns) as additional columns. QC Summary should be the LAST sheet.
- **Excel sheet names must be intuitive.** "Summits" → "MACS3 Peak Summits". "Narrow xls" → "MACS3 Narrow Peaks". Sheet names should describe content, not file format.
- **Multi-sample data needs sample_id column.** When merging peaks/annotations from multiple samples into one sheet, always add `sample_id` as the first column. Use `[{**r, "sample_id": s} for s in samples for r in load_data(s)]`.
- **Remove redundant sheets.** narrowPeak and MACS3 xls contain the same peaks (0-based vs 1-based coordinates). Use only xls (has fold_enrichment). Remove narrowPeak/broadPeak sheets. Similarly, combined TSV files that just concatenate per-sample data are redundant if Excel already aggregates.
- **Conditional sheets for sparse data.** If a data source may be empty (e.g., TE overlap counts before pipeline re-run), only create the sheet if data exists. Use `if data: ws = wb.create_sheet(...)`.
- **Split narrow/broad cutoff into separate sheets.** Both use same column structure — one sheet would overwrite the other. Use "Cutoff Narrow" and "Cutoff Broad".
- **MACS3 narrow vs broad xls format differs.** Narrow has 10 columns (includes `abs_summit`). Broad has 9 columns (no `abs_summit`). Parse with different column counts and indices.
