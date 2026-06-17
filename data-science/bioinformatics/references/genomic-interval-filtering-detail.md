# Genomic Interval Filtering

## When to use

- Filtering depth/coverage/VCF files to keep only exonic (or other) regions
- Excluding intron (IVS) and UTR regions from per-base data using a BED annotation
- Any task that maps positions from one genomic file against interval annotations
- Processing multi-GB genomic files that cannot fit in memory

## Core algorithm

### 1. BED coordinate convention (CRITICAL)

BED uses **0-based half-open** `[start, end)` coordinates.
Depth/VCF `Pos` columns are **1-based inclusive**.

Containment check for 1-based position `pos` in BED interval `[s, e)`:

```
s < pos <= e    (equivalently: pos >= s+1 and pos <= e)
```

When converting to 1-based inclusive intervals for storage:
```
1-based inclusive = [s + 1, e]
```

**PITFALL**: Do NOT store `[s+1, e-1]` — that loses the last base.
A BED interval `[3648119, 3648120)` covers base 3648120 (1-based).
Correct: `[3648120, 3648120]`. Wrong: `[3648120, 3648119]` (empty!).

### 2. Interval containment with sorted arrays (preferred over IntervalTree)

For non-overlapping intervals (typical for gene structure BED files),
use parallel sorted start/end arrays + `bisect_right`:

```python
from bisect import bisect_right

def in_excluded(pos: int, intervals: tuple[list[int], list[int]]) -> bool:
    starts, ends = intervals
    idx = bisect_right(starts, pos) - 1
    return 0 <= idx and pos <= ends[idx]
```

**Why NOT IntervalTree**:
- IntervalTree rejects zero-width intervals (`begin == end`), which arise
  from single-base BED intervals after correct coordinate conversion
- Sorted arrays are contiguous memory → CPU cache-friendly for 100M+ queries
- `bisect_right` is C-implemented, lower constant factor than tree traversal
- No external dependency

### 3. Streaming large files

```python
# Read line-by-line, constant memory regardless of file size
with open(depth_path) as fin, open(output_path, "w") as fout:
    fout.write(fin.readline())  # header
    for line in fin:
        parts = line.split("\t", maxsplit=2)  # only parse needed columns
        chrom = normalize_chrom(parts[0])
        pos = int(parts[1])
        if not in_excluded(pos, intervals_by_chrom.get(chrom, ([], []))):
            fout.write(line)
```

Key: split with `maxsplit=` to avoid parsing all columns for lines with many fields.

### 4. Chromosome name normalization

BED files may use `chr1` while depth files use `1`, or vice versa.
Always normalize: strip `chr` prefix from both sides.

```python
def norm_chrom(chrom: str) -> str:
    return chrom[3:] if chrom.startswith("chr") else chrom
```

## ProcessPoolExecutor pattern for parallel file processing

When filtering 66 files × 5GB each, use multiprocessing. Critical pitfalls:

**PITFALL**: Local functions inside `main()` cannot be pickled.
```python
# WRONG — raises AttributeError: Can't pickle local object
def main():
    def worker(path, out, trees):  # ← local, not picklable
        ...
    pool.submit(worker, ...)  # FAILS
```

**CORRECT**: Module-level worker + initializer pattern:
```python
# Module-level global
TREES: dict | None = None

def _init_worker(trees):
    global TREES
    TREES = trees

def _worker(depth_path: str, output_path: str) -> tuple[str, int, int]:
    assert TREES is not None
    k, e = filter_depth_file(depth_path, output_path, TREES)
    return depth_path, k, e

# In main():
with ProcessPoolExecutor(
    max_workers=args.workers,
    initializer=_init_worker,
    initargs=(trees,),
) as pool:
    pool.submit(_worker, str(df), out_path)
```

The `initializer=` pattern serializes `trees` once per worker process
(on creation), not per task submission. With fork-based workers, the
parent's memory is copied via COW, so even the initializer serialization
is fast.

## Full implementation reference

See `scripts/filter_intron_utr.py` — production script filtering 66 depth
files (5GB each) against an 833K-row BED file. Uses all patterns above.

**User preference**: All functions must have full type annotations (Parameters/Returns in docstring, parameter types in signature). Use `from typing import Optional, Tuple, List, Dict, Set`.

## Assembly Conversion (liftOver)

When annotations are in a different assembly than your data (e.g., hg19 BED
with hg38 BAM), convert coordinates using liftOver. On CentOS 7 systems, the
UCSC liftOver binary fails due to GLIBC version — use `pyliftover` Python
library instead.

