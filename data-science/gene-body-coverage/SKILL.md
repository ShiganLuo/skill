---
name: gene-body-coverage
description: "Use when computing gene body coverage curves from BAM files. Optimized Python script with fetch+blocks, numpy binning, max normalization, and multiprocessing."
version: 1.0.0
author: luoshg
homepage: https://github.com/ShiganLuo
license: MIT
metadata:
  hermes:
    tags: [bioinformatics, genomics, coverage, bam, bed, rnaseq]
    related_skills: []
---

# Gene Body Coverage Analysis

## Overview

Compute gene body coverage curves from BAM files. The script calculates mean
read coverage across the gene body (5' → 3'), bins it into N percentiles, and
outputs both raw and normalized coverage (TSV + plot).

Located at:
  /mnt/GenePlus002/genecloud/Org_terminal/org_52/terminal/luoshg_15179660974/Data/sta/20260508_SV_freq_correction/workflow/gene/low_frequency_task/gene_body/geneBody_coverage_advanced.py

## When to Use

- Computing gene body coverage for RNA-seq QC
- Comparing coverage uniformity across samples (FFPE vs fresh tissue)
- Generating RSeQC-style gene body coverage plots
- Need fast coverage computation on many BAM files

Don't use for:
- Variant calling or SNV analysis
- Simple depth statistics (use samtools depth instead)

## Quick Start

```bash
python geneBody_coverage_advanced.py \
    -i <BAM_INPUT> \
    -b <BED_FILE> \
    -o <OUTPUT_PREFIX> \
    -t 4 \
    --bins 100 \
    --exclude-region UTR IVS \
    --plot-format png
```

## Arguments

| Flag | Long | Required | Default | Description |
|------|------|----------|---------|-------------|
| `-i` | `--input` | Yes | — | BAM: single path, comma-separated, directory, or list file |
| `-b` | `--bed` | Yes | — | BED/TSV annotation file |
| `-o` | `--out-prefix` | Yes | — | Output file prefix |
| `-t` | `--threads` | No | 4 | Worker processes (one per BAM) |
| | `--bins` | No | 100 | Number of bins across gene body |
| | `--min-length` | No | 100 | Minimum gene length (bp) |
| | `--exclude-region` | No | None | Region types to exclude (e.g. UTR IVS) |
| | `--plot-format` | No | png | png, pdf, svg |

## BED File Format

Tab-separated with header. Column names configurable in main() load_bed4() call.

```
chrom  start    end      strand  gene   region  trains
1      879582   880073   -       NOC2L  CDS     NM_015658
1      880073   880180   -       NOC2L  CDS     NM_015658
1      880180   880436   -       NOC2L  IVS     NM_015658
```

Required columns: chrom, start, end, strand
Optional: transcript_id (grouping), region_id (filtering)

## Output Files

1. `<prefix>.gene_body_summary.tsv` — Three columns:
   - bin: bin number (1-100)
   - mean_coverage: raw mean coverage per bin
   - normalized_coverage: per-gene max-normalized coverage (0-1)

2. `<prefix>.gene_body.<format>` — Line plot:
   - X: Gene body percentile (5' → 3')
   - Y: Normalized coverage (0-1), fixed range [0, 1.05]

## Algorithm

1. Load BED → group intervals by transcript_id → filter excluded regions
2. Build gene models: sort exons, compute length, pre-compute bin edges
3. Per gene: bam.fetch() + get_blocks() for coverage (10-50x faster than pileup)
4. Vectorized binning: np.add.reduceat(gene_vec, bin_edges)
5. Per-gene max normalization: bin_means / max(bin_means)
6. Average across genes, then across BAMs

## Programmatic Usage

```python
from geneBody_coverage_advanced import (
    get_bam_files, load_bed4, summarize_bams, write_summary, plot_curve
)

bams = get_bam_files("/data/bam_list.txt")
bed = load_bed4("genes.bed", transcript_id_col="trains",
                region_id_col="region", exclude_region=["UTR", "IVS"])

mean_curve, norm_curve = summarize_bams(bams, bed, bins=100, threads=4)

write_summary("output.tsv", mean_curve, norm_curve)
plot_curve("output.png", norm_curve)
```

## Dependencies

```
python >= 3.8
numpy
pandas
pysam
matplotlib
```

## Common Pitfalls

1. **"Batman ears" curve (high at ends, low in middle)**
   → UTR or IVS not excluded. Add `--exclude-region UTR IVS`.

2. **All-zero output**
   → BED column names don't match file header.
   → BAM files not sorted or missing .bai index.

3. **Slow on large BAM files**
   → Increase `-t` threads (one worker per BAM).
   → Ensure BAM files on fast storage (SSD).

4. **Memory errors with many genes**
   → Reduce parallel BAM count.
   → Increase `--min-length` to skip short genes.

5. **Column name mismatch in BED**
   → Check actual column names with `head -1 file.bed`.
   → Update load_bed4() call in main() if non-standard names.

## Verification Checklist

- [ ] BED file has correct column names (chrom, start, end, strand)
- [ ] BAM files are sorted and indexed (.bai exists)
- [ ] UTR and IVS excluded if using gene-level BED with region column
- [ ] Output TSV has non-zero values
- [ ] Plot shows expected coverage shape (flat or slight 3' bias for RNA-seq)
