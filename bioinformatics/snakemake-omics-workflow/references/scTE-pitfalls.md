# scTE pitfalls (scRNAseq TE quantification)

scTE (v1.6.1) quantifies transposable element expression from single-cell BAM files.
Used in the scRNAseq pipeline under `modules/scTE/`.

## 1. Singularity cwd mismatch — relative temp file paths

**Symptom:** `FileNotFoundError: [Errno 2] No such file or directory: 'scTE_out_scTEtmp/o1/scTE_out.bed.zst.tmp'`

**Root cause:** scTE creates intermediate temp files using **relative paths** (e.g. `scTE_out_scTEtmp/o1/...`) relative to the process cwd. When running inside a Singularity container with `--home <output_dir>`, the container's cwd is the home dir, NOT the tmpdir where `-o` points. The relative path resolves to the wrong location.

**Fix:** Pass `cwd=tmpdir` to `subprocess.check_call()` in `scTE_quantify.py`:
```python
def run_scTE(bam, outdir, index, cb_tag, umi_tag, threads, scte_bin, cwd=None):
    cmd = [scte_bin, "-i", bam, "-o", outdir, "-x", index,
           "-p", str(threads), "-CB", cb_tag, "-UMI", umi_tag]
    subprocess.check_call(cmd, cwd=cwd)

# In main():
with tempfile.TemporaryDirectory() as tmpdir:
    outdir = os.path.join(tmpdir, "scTE_out")
    os.makedirs(outdir)
    run_scTE(..., cwd=tmpdir)
```

**Why this works:** `tempfile.TemporaryDirectory()` creates dirs in `/tmp/`, which is bind-mounted into the Singularity container. Setting `cwd=tmpdir` makes scTE's relative temp file paths resolve correctly inside the container.

**Concurrency safe:** Each `tempfile.TemporaryDirectory()` call generates a unique random path, so multiple samples running in parallel get isolated tmpdirs.

## 2. Output is `.csv.gz`, not `.csv`

**Symptom:** `FileNotFoundError: No CSV output found in /tmp/.../scTE_out or /tmp/...`

**Root cause:** scTE v1.6.1 outputs gzipped CSV (`scTE_out.csv.gz`), but the file detection code only matched `.csv`.

**Fix:** Match both extensions:
```python
csv_files = [f for f in os.listdir(outdir) if f.endswith((".csv", ".csv.gz"))]
```

`pd.read_csv()` handles `.csv.gz` natively (auto-detects compression from extension), so no change needed in the reader.

## 3. CSV must be transposed — rows=genes, cols=cells

**Symptom:** `var_names` are 16bp cell barcodes, `obs_names` are gene names. MT% is always 0 because `MT-` prefix matching runs against barcodes, not gene names.

**Root cause:** scTE CSV format: first column header is `gene/barcode`, first column values are gene/TE names, remaining columns are cell barcodes. So **rows = genes, columns = cells**. AnnData standard is obs=cells, var=genes. Without transpose, the matrix is inverted.

**Fix:** Transpose after reading:
```python
data = pd.read_csv(csv_path, index_col=0, header=0)
data.index = data.index.astype(str).str.replace("/", "_", regex=False)
if data.index.name and "/" in str(data.index.name):
    data.index.name = str(data.index.name).replace("/", "_")
data = data.T  # rows=genes,cols=cells → rows=cells,cols=genes
```

**Also fix the HDF5 `/` key issue** — `gene/barcode` becomes `data.index.name` before transpose. After transpose it's `data.columns.name` and won't be written to `/obs`, but replace `/` in index values for safety.

## 3b. Chromosome naming mismatch: GTF vs rmsk BED

**Symptom:** After rebuilding scTE index, mitochondrial genes (ND1, COX1, etc.) are missing from the output. `pct_counts_mt` is always 0 even after fixing the transpose.

**Root cause:** Ensembl GTF uses bare chromosome names (`1`, `2`, ..., `MT`), while UCSC-format rmsk BED uses `chr` prefix (`chr1`, `chr2`, ...). scTE_build can't match genes to TEs across mismatched chromosome names. MT chromosome has no TE entries in the BED file, so MT genes get excluded from the "exclusive" index.

**Fix:** Strip `chr` prefix from BED before scTE_build. Use `src/annotation/fix_te_bed_chr.py` (in-place fix):
```bash
python src/annotation/fix_te_bed_chr.py /path/to/rmsk_TE.bed
```

This fixes all three genomes in `config/scRNAseq.json`: GRCm39, GRCh38, Mmul_10.

**After fixing:** Rebuild index with `snakemake -R scTE_build_index`, then re-run `scTE_quantify`.

## 4. Preserve raw scTE matrix alongside h5ad

scTE runs in a `tempfile.TemporaryDirectory()` which is cleaned up after conversion. The raw CSV should be saved before cleanup:

```python
import shutil

csv_base = csv_files[0]  # e.g. "scTE_out.csv.gz"
raw_csv_out = os.path.join(os.path.dirname(args.output), csv_base)
shutil.copy2(csv_path, raw_csv_out)
```

**Pitfall:** Do NOT use `os.path.splitext()` to construct the output name for `.csv.gz` — it returns `.gz` not `.csv.gz`. Use the original filename directly.

## Snakemake rule pattern for scTE

The `scTE_quantify` rule in `scTE.smk` follows the standard Omics pattern:
- Rule validates inputs + assembles command + calls shell
- ALL logic lives in `bin/scTE_quantify.py` (argparse CLI)
- Uses `tempfile.TemporaryDirectory()` for scTE intermediate files
- Converts scTE CSV output to h5ad for Scanpy downstream
- Runs inside Singularity container (`scTE.sif`) with `--bind /tmp`
