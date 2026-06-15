# Genomic Coordinate Conversion (liftOver)

## Problem

Convert BED/interval coordinates from one genome assembly to another
(e.g., hg19 → hg38, mm9 → mm39).

## Tools

### 1. pyliftover (Python, preferred on CentOS 7)

UCSC liftOver binary requires GLIBC 2.29+ (not available on CentOS 7).
Use `pyliftover` Python library instead.

**Install**: `pip install pyliftover` (or install to custom path and set PYTHONPATH)

**Chain file download**:
```
http://hgdownload.soe.ucsc.edu/goldenPath/{fromAssembly}/liftOver/{fromAssembly}To{toAssemblyCap}.over.chain.gz
```
Examples:
- hg19→hg38: `hg19ToHg38.over.chain.gz`
- mm10→mm39: `mm10ToMm39.over.chain.gz`

**PITFALL: pyliftover returns SINGLE-POINT results, NOT intervals.**

```python
from pyliftover import LiftOver
lo = LiftOver("hg19ToHg38.over.chain.gz")

# Returns: [('chr1', 69069, '-', 20851231461)]
#          (chrom, pos, strand, score)
# This is a SINGLE POINT, not an interval!
result = lo.convert_coordinate('chr1', 69069)
```

For BED interval conversion, convert start and end SEPARATELY.
Add `output_chr_style` parameter to control chromosome naming.

**User preference**: All functions must have full type annotations (Parameters/Returns in docstring).

```python
from typing import Optional, Tuple, List
from pyliftover import LiftOver


def convert_interval(
    lo: LiftOver,
    chrom: str,
    start: int,
    end: int,
    output_chr_style: bool = False,
) -> Optional[Tuple[str, int, int]]:
    """
    Convert a BED interval from one assembly to another.

    Parameters
    ----------
    lo : LiftOver
        LiftOver object with loaded chain file
    chrom : str
        Chromosome (supports '1' or 'chr1' input)
    start : int
        Start position (0-based BED)
    end : int
        End position
    output_chr_style : bool, optional
        If True, output 'chr1' style. If False (default), output '1' style.

    Returns
    -------
    Optional[Tuple[str, int, int]]
        (new_chrom, new_start, new_end) or None if conversion failed
    """
    if not chrom.startswith('chr'):
        chrom_lift = 'chr' + chrom
    else:
        chrom_lift = chrom

    start_result: List[Tuple[str, int, str, int]] = lo.convert_coordinate(chrom_lift, start)
    if not start_result or len(start_result) == 0:
        return None

    end_result: List[Tuple[str, int, str, int]] = lo.convert_coordinate(chrom_lift, end)
    if not end_result or len(end_result) == 0:
        return None

    new_chrom_s: str = start_result[0][0]
    new_start: int = start_result[0][1]
    new_chrom_e: str = end_result[0][0]
    new_end: int = end_result[0][1]

    if new_chrom_s != new_chrom_e:
        return None

    new_chrom: str = new_chrom_s
    if output_chr_style:
        if not new_chrom.startswith('chr'):
            new_chrom = 'chr' + new_chrom
    else:
        new_chrom = new_chrom[3:]

    new_start = int(new_start)
    new_end = int(new_end)
    if new_start > new_end:
        new_start, new_end = new_end, new_start

    return (new_chrom, new_start, new_end)
```

### CLI wrapper with argparse

```python
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="liftOver BED: hg19→hg38")
    parser.add_argument(
        "--chr", action="store_true", default=False,
        help="Output chr-style chromosomes (chr1, chrX) instead of numeric (1, X)"
    )
    return parser.parse_args()
```

### pyliftover installation on shared servers

On servers where `pip install` goes to a custom target directory:

```bash
# Install to user packages
pip install pyliftover --target=/path/to/pip/packages

# Set PYTHONPATH before running
export PYTHONPATH=/path/to/pip/packages:$PYTHONPATH
python3 lift_hg19_to_hg38.py
```

### 2. UCSC liftOver binary (requires GLIBC 2.29+)

```bash
# Download
wget http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/liftOver
chmod +x liftOver

# Run
liftOver input.bed hg19ToHg38.over.chain.gz output.bed unmapped.bed -minMatch=0.95
```

**PITFALL**: On CentOS 7 (GLIBC 2.17), the binary fails with:
`version 'GLIBC_2.29' not found`. Use pyliftover instead.

### 3. CrossMap (Python, alternative)

```bash
pip install CrossMap
CrossMap.py bed hg19ToHg38.over.chain.gz input.bed output.bed
```

## Chain File Size Reference

Chain files are typically 100-500MB compressed. If download is <1MB,
it's likely an error page. Verify with `file` and `zcat | head`.

## Typical Conversion Rates

- hg19→hg38: ~99.9% success rate for well-annotated regions
- Unmapped regions are typically in repetitive/complex regions or
  regions that changed assembly structure

## Integration with Gene Extraction

When extracting genes from GTF, the GTF already specifies the assembly.
If you need genes in a different assembly:
1. Extract BED from GTF (in GTF's native assembly)
2. Use liftOver/pyliftover to convert to target assembly
3. Verify conversion rate (>99% expected for gene coordinates)
