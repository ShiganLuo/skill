---
name: chipseq-peak-calling-workflow
description: ChIP-seq Peak Calling subworkflow for Omics Snakemake framework - adds FRiP score, HOMER annotation, BigWig tracks to MACS3 pipeline
tags: [chipseq, peak-calling, macs3, homer, frip, snakemake]
---

# ChIP-seq Peak Calling Workflow

## Overview

Complete ChIP-seq peak calling subworkflow for the Omics Snakemake framework, ported from the nf-core/chipseq Nextflow pipeline.

## Pipeline Steps

1. **FastQC (raw)** - Quality check raw reads
2. **Trim Galore** - Adapter trimming
3. **FastQC (trimmed)** - Quality check trimmed reads
4. **Bowtie2** - Alignment to reference genome
5. **BigWig tracks** - Normalized coverage tracks (bamCoverage)
6. **MACS3** - Peak calling
7. **FRiP Score** - Fraction of Reads in Peaks QC metric
8. **HOMER** - Peak annotation with genomic features

## Key Metrics

- **FRiP Score**: reads_in_peaks / total_mapped_reads
  - >= 0.3 for transcription factors (narrow peaks)
  - >= 0.2 for histone marks (broad peaks)

## File Structure

```
Omics/
├── modules/
│   ├── frip_score/
│   │   ├── frip_score.smk
│   │   └── frip_score.yaml
│   └── homer/
│       ├── homer.smk
│       └── homer.yaml
└── subworkflow/
    └── PeakCalling.smk
```

## Config Requirements

```yaml
# Procedure tools
Procedure:
  samtools: "samtools"
  bedtools: "bedtools"
  macs3: "macs3"
  bamCoverage: "bamCoverage"
  annotatePeaks: "annotatePeaks.pl"

# MACS3 parameters
Params:
  macs3:
    bw: 200
    pvalue: "1e-5"
    genome_size: "mm"  # hs (human), mm (mouse), etc.
    cutoff_analysis: false  # true → --cutoff-analysis (~30x slower)

# Genome references
genome:
  fasta: "/path/to/genome.fa"
  gtf: "/path/to/genes.gtf"
  bowtie2_index_prefix: "/path/to/bowtie2_index"

# Samples
ip_samples: ["sample1", "sample2"]
input_samples: ["input1", "input2"]
sample_ip_input_map:
  sample1: "input1"
  sample2: "input2"
```

## Pitfalls

- MACS3 module expects BAM at `indir/{sample_id}/{sample_id}.sorted_markdup.bam` (markdup BAM from gatk_prepare, NOT raw BAM)
- HOMER annotatePeaks.pl requires GTF with gene annotations
- FRiP score uses `bedtools intersect -u` (not -c) to count unique reads
- MACS3 `cutoff_analysis`: when `true`, the module must append `--cutoff-analysis` to the cmd list. A common bug is logging the flag but forgetting to append it (see snakemake-omics-workflow pitfall #14)
- After running cutoff_analysis, interpret results with `references/cutoff_analysis_guide.md` — includes column meanings, elbow point detection, and threshold selection guide
