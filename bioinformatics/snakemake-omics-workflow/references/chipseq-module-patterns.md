# ChIP-seq Module Patterns

Config keys specific to ChIP-seq workflows:

```python
indir = config.get("indir", "input")           # BAM directory (from bowtie2)
peaks_indir = config.get("peaks_indir", "peaks")  # Peaks directory (from macs3)
samples = config.get("samples", [])
ip_samples = config.get("ip_samples", [])
input_samples = config.get("input_samples", [])
sample_ip_input_map = config.get("sample_ip_input_map", {})  # IP -> input control mapping
```

## Nested Procedure config for sub-tools

When a tool is a sub-command of a package (bedtools has intersect, bamtobed, etc.),
use the parent tool name in Procedure and pass the sub-command in the shell script:

```python
params:
    bedtools = config.get("Procedure", {}).get("bedtools") or "bedtools",
    samtools = config.get("Procedure", {}).get("samtools") or "samtools"
# In script: $BEDTOOLS intersect -a BAM -b PEAK -u
```

Config JSON:
```json
{
    "Procedure": {
        "bedtools": "bedtools",
        "samtools": "samtools"
    }
}
```

Note: Prefer `bedtools intersect` over legacy `intersectBed` — same functionality, better maintained.

## Markdup vs Dedup — critical distinction for ChIP-seq

**markdup** (GATK4 via `gatk_prepare.smk`): adds read groups + flags PCR duplicates in BAM. Downstream tools like MACS3 handle filtering via `--keep-dup auto`. Output: `.sorted_markdup.bam`. Uses existing `modules/gatk/gatk_prepare.smk` — do NOT create a new markdup module.

**dedup** (samtools markdup -r via `igv.smk`): removes duplicate reads entirely. Suitable for visualization tracks (BigWig) but NOT for peak calling — loses information MACS3 needs. Output: `.dedup.bam`.

**ChIP-seq DAG (aligned with nf-core/chipseq):**
```
Align (bowtie2/bwa) → raw bam
    ├── gatk_prepare: AddOrReplaceReadGroups + MarkDuplicates → .sorted_markdup.bam
    │       ├── MACS3 peak calling (--keep-dup auto handles flagged dups)
    │       ├── FRiP score (uses .sorted_markdup.bam)
    │       └── HOMER annotation (on MACS3 peaks)
    └── igv dedup (samtools markdup -r) → .dedup.bam → BigWig (bamCoverage)
```

**Key rule:** MACS3 peak calling MUST receive markdup (flagged) BAM, NOT raw and NOT dedup-removed. The `--keep-dup auto` default correctly filters marked duplicates during peak calling.

**Subworkflow config pattern:**
```python
gatk_prepare_config = {
    "indir": bowtie2_config["outdir"],
    "outdir": f"{outdir}/common/4_markdup_bam",
    "logdir": logdir,
    "input_bam_substring": "",
    "Procedure": {
        "gatk": config.get("Procedure", {}).get("gatk") or "gatk",
        "samtools": config.get("Procedure", {}).get("samtools") or "samtools"
    },
    "Params": {"gatk": config.get("Params", {}).get("gatk", {})},
    "addReadsGroup": config.get("addReadsGroup", {}),
    "genome": {"fasta": config.get("genome", {}).get("fasta")}
}
```

**Output naming:** `.sorted_markdup.bam` + `.sorted_markdup.bai` + `.Markdup-metrics.txt`

**samtools markdup pipeline (igv.smk, with -r, for tracks only):**
```bash
samtools sort -n -@ ${threads} input.bam |
  samtools fixmate -m - - |
  samtools sort -@ ${threads} - |
  samtools markdup -r -@ ${threads} - output.dedup.bam &&
  samtools index -@ ${threads} output.dedup.bam
```

## IP vs Input sample handling — critical rules

**Input samples do NOT get peak calling.** MACS3 only runs on `ip_samples`. Input BAMs serve as `-c` control for IP peak calling. Input samples have no narrowPeak/broadPeak/annotation files.

**`sample_ip_input_map` must be built from design_pairs, NOT from a default.** The correct mapping comes from `design_pair.exp_sample_id → design_pair.ctr_sample_id`. A bug in node.py once overwrote all IPs to use `input_samples[0]` — never do this:

```python
# ❌ WRONG — overwrites correct design-based mapping
if input_samples:
    default_input = input_samples[0]
    for ip_sample in ip_samples:
        sample_ip_input_map[ip_sample] = default_input

# ✅ CORRECT — mapping already set from design_pairs at line 430
for design_pair in design_pairs:
    sample_ip_input_map[design_pair.exp_sample_id] = design_pair.ctr_sample_id
```

