# Bioinformatics Coverage Analysis

## Core Algorithm

### 1. BED Loading

BED/TSV files with configurable column names. Group intervals by transcript ID,
filter by region type (e.g., exclude UTR, IVS).

```python
def load_bed4(path, col_chrom="chrom", col_start="start", col_end="end",
              col_strand="strand", transcript_id_col=None,
              region_id_col=None, exclude_region=None):
    # Read BED, filter excluded regions, group by transcript
    # Returns: List[Tuple[str, str, List[Tuple[int, int]]]]
    #   = (chrom, strand, [(start, end), ...]) per transcript
```

Key: `exclude_region` uses exact string matching via `isin()`. Values must
match exactly (e.g., "UTR" not "5UTR").

### 2. Gene Model Construction

For each transcript:
1. Sort exons by genomic coordinate
2. Compute total length = sum(end - start)
3. Build exon map: (exon_start, exon_end, transcript_offset)
4. Pre-compute bin edges: `np.linspace(0, length, bins+1)`
5. Pre-compute bin widths: `np.diff(edges)`, clamp to >= 1

### 3. Coverage Extraction (FAST method)

**Use `bam.fetch()` + `read.get_blocks()` — NOT `pysam.pileup()`**

`pileup()` builds PileupColumn objects per position (10-50x slower).
`fetch()` + `get_blocks()` iterates aligned blocks directly:

```python
for read in bam.fetch(chrom, start, end):
    if read.is_unmapped or read.is_duplicate or read.is_qcfail:
        continue
    if read.is_secondary or read.is_supplementary:
        continue
    for block_start, block_end in read.get_blocks():
        s = max(block_start, region_start) - region_start
        e = min(block_end, region_end) - region_start
        if e > s:
            cov[s:e] += 1
```

### 4. Vectorized Binning

```python
binned = np.add.reduceat(gene_vec, bin_edges[:-1])
bin_means = binned / bin_widths
```

For negative-strand genes: `bin_means = bin_means[::-1]` to get 5'→3' direction.

### 5. Normalization (Option A: per-gene max)

```python
max_val = bin_means.max()
if max_val > 0:
    bin_normalized = bin_means / max_val  # range [0, 1]
```

Eliminates expression-level differences, preserves coverage distribution shape.

### 6. Aggregation

- Per BAM: accumulate across genes, divide by gene count
- Across BAMs: average per-BAM curves
- Output both raw (mean_coverage) and normalized (0-1) curves

## CLI Interface

```bash
python geneBody_coverage.py \
    -i <BAM_INPUT> \       # single, comma-sep, dir, or list file
    -b <BED_FILE> \        # BED/TSV with header
    -o <OUTPUT_PREFIX> \
    -t 4 \                 # threads (one per BAM)
    --bins 100 \           # percentiles across gene body
    --min-length 100 \     # skip short genes
    --exclude-region UTR IVS \  # regions to filter
    --plot-format png
```

## Output

TSV: `bin  mean_coverage  normalized_coverage`
Plot: line chart, X=percentile (5'→3'), Y=normalized coverage (0-1)

## Pitfalls

### P1: "Batman ears" curve (high at ends, low in middle)

**Cause**: UTR or IVS (introns) not excluded from gene body.

Gene structure: `[exon][intron][exon][intron]...[exon]`

First and last positions always land on exons (high coverage), but middle
positions often fall in introns (near-zero coverage).

**Fix**: `--exclude-region UTR IVS`

### P2: Wrong region column values

`exclude_region` uses `isin()` (exact match). If BED has "5UTR"/"3UTR"
but you exclude "UTR", nothing gets filtered. Check actual values:
```bash
cut -f<N> file.bed | sort | uniq -c
```

### P3: pileup() is the bottleneck

For 1000 genes × 10KB average, pileup takes hours. fetch+blocks takes minutes.

### P4: Missing supplementary filter

Always filter `is_supplementary` alongside `is_secondary` for coverage counting.

### P5: Coverage not normalized

Raw coverage curves are dominated by high-expression genes. Normalize per-gene
by max to compare distribution shapes across samples.

## Performance

| Approach | Speed | Notes |
|----------|-------|-------|
| pysam.pileup() | 1x | Baseline, very slow |
| fetch + get_blocks | 10-50x | Recommended |
| samtools depth (C) | 50-100x | External subprocess |
| numpy reduceat binning | O(L) vectorized | vs O(bins×L) Python loop |

Multiprocessing: one worker per BAM (not per gene). Genes are pickled to workers.
