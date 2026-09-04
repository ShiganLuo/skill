# ChIP-seq QC Report PPT Generation

Generate a 9-slide PPT from PeakCalling output using pptxgenjs.

## Data Collection Script

Collect all QC metrics from the output directory:

```python
from hermes_tools import terminal

base = "<outdir>/PeakCalling"

# Bowtie2 alignment rates (from logs, not metrics file)
for s in samples:
    r = terminal(f"grep 'overall alignment rate' {base}/log/{s}/bowtie2_align.log")
    # e.g. "85.50% overall alignment rate"

# MarkDuplicates metrics (GATK format: LIBRARY header + data row)
for s in samples:
    r = terminal(f"grep -A1 'LIBRARY' {base}/common/4_markdup_bam/{s}/{s}.Markdup-metrics.txt")
    # Columns: LIBRARY UNPAIRED_READS_EXAMINED READ_PAIRS_EXAMINED ... PERCENT_DUPLICATION ESTIMATED_LIBRARY_SIZE

# Peak counts
for s in ip_samples:
    r = terminal(f"wc -l {base}/peaks/{s}/{s}_peaks.narrowPeak")

# FRiP scores (tab-separated: sample_id  score)
for s in ip_samples:
    r = terminal(f"cat {base}/QC/3_frip_score/{s}/{s}.FRiP.txt")

# Annotation categories (column 8 of HOMER output, simplified)
for s in ip_samples:
    r = terminal(f"tail -n +2 {base}/annotation/{s}/{s}_peaks.annotatePeaks.txt | "
                  "awk -F'\\t' '{split($8,a,\" \"); cat=a[1]; ... print cat}' | sort | uniq -c | sort -rn")

# TSS distance distribution (column 10)
for s in ip_samples:
    r = terminal(f"tail -n +2 {base}/annotation/{s}/{s}_peaks.annotatePeaks.txt | "
                  "awk -F'\\t' '{d=$10; if(d<0)d=-d; ...}' | sort | uniq -c | sort -rn")

# Top peaks by score
for s in ip_samples:
    r = terminal(f"tail -n +2 {base}/annotation/{s}/{s}_peaks.annotatePeaks.txt | "
                  "sort -t$'\\t' -k6 -rn | head -5 | awk -F'\\t' '{...}'")
```

## PPT Structure (9 slides)

| Slide | Title | Content |
|-------|-------|---------|
| 1 | 标题页 | Project name, samples, date, pipeline summary |
| 2 | 分析流程概览 | 8 step cards + sample info table |
| 3 | Bowtie2 比对统计 | Stat cards + bar chart + notes |
| 4 | GATK MarkDuplicates 统计 | Table + bar chart + notes |
| 5 | MACS3 Peak Calling 结果 | Peak count cards + FRiP cards + chart |
| 6 | Peak注释 — 基因组区域分布 | Two doughnut charts (Intergenic/Intron/Promoter/Exon/TTS) |
| 7 | 距离最近TSS分布 | Grouped bar chart + analysis notes |
| 8 | Top靶基因 | Two tables (top 5 peaks) + shared targets box |
| 9 | 总结与QC评估 | QC metric table + conclusion cards |

## Design Guidelines

- Color palette: Genomics theme (dark navy `1B2A4A`, teal accent `16C79A`, coral warning `E94560`)
- Stat cards: large number (32-44pt) + accent top bar + label below
- Charts: clean background, muted grid, data labels on bars
- Tables: dark header row, alternating rows optional
- All text in Chinese (用户偏好)
- FRiP thresholds: use `≥20%` not `≥0.2` — avoid unit confusion
- Mark FRiP values below threshold with ⚠

## PptxGenJS Setup

```bash
cd /tmp && npm init -y && npm install pptxgenjs
node generate_report.js
```

## FRiP Threshold Interpretation

FRiP = reads_in_peaks / total_mapped_reads (as fraction)

- Good TF ChIP: ≥ 0.3 (30%)
- Good histone ChIP: ≥ 0.2 (20%)
- Typical display: show as percentage (0.26%, 1.03%)
- Threshold in PPT: write as "≥20%" NOT "≥0.2" to match percentage display

## Pitfalls

1. **Unit mismatch**: If FRiP values show as "0.26%" and threshold says ">0.2", users get confused (0.2 = 20%). Always use consistent units.
2. **Approximate lib size**: GATK estimated_library_size is approximate (~23M). Display with "~" prefix.
3. **Bowtie2 metrics file ≠ alignment summary**: The `_bowtie2_metrics.txt` file has detailed per-read stats. The "overall alignment rate" comes from the bowtie2 log file.
4. **HOMER annotation categories**: Column 8 has detailed annotations like "intron (ENSMUST..., intron 1 of 1)". Simplify to first word only for the pie chart.
5. **Doughnut/pie charts MUST have explicit color legend**: PptxGenJS `legendPos: "b"` may render poorly or invisibly in LibreOffice. Always add a manual legend card: colored rectangles + text labels (e.g. "内含子 (Intron)"). Also add a per-chart data table below showing count + percentage for each category.

## Annotation Excel Export

Export HOMER annotation results to a multi-sheet Excel:

```python
import pandas as pd
dfs = []
for sample in ip_samples:
    df = pd.read_csv(f"{base}/annotation/{sample}/{sample}_peaks.annotatePeaks.txt", sep="\t")
    df.columns.values[0] = "PeakID"
    df.insert(0, "Sample", sample)
    dfs.append(df)
merged = pd.concat(dfs, ignore_index=True)
merged["Annotation_Category"] = merged["Annotation"].apply(
    lambda x: str(x).split("(")[0].strip() if pd.notna(x) else "Unknown")
with pd.ExcelWriter(outpath, engine="openpyxl") as writer:
    merged[key_cols].to_excel(writer, sheet_name="All_Peaks", index=False)
    merged.groupby(["Sample","Annotation_Category"]).size().reset_index(name="Count").to_excel(
        writer, sheet_name="Summary", index=False)
    merged.nlargest(30, "Peak Score")[key_cols].to_excel(writer, sheet_name="Top30", index=False)
    merged[merged["Annotation_Category"].str.contains("promoter",case=False,na=False)][key_cols].to_excel(
        writer, sheet_name="Promoter_Peaks", index=False)
```