**node.py outfiles for PeakCalling:**
- IP samples: peaks, annotation, FRiP, heatmap, TE overlap, bigwig, markdup
- Input samples: markdup, bigwig only (no peaks/annotation/FRiP)
- Global: cutoff_analysis.png, te_family_overlap.png, tracks, report

## TE overlap enrichment analysis (reads-based)

For computing TE subfamily enrichment (IP vs Input), count reads in peak-TE overlap regions from both BAMs using `bedtools coverage -counts`:

```python
# In intersect_te.py — after bedtools intersect finds peak-TE overlaps:
# 1. Extract overlap regions as BED
# 2. Filter duplicates: samtools view -b -F 1024 -o tmp.bam input.bam
# 3. Count reads: bedtools coverage -a regions.bed -b tmp.bam -counts
# 4. Output per-locus: sample_id, te_subfamily, te_length, interval_overlap_frac, overlap_peak_count, ip_reads, input_reads
```

**Pitfall: `bedtools coverage -F` is a fraction (0.0-1.0), NOT a samtools flag.** `bedtools coverage -F 1024` fails with `-F must be in the range (0.0, 1.0]`. To exclude PCR duplicates, pre-filter with samtools:
```bash
samtools view -b -F 1024 -o tmp.bam input.bam   # filter dups
bedtools coverage -a regions.bed -b tmp.bam -counts  # count reads
```

**Enrichment plot:** log2(sum(ip_reads) / sum(input_reads)) per TE subfamily. Both reads are in the same TSV row — no need for IP/Input condition grouping.

**TE GTF hierarchy:** `class_id` (LINE/SINE/LTR) → `family_id` (L1/B2/ERV1) → `gene_id` (Lx2B2/B1_Mur1 — most specific). Use `gene_id` for subfamily-level analysis.

## MACS3 cutoff analysis plot

A combined cutoff plot for all IP samples should be a separate rule:

```python
rule macs3_cutoff_plot:
    input:
        cutoffs = expand(outdir + "/{sample_id}/{sample_id}_cutoff_analysis.txt", sample_id=ip_samples),
    output:
        plot = outdir + "/cutoff_analysis.png",
```

The plotting script uses `matplotlib` — if the macs3 SIF doesn't have it, add `matplotlib>=3.5.0` to `macs3.yaml` and rebuild the SIF.

## Report module conventions (PPT + Excel)

**PPT style must match RNAseq_report:**
- Light theme: `C_BG = 0xF6,0xF8,0xFB`, `C_NAVY = 0x18,0x25,0x43` header bar
- Standard 16:9: `SLIDE_W=10.0, SLIDE_H=5.625`
- Helper functions: `_header()`, `_table()`, `_bullets()`, `_textbox()`, `_add_img()`

**Excel must collect ALL module data.** For PeakCalling, this includes:
1. Overview, 2. TrimGalore stats, 3. Bowtie2 alignment, 4. Bowtie2 metrics, 5. MarkDuplicates, 6. MACS3 Info, 7. Peak Count, 8. narrowPeak (all columns), 9. broadPeak, 10. MACS3 xls (fold_enrichment), 11. Summits, 12. Cutoff Analysis, 13. FRiP, 14. HOMER Annotation (full 19 columns), 15. Region Distribution, 16. Top Genes, 17. TSS Distance, 18. TE Overlap Counts, 19. TE Subfamily Overlap, 20. QC Summary

**CLI arg passing for `nargs="+"` args:** Each sample must be a separate `--samples` argument, NOT joined into one string:
```python
# ❌ WRONG — 'Pop5IP Rpp14IP Rpp21IP' becomes one string
cmd += ["--samples", " ".join(samples)]

# ✅ CORRECT — each sample is a separate arg
for s in samples:
    cmd += ["--samples", s]
```

**Report module config must pass correct directory paths:**
```python
PeakCalling_report_config = {
    "peaks_dir": f"{outdir}/results/peaks",       # NOT outdir/peaks
    "annotation_dir": f"{outdir}/results/annotation",  # NOT outdir/annotation
    "qc_dir": f"{outdir}/QC/3_frip_score",
    "log_sample_dir": f"{logdir}/sample",         # NOT logdir
    "markdup_dir": f"{outdir}/common/4_markdup_bam",
}
```

## Wildcard constraints for repeated patterns

When an output pattern has `{sample_id}` appearing twice (e.g., `outdir/{sample_id}/{sample_id}.fastqc.txt`), Snakemake's greedy regex may match `Pop5IP/Pop5IP.fastqc.txt` as the entire `sample_id`. Fix with:

