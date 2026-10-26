# Snakemake Module Path Contract Pitfalls

General patterns when wiring Snakemake modules via `use rule ... from <module>` with config dicts.

## The Suffix Mismatch Problem

**Symptom**: `MissingInputException` in a downstream rule. The file "should exist" but the name is slightly off.

**Root cause**: Producer and consumer modules use different filename suffixes for the same logical file.

### Example: featureCounts ↔ MarkDuplicates

MarkDuplicates (`gatk_prepare.smk`) outputs:
```
{outdir}/{sample_id}/{sample_id}.sorted_markdup.bam
```

featureCounts (`featureCounts.smk`) expected:
```
{indir}/{sample_id}/{sample_id}.bam
```

Even though `indir == outdir` (both point to `4_markdup_bam`), the suffix mismatch causes `MissingInputException`.

**Fix**: Update the downstream consumer's input function to match the producer's exact output suffix:
```python
# Before (wrong):
bams.append(f"{indir}/{sample_id}/{sample_id}.bam")
# After (correct):
bams.append(f"{indir}/{sample_id}/{sample_id}.sorted_markdup.bam")
```

### Debugging Steps

1. Read the producer rule's `output:` block — note the exact filename pattern
2. Read the consumer's input function — note what filename it constructs
3. Compare character by character — suffixes like `.bam` vs `.sorted_markdup.bam` are easy to miss
4. If `indir` is wired to the producer's `outdir`, the filename patterns MUST match exactly

## The `input_bam_substring` Pattern

Some modules (gatk_prepare) accept `input_bam_substring` to handle varying upstream output names:
```python
if input_bam_substring != "":
    in_dict["bam"] = os.path.join(indir, f"{wildcards.sample_id}/{wildcards.sample_id}." + input_bam_substring + ".bam")
else:
    in_dict["bam"] = os.path.join(indir, f"{wildcards.sample_id}/{wildcards.sample_id}.bam")
```

When using this pattern, ensure the downstream module's hardcoded path matches what the upstream actually produces. If the upstream changes its naming convention, ALL downstream consumers must be updated.

## General Rule

In the Omics framework, each module's `indir` is wired to the previous module's `outdir` in the subworkflow. The **filename contract** between modules is implicit — there's no central schema. When a `MissingInputException` appears:
1. Check the subworkflow wiring (does `indir` point to the right `outdir`?)
2. Check the filename pattern (does the consumer construct the same path the producer emits?)