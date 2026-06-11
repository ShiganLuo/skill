# Coverage Analysis — Full Implementation Detail

## BED Loading

BED/TSV files with configurable column names. Group intervals by transcript ID, filter by region type.

```python
def load_bed4(path, col_chrom="chrom", col_start="start", col_end="end",
              col_strand="strand", transcript_id_col=None,
              region_id_col=None, exclude_region=None):
    # Read BED, filter excluded regions, group by transcript
    # Returns: List[Tuple[str, str, List[Tuple[int, int]]]]
    #   = (chrom, strand, [(start, end), ...]) per transcript
```

Key: `exclude_region` uses exact string matching via `isin()`. Values must match exactly (e.g., "UTR" not "5UTR").

## Gene Model Construction

For each transcript:
1. Sort exons by genomic coordinate
2. Compute total length = sum(end - start)
3. Build exon map: (exon_start, exon_end, transcript_offset)
4. Pre-compute bin edges: `np.linspace(0, length, bins+1)`
5. Pre-compute bin widths: `np.diff(edges)`, clamp to >= 1

## Coverage Extraction (FAST method)

**Use `bam.fetch()` + `read.get_blocks()` — NOT `pysam.pileup()`**

`pileup()` builds PileupColumn objects per position (10-50x slower). `fetch()` + `get_blocks()` iterates aligned blocks directly:

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

## Vectorized Binning

```python
binned = np.add.reduceat(gene_vec, bin_edges[:-1])
bin_means = binned / bin_widths
```

For negative-strand genes: `bin_means = bin_means[::-1]` to get 5'→3' direction.

## Normalization (Option A: per-gene max)

```python
max_val = bin_means.max()
if max_val > 0:
    bin_normalized = bin_means / max_val  # range [0, 1]
```

Eliminates expression-level differences, preserves coverage distribution shape.

## Aggregation

- Per BAM: accumulate across genes, divide by gene count
- Across BAMs: average per-BAM curves
- Output both raw (mean_coverage) and normalized (0-1) curves

## Performance

| Approach | Speed | Notes |
|----------|-------|-------|
| pysam.pileup() | 1x | Baseline, very slow |
| fetch + get_blocks | 10-50x | Recommended |
| samtools depth (C) | 50-100x | External subprocess |
| numpy reduceat binning | O(L) vectorized | vs O(bins×L) Python loop |

Multiprocessing: one worker per BAM (not per gene). Genes are pickled to workers.
