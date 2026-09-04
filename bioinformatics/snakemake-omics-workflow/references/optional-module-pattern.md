# Optional Modules with Skip Flags

## Pattern

Modules can be conditionally included using `skip_<module>` flags in config.

### In subworkflow .smk

```python
skip_fragment_size = config.get("Params", {}).get("skip_fragment_size", False)
if not skip_fragment_size:
    fragment_size_config = {
        "indir": upstream_config["outdir"],  # chain from upstream module
        "outdir": f"{outdir}/mutation/fragment_size",
        "logdir": logdir,
        "ROOT_DIR": ROOT_DIR,
        "samples": paired_samples + single_samples,
        "Procedure": {
            "samtools": config.get("Procedure", {}).get("samtools")
        }
    }
    module fragment_size:
        snakefile: "../modules/fragment_size/fragment_size.smk"
        config: fragment_size_config
    logger.info(f"fragment_size_config: {fragment_size_config}")
    use rule samtools_stats from fragment_size as Mutation_samtools_stats
    use rule getFragmentSize from fragment_size as Mutation_getFragmentSize
    use rule plotFragmentSize from fragment_size as Mutation_plotFragmentSize
else:
    logger.info("Skipping fragment_size module (skip_fragment_size=True)")
```

### In run.py `run<Workflow>()`

```python
# Only add outfiles for optional modules if not skipped
skip_fragment_size = datajson.get("Params", {}).get("skip_fragment_size", False)
if not skip_fragment_size:
    outfiles.append(f"{outdir}/mutation/fragment_size/fragment/FragmentSize.txt")
    outfiles.append(f"{outdir}/mutation/fragment_size/fragment/FragmentSize.png")
```

### In config JSON

```json
{
    "Params": {
        "skip_fragment_size": false
    }
}
```

## Key points

- `skip_<module>` defaults to `False` (enabled by default)
- Outfiles must be conditionally added in run.py to match
- The skip check must happen BOTH in subworkflow .smk (to skip module import) AND in run.py (to skip outfile generation)
- Use `logger.info()` to log when a module is skipped

## Real example: fragment_size module

The fragment_size module analyzes cfDNA/ctDNA fragment length distribution:

1. `samtools_stats` — per-sample BAM statistics
2. `getFragmentSize` — aggregate all samples into histogram table
3. `plotFragmentSize` — plot distribution with 167bp highlight

Module files:
- `modules/fragment_size/fragment_size.smk`
- `modules/fragment_size/fragment_size.json`
- `modules/fragment_size/fragment_size.yaml`
- `modules/fragment_size/bin/getFragmentSize.py` — parses samtools stats IS lines
- `modules/fragment_size/bin/plotFragmentSize.py` — matplotlib line plot per sample

Usage:
```bash
# Include fragment size analysis (default)
python run.py -m meta -w Mutation -o output

# Skip fragment size analysis
python run.py -m meta -w Mutation -o output --Params.skip_fragment_size true
```
