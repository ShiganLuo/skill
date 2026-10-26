# Pitfall #51: Snakemake declared outputs must ALL exist even when tool skips

When a rule declares multiple outputs but the tool skips processing (e.g., XenofilteR when host==contaminant genome), ALL declared outputs must still be created. Snakemake checks for output file existence and raises `SpawnedJobError` if any are missing.

## Symptom

Tool log says "completed successfully" but Snakemake main log shows `Error in rule <name>` with "check log file(s) for error details". The per-rule log shows no error.

## Fix

In the skip branch of the `run:` block, create all declared outputs:
- Files that would be created by normal processing: `touch` or `ln -s` equivalent
- `.bam.bai` index files: symlink to the input `.bai`

## Example (XenofilteR)

```python
if host == contaminant:
    # must create ALL declared outputs
    shell(f"touch {output.csvIn}")
    shell(f"ln -s {input.host_bam} {output.outBam}")
    shell(f"ln -s {input.host_bam}.bai {output.outBai}")
```

## Why

Snakemake's output checking is independent of the tool's exit code. A clean exit with missing outputs is still a failure.
