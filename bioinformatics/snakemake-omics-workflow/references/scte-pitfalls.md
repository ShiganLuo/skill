# scTE Pitfalls (v1.6.1)

scTE quantifies transposable element expression from single-cell BAM files.

## 1. Relative temp file paths break in Singularity containers

scTE creates temp files using **relative paths** from its cwd (e.g. `scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp`). When running inside Singularity with `--home` set to a non-tmpdir path, the container's cwd differs from the Python `tempfile.TemporaryDirectory()` location.

**Symptom**: `FileNotFoundError: [Errno 2] No such file or directory: 'scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp'`

**Fix**: Pass `cwd=tmpdir` to `subprocess.check_call()` when invoking scTE, so the relative paths resolve against the temp directory:
```python
with tempfile.TemporaryDirectory() as tmpdir:
    outdir = os.path.join(tmpdir, "scTE_out")
    subprocess.check_call(scTE_cmd, cwd=tmpdir)
```

## 2. Output is `.csv.gz`, not `.csv`

scTE v1.6.1 outputs gzipped CSV (`scTE_out.csv.gz`). File discovery must match both:
```python
csv_files = [f for f in os.listdir(outdir) if f.endswith((".csv", ".csv.gz"))]
```
Note: `os.path.splitext("scTE_out.csv.gz")` returns `(".csv", ".gz")` — NOT `("scTE_out", ".csv.gz")`. Avoid `splitext` for constructing output names from `.csv.gz` files.

## 3. HDF5 `/` in keys — index name AND barcode values

scTE CSV has:
- **Index name**: `gene/barcode` (contains `/`)
- **Cell barcodes**: may contain `/` (e.g. `AAAC/GG`)

h5ad uses HDF5, which **rejects `/` in keys**. Both the index name and index values must be sanitized:
```python
data.index = data.index.astype(str).str.replace("/", "_", regex=False)
if data.index.name and "/" in str(data.index.name):
    data.index.name = str(data.index.name).replace("/", "_")
```

**Symptom**: `ValueError: Forward slashes are not allowed in keys in <class 'h5py._hl.group.Group'>`

## 4. Preserve raw scTE matrix

The temp directory is cleaned up after conversion. Save the raw CSV alongside the h5ad:
```python
raw_csv_out = os.path.join(os.path.dirname(args.output), csv_files[0])
shutil.copy2(csv_path, raw_csv_out)
```
Use `csv_files[0]` directly as the filename (preserves `.csv.gz` extension intact).

## 5. Concurrency safety

`tempfile.TemporaryDirectory()` generates unique paths per invocation — multiple samples running in parallel via Snakemake each get their own isolated tmpdir. No conflict risk.

## 6. Transposed matrix in scTE_csv_to_h5ad

scTE CSV output has **genes as rows, cells as columns**:
```
gene/barcode, AAAAAAAAAAAAAAAA, AAAAAAACAAAGCACA, ...  ← cell barcodes (columns)
(GAATG)n,     0, 0, 0, ...                             ← TE/gene (rows)
5S_rRNA,      0, 0, 0, ...
```

The original code treated rows as cells (obs) and columns as genes (var) — reversed.
**Fix**: add `data = data.T` after `pd.read_csv` to transpose to standard AnnData format (obs=cells, var=genes).

**Symptom**: obs_names are gene names like `A1BG`, var_names are 16bp barcodes like `AAAAAAAAAAAAAAAA`.

## 7. MT chromosome conversion bug in scTE base.py (upstream)

**File**: scTE `base.py` → `splitAllChrs()` lines 249-256

```python
chrom = t[0].replace('chr', '')   # BAM chrM → M
if chrom not in chromosome_list:  # chromosome_list has 'MT' from GTF
    if chrom == 'MT':             # ← WRONG: should be 'M' → 'MT'
        chrom = 'M'
    else:
        continue                  # M not in list, all MT reads skipped
```

BAM uses UCSC `chrM` → stripped to `M`. GTF uses Ensembl `MT`. The conversion `MT→M` is backwards; should be `M→MT`. All mitochondrial reads are silently dropped.

**Workaround**: Not fixable without patching scTE source. Use Cell Ranger output for MT-containing analysis.

## 8. MT exon features lack gene_name in Ensembl GTF

Ensembl GTF MT protein-coding genes (ND1, COX1, etc.) have `gene_name` in their `gene` and `exon` features. But Mt_tRNA and Mt_rRNA features only have `gene_id`, not `gene_name`.

scTE `annotation.py` line 52 does `t[8].split('gene_name "')[1]` which crashes on features without `gene_name`. The scTE build will fail or skip all MT tRNA/rRNA genes.

## 9. TE BED chromosome naming mismatch

TE BED files from UCSC RepeatMasker use `chr1`, `chr2`, etc. Ensembl GTF uses `1`, `2`, etc.

**Fix**: Strip `chr` prefix from TE BED before using with scTE:
```bash
python3 workflow/Omics/src/annotation/fix_te_bed_chr.py /path/to/rmsk_TE.bed  # in-place fix
```

## 10. Diagnosis approach when MT% = 0

1. Check if data is transposed (obs_names should be cell barcodes, not gene names)
2. Check if MT genes exist in var_names (grep for ND1, COX1, etc.)
3. If not in var_names, check the scTE annotation file for MT genes
4. If MT genes missing from annotation, check GTF for gene_name attribute on MT exons
5. Check BAM chromosome naming vs GTF chromosome naming
