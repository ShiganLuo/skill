# scTE Mitochondrial Chromosome Naming Bug (M<->MT)

## Problem

scTE's `split_all_chrs()` in `base.py` strips the `chr` prefix from both the
chromosome_list (derived from TE annotation) and the input BED file, then
matches BED lines to chromosomes. However, mitochondrial naming varies:

| Source         | Typical naming |
|----------------|---------------|
| GTF (Ensembl)  | MT            |
| GTF (UCSC/NCBI)| chrM → M after strip |
| rmsk BED       | chrM → M after strip |
| rmsk BED (alt) | chrMT → MT after strip |

When annotation uses "MT" but BED uses "M" (or vice versa), the line gets
dropped silently — no error, just missing mitochondrial TE counts.

## Container Status (as of 2026-08-27)

`/home/luosg/Database/env/scTE/scTE.sif` has an **incomplete fix** (line ~772):

```python
if chrom not in chromosome_list:
    # Force chrMT -> chrM
    if chrom == 'MT':
        chrom = 'M'
    else:
        continue
```

This only handles MT→M. The reverse (M→MT when annotation has MT) is missing.

## Complete Bidirectional Fix

```python
if chrom not in chromosome_list:
    if chrom == 'MT':
        chrom = 'M'
    elif chrom == 'M':
        chrom = 'MT'
    else:
        continue

    # Re-check after mapping — if still not in list, skip
    if chrom not in chromosome_list:
        continue
```

## How to Verify

```bash
# Check current code inside container
apptainer exec /home/luosg/Database/env/scTE/scTE.sif \
    sed -n '770,780p' /opt/conda/envs/scTE/lib/python3.14/site-packages/scTE/base.py

# Check what chromosome names your TE annotation uses
apptainer exec /home/luosg/Database/env/scTE/scTE.sif \
    python3 -c "from scTE.miniglbase import glload; g = glload('path/to/TE.genelist'); print(set(r['chr'] for r in g))"
```

## Context

- Function: `split_all_chrs()` in `/opt/conda/envs/scTE/lib/python3.14/site-packages/scTE/base.py`
- The chromosome_list is built from TE annotation (GTF/genelist), strips 'chr' at line 755
- BED input also strips 'chr' at line 769
- The mismatch check happens at line 772
- Container Python version: 3.14 (scTE env)
