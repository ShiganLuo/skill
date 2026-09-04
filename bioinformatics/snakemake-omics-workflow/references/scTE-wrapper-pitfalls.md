# scTE wrapper pitfalls (Singularity + Snakemake)

## 1. Relative temp file paths — set `cwd` for subprocess

scTE creates intermediate temp files using **relative paths** (e.g. `scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp`) relative to the process cwd, NOT the `-o` output path.

When running inside Singularity with `--home <output_dir>`, the container's cwd defaults to the home dir, not the tmpdir. If you use `tempfile.TemporaryDirectory()` for the output, the relative path resolves to the wrong location.

**Fix**: pass `cwd=tmpdir` to `subprocess.check_call()`:

```python
with tempfile.TemporaryDirectory() as tmpdir:
    outdir = os.path.join(tmpdir, "scTE_out")
    os.makedirs(outdir)
    subprocess.check_call(scTE_cmd, cwd=tmpdir)
```

## 2. Output format: `.csv.gz` not `.csv`

scTE v1.6.1 outputs `scTE_out.csv.gz` (gzip-compressed), not `scTE_out.csv`. Code that searches for `*.csv` will miss it.

**Fix**: match both extensions:

```python
csv_files = [f for f in os.listdir(outdir) if f.endswith((".csv", ".csv.gz"))]
```

`pd.read_csv()` handles `.csv.gz` natively (auto-detects compression).

## 3. HDF5 `/` in cell barcodes

scTE cell barcodes may contain `/` (e.g. `gene/barcode`). HDF5 keys cannot contain forward slashes — `adata.write_h5ad()` raises:

```
ValueError: Forward slashes are not allowed in keys
```

**Fix**: replace `/` with `_` in the index before writing:

```python
data.index = data.index.astype(str).str.replace("/", "_", regex=False)
```

## 4. `os.path.splitext` on compound extensions

`os.path.splitext("scTE_out.csv.gz")` returns `("scTE_out.csv", ".gz")`, not `("scTE_out", ".csv.gz")`. Don't use it to build output filenames from `.csv.gz` inputs.

**Fix**: use the original basename directly:

```python
raw_csv_out = os.path.join(output_dir, csv_basename)  # preserves .csv.gz
```

## 5. Save raw matrix before conversion

scTE runs in a `tempfile.TemporaryDirectory` that is deleted after the `with` block. The raw CSV is lost unless explicitly copied out. Always copy the raw scTE matrix to a persistent location before converting to h5ad.

## 6. Singularity `/tmp` bind

The Snakemake Singularity args must include `/tmp` in the bind mounts. The `tempfile.TemporaryDirectory()` creates dirs under `/tmp/` which must be accessible inside the container.
