---
name: genomic-interval-filtering
description: >
  Filter large genomic data files (depth, coverage, VCF) by BED annotation
  intervals — exclude/include regions based on gene structure (exons, introns,
  UTR). Covers BED coordinate conventions, efficient interval containment
  queries, and streaming multi-GB files with constant memory.
tags:
  - bioinformatics
  - bed-annotation
  - genomic-interval
  - depth-filtering
  - large-file-processing
triggers:
  - filter depth by BED
  - exclude intron UTR
  - BED annotation filtering
  - genomic interval containment
  - filter depth file regions
  - remove intronic positions
  - exon-only depth
---

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
