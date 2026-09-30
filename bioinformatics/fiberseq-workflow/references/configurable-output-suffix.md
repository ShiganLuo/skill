# Configurable Output Suffixes in Snakemake Modules

When a module's output filename needs to carry pipeline-stage information
(e.g., `.fiberseq.fire.sorted.bam` instead of `.sorted.bam`), use a
configurable output suffix alongside the input suffix.

## Pattern

```python
# Module .smk
_bam_suffix = config.get("bam_suffix", ".bam")           # input suffix
_out_suffix = config.get("output_bam_suffix", ".sorted")  # output suffix

rule some_aligner:
    input:
        bam = indir + "/{sample_id}/{sample_id}" + _bam_suffix,
    output:
        bam = outdir + "/{sample_id}/{sample_id}" + _out_suffix + ".bam",
        bai = outdir + "/{sample_id}/{sample_id}" + _out_suffix + ".bai",
```

## Subworkflow Usage

```python
pbmm2_config = {
    "indir": prepare_outdir,
    "outdir": aligned_dir,
    "bam_suffix": ".fiberseq.fire.bam",
    "output_bam_suffix": ".fiberseq.fire.sorted",  # no .bam, just the middle part
    ...
}
```

## Why

- BAM filenames become self-documenting (`.fiberseq.fire.sorted.bam` tells
  you exactly what pipeline stage produced it)
- Downstream modules can read the correct file without relying on directory
  paths alone
- Default `.sorted` preserves backward compatibility for existing workflows
  (PacVar, etc.) that don't pass `output_bam_suffix`

## Pitfall

Don't include `.bam` in `output_bam_suffix` — the rule appends `.bam` and
`.bai` separately. The suffix is just the infix between `{sample_id}` and
the extension.