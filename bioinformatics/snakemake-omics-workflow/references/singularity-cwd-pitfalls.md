# Singularity runtime cwd pitfalls

## Problem: relative temp file paths break inside containers

When a Python wrapper calls a tool inside a Singularity container via
`subprocess.check_call(cmd)`, the tool may create temp files using **relative
paths** relative to its cwd. Inside the container, the cwd is determined by
`--home`, NOT by the Python process's cwd. This mismatch causes
`FileNotFoundError` when the tool tries to create or clean up temp files.

### Real example: scTE

`scTE_quantify.py` creates a temp directory via `tempfile.TemporaryDirectory()`
(e.g. `/tmp/tmpXXXXXX/`) and passes `-o /tmp/tmpXXXXXX/scTE_out` to scTE.
Inside the Singularity container (`--home /path/to/output`), scTE creates
temp files at relative path `scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp`.
Since container cwd = `--home` (the output dir), not `/tmp/tmpXXXXXX/`, the
relative path resolves to the wrong directory.

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp'
```

### Fix

Pass `cwd=tmpdir` to `subprocess.check_call` so the tool's relative paths
resolve against the temp directory:

```python
def run_scTE(bam, outdir, index, cb_tag, umi_tag, threads, scte_bin, cwd=None):
    cmd = [scte_bin, "-i", bam, "-o", outdir, ...]
    subprocess.check_call(cmd, cwd=cwd)  # cwd propagated

# In main():
with tempfile.TemporaryDirectory() as tmpdir:
    outdir = os.path.join(tmpdir, "scTE_out")
    os.makedirs(outdir)
    run_scTE(..., cwd=tmpdir)  # <-- key fix
```

### General rule

When a Snakemake rule runs a tool inside a Singularity container and the tool
uses relative paths for temp/intermediate files, always set `cwd` in the
subprocess call to the directory where those relative paths should resolve.
The Singularity `--home` flag sets the container's cwd, which may differ from
the Python caller's cwd or the temp directory.
