# ChIP-seq Peak Calling Report Structure

Standard slide structure for ChIP-seq peak calling analysis PPT reports.

## Slide Order

1. **Title** — project name, sample list, genome, date, pipeline summary
2. **Workflow Overview** — numbered step diagram (FastQC → Trim → Align → MarkDup → PeakCall → Annotate → FRiP) + sample info table
3. **Alignment Statistics** — bar chart of alignment rates per sample, QC threshold line (80%)
4. **MarkDuplicates Statistics** — table: read pairs, duplicate pairs, dup rate, unmapped, library size
5. **Peak Calling Results** — dual chart: peak counts + FRiP scores, threshold line at 20%
6. **Peak Annotation Distribution** — pie charts per sample (Promoter, Exon, Intron, Intergenic, TTS)
7. **Top Target Genes** — per-sample table of top peaks by score, shared genes highlighted
8. **Summary & QC Assessment** — combined QC table + per-sample conclusions + recommendations

## Key QC Metrics

| Metric | Threshold | Source |
|--------|-----------|--------|
| Alignment rate | >80% | bowtie2 log |
| Duplication rate | <50% | GATK MarkDuplicates metrics |
| FRiP score | ≥20% | peak reads / total mapped reads |

## Data Sources

- Alignment: `{sample}_bowtie2_metrics.txt` or `bowtie2_align.log`
- Duplicates: `{sample}.Markdup-metrics.txt` (GATK format, tab-separated)
- Peaks: `{sample}_peaks.xls` (MACS3 output)
- Annotations: `{sample}_peaks.annotatePeaks.txt` (HOMER output)
- FRiP: `{sample}.FRiP.txt`
- Cutoff analysis: `{sample}_cutoff_analysis.txt` (MACS3 --cutoff-analysis)

## Pitfalls

- **Review existing deliverables first.** When user asks to "make a PPT" and one already exists, READ it first to match structure/style. Use `python -m markitdown existing.pptx` or `pptx` library to inspect.
- **Pop5 vs Rpp naming.** Samples may have different naming conventions (Pop5, Rpp14, Rpp21). Always check all sample directories, not just the ones mentioned in conversation.
- **FRiP interpretation.** FRiP < 20% does NOT mean the experiment failed — it depends on antibody quality and target type. Flag as "below threshold" but don't call it a failure.
- **Matplotlib CJK fonts.** Use English labels in charts if no CJK font available, or configure `rcParams["font.sans-serif"]` to include a CJK font.
