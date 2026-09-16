# Concurrent Script File Collision in Shared Directories

## The Bug

When multiple wildcard combinations share the same `sample_outdir`, concurrent Snakemake jobs overwrite each other's scripts if timestamps match.

## Real Case: star_index

`star_index` rule uses `os.path.dirname(output.index_file)` where output is `directory(outdir + "/index/{genome}")`:

```python
sample_outdir = os.path.dirname(str(output.index_file))
# GRCm39: dirname(".../index/GRCm39") = ".../index/"
# GRCh38: dirname(".../index/GRCh38") = ".../index/"
# SAME directory!

script = os.path.join(sample_outdir, f"star_index_{current_time}.sh")
# Both write to .../index/star_index_20260911_171441.sh
```

GRCm39 writes first, GRCh38 overwrites it. GRCh38 then runs the GRCm39 script (wrong genome), fails with confusing STAR errors about tmp directories.

**Symptom**: `could not make temporary directory: .../tmp_star_GRCm39/` when building GRCh38 index. The log shows GRCh38 input/output paths but the script contains GRCm39 commands.

## Fix

Include wildcard values in the script filename:

```python
# WRONG
script = os.path.join(sample_outdir, f"star_index_{current_time}.sh")

# RIGHT
script = os.path.join(sample_outdir, f"star_index_{wildcards.genome}_{current_time}.sh")
```

## Rule

If `sample_outdir` is derived from `os.path.dirname(output)` on a `directory()` output, it may be a shared parent directory. Always include relevant wildcards in the script filename to prevent collisions.

Safe: `sample_outdir = str(output.some_dir)` — per-wildcard output directory.
Dangerous: `sample_outdir = os.path.dirname(str(output.some_dir))` — shared parent.

## Verification

```bash
grep -rn 'f".*_{current_time}\.sh"' modules/
```

Check each hit: is `sample_outdir` truly per-instance, or a shared parent?