**Critical pitfall**: `pyliftover.convert_coordinate()` returns single-point
results `(chrom, pos, strand, score)`, NOT interval results. For BED intervals,
convert start and end positions separately, then check they landed on the same
chromosome. See `references/genomic-coordinate-conversion.md` for full code.

## Extracting Gene BED from GTF + GMT

To generate a BED file for a gene set (e.g., housekeeping genes from MSigDB):
1. Parse GMT file → gene symbol set (fields[2:])
2. Parse GENCODE GTF → gene-level coordinates (only `fields[2] == 'gene'`)
3. Match gene symbols, output BED6

GTF is 1-based; subtract 1 from start for BED 0-based coordinates.
Typical match rate: ~99.8% for curated gene sets against GENCODE.
See `references/gtf-gene-extraction-with-gmt.md` for implementation.

## Pitfalls

1. **BED coordinate formula**: `[s+1, e]` not `[s+1, e-1]`. The latter
   drops the last base and creates zero-width intervals from single-base BED rows.

2. **IntervalTree zero-width**: IntervalTree raises `ValueError: Null Interval`
   when `begin == end`. Use sorted arrays instead, or skip zero-width intervals
   if you must use IntervalTree.

3. **Multiprocessing pickling**: Functions defined inside other functions
   (closures) cannot be pickled. Always define workers at module level.

4. **maxsplit in parsing**: Don't `split("\t")` entire 9+ column lines when
   you only need columns 0 and 1. Use `split("\t", maxsplit=2)`.

5. **Chromosome mismatch**: Always normalize `chr` prefix before lookup.
   A silent miss means positions on that chromosome are ALL kept (wrong).

6. **Reference genome version mismatch (SILENT FAILURE)**: Using annotation
   files (VCF, BED, GTF) from a different reference assembly than the BAM
   causes `Assertion 'aux->itr' failed` in htslib tools (bam-gps, bcftools)
   or silently empty results. Always verify all three (BAM, VCF, BED) use
   the same chromosome naming convention AND the same assembly version.
   Example: `common_all_20180423_hkg.vcf.gz` is GRCh37 but BAM is GRCh38
   → assertion failure. See `references/dbsnp-vcf-and-chromosome-naming.md`.

7. **pyliftover single-point return**: `convert_coordinate()` returns
   `[(chrom, pos, strand, score)]` for a SINGLE POINT, not an interval.
   Calling it with `(chrom, start, end)` gives the start point only.
   For BED intervals, call separately for start and end, then verify
   both landed on the same chromosome.

8. **GTF 1-based vs BED 0-based**: GTF coordinates are 1-based inclusive.
   BED coordinates are 0-based half-open. When extracting from GTF:
   `bed_start = gtf_start - 1`. Forgetting this shifts all intervals by 1.

9. **UCSC liftOver binary GLIBC**: The UCSC liftOver binary requires
   GLIBC 2.29+ (CentOS 7 has 2.17). Error: `version 'GLIBC_2.29' not found`.
   Use pyliftover Python library as alternative.

## References

- `references/dbsnp-vcf-and-chromosome-naming.md` — dbSNP release structure,
  GCF accession mapping, chromosome naming across 3 formats (RefSeq/bare/UCSC),
  region-filtered VCF creation with bcftools, and reference version mismatch
  diagnosis.
- `references/gene-coordinate-sources-and-bed-generation.md` — UCSC refGene
  download URLs and format, housekeeping gene list sources (Eisenberg & Levanon
  2013, HGNC, UniHouse), BED generation workflow from gene lists, and common
  pitfalls (gene aliases, multiple transcripts).
- `references/housekeeping-gene-lists.md` — Curated housekeeping gene lists
  organized by function (ribosomal, translation, proteasome, cytoskeleton,
  metabolism, oxidative phosphorylation). Quick copy-paste lists for RT-qPCR
  panels.
- `references/genomic-coordinate-conversion.md` — liftOver/pyliftover for
  assembly conversion (hg19→hg38). Critical pitfall: pyliftover returns
  single-point results, not intervals. Convert start/end separately.
    Also covers chain file download URLs and GLIBC compatibility.
    Includes `output_chr_style` parameter for chr-style vs numeric chromosomes.
- `references/gtf-gene-extraction-with-gmt.md` — Extract gene BED from
  GENCODE GTF + MSigDB GMT files. Covers GMT parsing, GTF 1-based→0-based
  conversion, regex extraction of gene_name, and typical match rates.

## Scripts

- `scripts/generate_bed_from_gene_list.py` — Generate BED file from gene list
  using UCSC refGene coordinates. Supports command-line gene list or file input.
  Usage: `python generate_bed_from_gene_list.py --genome hg38 --gene-file genes.txt -o output.bed`