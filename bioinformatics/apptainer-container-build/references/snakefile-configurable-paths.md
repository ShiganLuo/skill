# Snakemake Configurable Paths Pattern

## Problem
Shared Snakemake modules (e.g., `featureCounts.smk`) hardcode input file extensions like `{sample_id}.bam`, but upstream rules may produce different suffixes (e.g., `{sample_id}.sorted_markdup.bam` from MarkDuplicates).

## Solution
Add a `bam_substring` config parameter to the module:

```python
# In the module (e.g., featureCounts.smk)
def get_bams_for_featureCounts(wildcards):
    bams = []
    suffix = config.get("bam_substring", "")
    suffix_str = f".{suffix}" if suffix else ""
    for sample_id in samples:
        bams.append(f"{indir}/{sample_id}/{sample_id}{suffix_str}.bam")
    return bams
```

```python
# In the subworkflow (e.g., ncRNAseq.smk)
featureCounts_config = {
    "indir": align_bam_dir,
    "bam_substring": "sorted_markdup",  # produces {sample}.sorted_markdup.bam
    ...
}
```

Default is empty (`{sample_id}.bam`), preserving backward compatibility.

## Snakemake IncompleteFilesException
When a run is interrupted (e.g., STAR killed mid-alignment), Snakemake marks output files as incomplete. Fix:

```bash
# Delete incomplete files and rerun
rm -rf <incomplete_directory>/
# Or mark as complete if files are unnecessary
snakemake --cleanup-metadata <filenames>
```

These are often unmapped reads (`*.Unmapped.out.mate1/mate2`) that aren't needed downstream.