# bedtools coverage Pitfalls

## -F flag is a FRACTION, not a samtools-style flag

`bedtools coverage -F` expects a float in (0.0, 1.0] — minimum overlap as a fraction of B.
It is NOT the samtools-style integer flag (e.g., 1024 for duplicates).

```
# WRONG — "F must be in the range (0.0, 1.0]"
bedtools coverage -a regions.bed -b sample.bam -counts -F 1024

# CORRECT — filter duplicates with samtools first, then pipe
samtools view -b -F 1024 -o filtered.bam sample.bam
bedtools coverage -a regions.bed -b filtered.bam -counts
```

## Pipeline pattern for counting reads excluding duplicates

```python
import subprocess, tempfile, os

def run_bedtools_coverage(bed_file, bam_file, bedtools="bedtools"):
    """Count reads in BED regions, excluding PCR duplicates (flag 0x400)."""
    tmp_bam = tempfile.mktemp(suffix=".bam")
    try:
        subprocess.run(["samtools", "view", "-b", "-F", "1024", "-o", tmp_bam, bam_file], check=True)
        result = subprocess.run(
            [bedtools, "coverage", "-a", bed_file, "-b", tmp_bam, "-counts"],
            capture_output=True, text=True, check=True
        )
        counts = {}
        for line in result.stdout.strip().split("\n"):
            if not line: continue
            fields = line.split("\t")
            if len(fields) >= 4:
                counts[(fields[0], int(fields[1]), int(fields[2]))] = int(fields[3])
        return counts
    finally:
        if os.path.exists(tmp_bam):
            os.unlink(tmp_bam)
```

## stdin piping doesn't work for BAM format

`bedtools coverage -b stdin` doesn't reliably detect BAM format. Use a temp file instead of piping.
