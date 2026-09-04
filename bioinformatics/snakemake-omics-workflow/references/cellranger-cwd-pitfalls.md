# Cell Ranger cwd / output-dir pitfalls

## Problem

Both `cellranger mkref` and `cellranger count` create output in the **current working directory**. They have NO `--output-dir` flag (it is silently ignored if passed).

- `cellranger mkref --genome X` creates `mkref_X/` in cwd
- `cellranger count --id X` creates `X/` in cwd

If the Snakemake rule runs from the default working directory (snakemake's cwd), the output lands in the wrong place.

## Fix: set cwd explicitly

### In Python (subprocess)

```python
subprocess.check_call(cmd, cwd=output_dir)
```

### In shell script generation (smk rule)

```python
with open(command_script, "w") as f:
    f.write("#!/usr/bin/env bash\nset -euo pipefail\n")
    f.write(f"cd {outdir}\n")  # ← must cd BEFORE cellranger
    f.write(" ".join(cmd) + "\n")
```

## Stale pipestance cleanup

Previous failed runs leave `mkref_<genome>/` directories. Re-running with different params triggers:

```
RuntimeError: pipestance 'mkref_X' already exists with different invocation file
```

Auto-clean before running:

```python
mkref_dir = os.path.join(output_dir, f"mkref_{genome_name}")
if os.path.exists(mkref_dir):
    logger.warning(f"Removing stale mkref directory: {mkref_dir}")
    shutil.rmtree(mkref_dir)
```

## Chromosome naming for non-human genomes

Cellranger does NOT require `chr` prefix. For non-human Ensembl genomes, keep original chromosome names (1, 2, ..., X, Y, MT). Adding `chr` prefix to FASTA but not GTF causes mismatch:

```
Invalid contig name encountered on GTF line 6: 1. The FASTA file has contigs: ['chr1', 'chr2', ...]
```

Rule: if FASTA uses Ensembl names, GTF must use the same names. Don't add `chr` unless both files have it.

## cellranger count specific pitfalls

### No --output-dir flag

Same as mkref: `cellranger count` ignores `--output-dir`. It creates `<sample_id>/` in cwd. The smk rule must `cd` to the parent output directory:

```python
# In shell script generation:
f.write(f"cd {outdir}\n")  # outdir = parent of sample dirs
f.write(" ".join(cmd) + "\n")  # cellranger creates {sample_id}/ inside
```

### --transcriptome must point to genome subdirectory

`cellranger mkref --genome Mmul_10` creates `cellranger_ref/Mmul_10/` (with fasta/, genes/, star/, reference.json). The `--transcriptome` for count must point to `cellranger_ref/Mmul_10/`, NOT `cellranger_ref/`:

```
[error] Your reference does not contain the expected files, or they are not readable.
```

Fix: compute `cellranger_transcriptome_dir = cellranger_ref_dir + "/" + genome_name` and use it as the transcriptome input.

### Stale sample directory cleanup

`cellranger count` fails if `<sample_id>/` exists but isn't a valid pipestance:

```
RuntimeError: /path/to/outdir/sample_id is not a pipestance directory
```

Auto-clean before running (in smk run: block):

```python
sample_outdir = os.path.join(outdir, sample_id)
if os.path.exists(sample_outdir):
    import shutil
    rule_logger.warning(f"Removing stale sample directory: {sample_outdir}")
    shutil.rmtree(sample_outdir)
# Don't pre-create — cellranger will create it
```

### Shell script location

Write the command script to `outdir`, NOT `sample_outdir`. If the script is inside `sample_outdir`, cellranger detects the directory exists (with the script file) and tries to re-attach as a pipestance:

```python
command_script = os.path.join(outdir, f"cellranger_count_{sample_id}_{current_time}.sh")
```

## Python stdout buffering in containers

When Python stdout is redirected to a file (`>> log 2>&1`), Python detects non-TTY and uses **block buffering** (4-8KB). Log messages appear in chunks, not line-by-line. This is not container-specific — it happens with any file redirect.

Fix options (pick one):
- `PYTHONUNBUFFERED=1` environment variable
- `python -u script.py` (unbuffered flag)
- `sys.stdout.reconfigure(line_buffering=True)` in script
