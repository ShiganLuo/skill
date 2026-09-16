# featureCounts BAM Path Contract

## Problem

`featureCounts.smk` module constructs input BAM paths from `config["indir"]`:

```python
bams.append(f"{indir}/{sample_id}/{sample_id}.bam")
```

But upstream rules (e.g., MarkDuplicates via `gatk_prepare.smk`) output `{sample_id}.sorted_markdup.bam`. This causes `MissingInputException` in Snakemake dry-run.

## Solution: `bam_substring` Parameter

Add a configurable `bam_substring` to `featureCounts.smk`:

```python
def get_bams_for_featureCounts_paired(wildcards):
    bams = []
    suffix = config.get("bam_substring", "")
    suffix_str = f".{suffix}" if suffix else ""
    for sample_id in paired_samples:
        bams.append(f"{indir}/{sample_id}/{sample_id}{suffix_str}.bam")
    return bams
```

In the calling subworkflow, pass the substring:

```python
featureCounts_config = {
    "indir": align_bam_dir,       # e.g., {outdir}/common/4_markdup_bam
    "bam_substring": "sorted_markdup",  # matches MarkDuplicates output
    ...
}
```

## Resulting Path Resolution

| `bam_substring` | Input path |
|:---|:---|
| `""` (default) | `{sample_id}/{sample_id}.bam` |
| `"sorted_markdup"` | `{sample_id}/{sample_id}.sorted_markdup.bam` |

## Key Rules

- Default must be `""` (empty) → `{sample_id}.bam` — backwards compatible
- Subworkflow passes `bam_substring` based on what the upstream rule actually outputs
- This mirrors the `input_bam_substring` pattern already used in `gatk_prepare.smk` for `addReadsGroup`

## General Pattern

Any Snakemake module that reads BAMs from an upstream rule should support a configurable suffix parameter. The calling subworkflow knows the upstream output naming; the module should not hardcode it.