```python
wildcard_constraints:
    sample_id = "[^/]+"
```

## FRiP score module pattern

FRiP = reads_in_peaks / total_mapped_reads

Command sequence:
1. `bedtools intersect -a BAM -b PEAK -u | samtools view -c -` — count reads in peaks
2. `samtools flagstat BAM | grep 'mapped (' | grep -v "primary" | head -1 | awk '{print $1}'` — total mapped reads
3. `awk "BEGIN {printf \"%.6f\", reads_in_peaks / total_mapped}\"` — calculate ratio

Output: `{sample_id}.FRiP.txt` with tab-separated `sample_id\tfrip_score`

Conda deps: `bedtools>=2.30.0`, `samtools>=1.15.1`

Thresholds: >= 0.3 for TFs (narrow), >= 0.2 for histone marks (broad).

## HOMER annotatePeaks module pattern

Command: `annotatePeaks.pl <peak> <genome_fasta> -gtf <gtf> > output.txt`

Config keys:
- `Procedure.annotatePeaks` (default: `annotatePeaks.pl`)
- `genome.fasta`, `genome.gtf`

Output: `{sample_id}/{sample_id}_peaks.annotatePeaks.txt`

HOMER annotation columns (19 total):
PeakID, Chr, Start, End, Strand, Peak Score, Focus Ratio/Region Size, Annotation, Detailed Annotation, Distance to TSS, Nearest PromoterID, Entrez ID, Nearest Unigene, Nearest Refseq, Nearest Ensembl, Gene Name, Gene Alias, Gene Description, Gene Type

Conda deps: `homer>=4.11`

## Full PeakCalling config JSON

The `config/PeakCalling.json` must include all Procedure/Params keys for every module in the DAG:

```json
{
    "Procedure": {
        "trim_galore": null, "bowtie2-build": null, "bowtie2": null,
        "samtools": null, "gatk": null, "bamCoverage": null,
        "macs3": null, "bedtools": null, "annotatePeaks": null
    },
    "Params": {
        "trim_galore": {"quality": 25},
        "gatk": {"javaOptions": "-Xmx30g", "tmp-dir": null},
        "bamCoverage": {"binSize": 50, "normalizeUsing": "CPM", "offset": null, "extendReads": false},
        "macs3": {"bw": 200, "pvalue": "1e-5", "genome_size": "mm"},
        "peak_te_overlap": {"method": "reads", "sort_by": "te_length", "top_n": 30, "combine": false}
    },
    "addReadsGroup": {"RGLB": "lib1", "RGPL": "ILLUMINA", "RGPU": "unit1"},
    "genome": {"fasta": null, "gtf": null, "bowtie2_index_prefix": null, "te_gtf": null}
}
```

**MACS3 Params:**
- `bw`: bandwidth for model building (default 200)
- `pvalue`: p-value cutoff for peak calling (default "1e-5")
- `genome_size`: genome size shorthand — "hs" (human), "mm" (mouse), etc.

**peak_te_overlap Params:**
- `method`: "reads" (IP/Input read ratio), "count" (peak count), "interval" (overlap fraction)
- `sort_by`: "te_length" (default) or "enrichment"
- `top_n`: number of subfamilies to show (default 30)
- `combine`: false = separate plot per IP:Input pair, true = single combined plot

## run.py endpoint function

`runPeakCalling()` outfiles must match the FINAL outputs (markdup, peaks, FRiP, HOMER), NOT intermediate files (trimmed fastq, raw bam). Intermediate files are tracked by Snakemake DAG automatically:

```python
# Final endpoints only
outfiles.append(f"{outdir}/common/4_markdup_bam/{sid}/{sid}.sorted_markdup.bam")
outfiles.append(f"{outdir}/results/tracks/{sid}.bigwig")
outfiles.append(f"{outdir}/results/peaks/{sid}/{sid}_peaks.narrowPeak")
outfiles.append(f"{outdir}/QC/3_frip_score/{sid}/{sid}.FRiP.txt")
outfiles.append(f"{outdir}/results/annotation/{sid}/{sid}_peaks.annotatePeaks.txt")
outfiles.append(f"{outdir}/results/te_overlap/{sid}/{sid}_te_subfamily_overlap.tsv")
outfiles.append(f"{outdir}/results/peaks/cutoff_analysis.png")
outfiles.append(f"{outdir}/results/te_overlap/te_family_overlap.png")
outfiles.append(f"{outdir}/PeakCalling_report.pptx")
outfiles.append(f"{outdir}/PeakCalling_report.xlsx")
```
