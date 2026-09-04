# Cellranger, STAR, and Non-human Genome Pitfalls

## 68. Cellranger mkref/count have NO --output flag — must set cwd

Both `cellranger mkref` and `cellranger count` create output in the **current working directory**. They do NOT accept `--output` or `--output-dir` flags. Passing these flags silently ignores them, and cellranger creates output in the snakemake working directory instead.

**Symptom:** `RuntimeError: pipestance 'mkref_X' already exists` or `is not a pipestance directory`

**Fix for mkref (in bin/cellranger_ref.py):**
```python
subprocess.check_call(cmd, cwd=args.output)  # ← set cwd to output dir
```

**Fix for count (in cellranger.smk):**
```python
with open(command_script, "w") as f:
    f.write("#!/usr/bin/env bash\nset -euo pipefail\n")
    f.write(f"cd {outdir}\n")  # ← MUST cd first
    f.write(" ".join(cmd) + "\n")
```

**Stale directory cleanup:** cellranger fails if target dir exists but isn't a valid pipestance. Always clean up:
```python
mkref_dir = os.path.join(args.output, f"mkref_{args.genome}")
if os.path.exists(mkref_dir):
    import shutil
    shutil.rmtree(mkref_dir)
```

For the full cellranger module pattern, see `cellranger-module-pattern.md`.

## 69. STARsolo read order: --readFilesIn R2(cDNA) R1(barcode)

For 10x Chromium scRNA-seq with STARsolo, the `--readFilesIn` order matters:
- **First file:** cDNA read (R2, 90-150bp) — this is what STAR aligns
- **Second file:** Barcode+UMI read (R1, 28bp) — used for cell/UMI identification

**Wrong order symptom:** `Average input read length | 28` in Log.final.out, ~19% uniquely mapped, ~65% unmapped: too short.

**Verification:** Check `Log.final.out` for `Average input read length`. If it shows 28 (barcode length) instead of ~150 (cDNA length), the reads are reversed.

**Fix in star.smk:**
```python
# For 10x: R2 is cDNA (align), R1 is barcode (UMI)
cmd = [
    params.STAR, "--runThreadN", str(threads),
    "--readFilesIn", r2_fastq, r1_fastq,  # ← cDNA first, barcode second
    ...
]
```

Note: Some claim STARsolo auto-detects barcode read via `--soloBarcodeReadLength 0`, but empirical evidence shows it uses the FIRST read for alignment regardless. Always put cDNA first.

## 70. Non-human genome: do NOT add chr prefix to FASTA/GTF

For non-human genomes (macaque, mouse, etc.), keep original Ensembl chromosome names (1, 2, ..., X, Y, MT). Do NOT add chr prefix.

**Why:** Cellranger only requires FASTA and GTF chromosome names to MATCH. Adding chr prefix to FASTA but not GTF (or vice versa) causes `Invalid contig name` errors.

**Wrong approach:** Modify FASTA headers to add chr, then try to modify GTF to match → error-prone, double-prefixing bugs.

**Right approach:** Skip FASTA header modification entirely. Use original Ensembl files as-is (after ID version stripping if needed).

```python
# For non-human: just strip ID versions, don't modify chromosomes
modify_gtf_ids(gtf_src, gtf_id_modified)
filter_gtf_by_biotype(gtf_id_modified, gtf_filtered, BIOTYPE_PATTERN)
# NO modify_fasta_headers call
```

## 71. Stale pipestance/sample directory cleanup before cellranger

Cellranger fails if the target output directory exists but isn't a valid pipestance:
- `RuntimeError: pipestance 'X' already exists with different invocation file`
- `RuntimeError: X is not a pipestance directory`

**Always clean up before running:**
```python
# In mkref
mkref_dir = os.path.join(args.output, f"mkref_{args.genome}")
if os.path.exists(mkref_dir):
    import shutil
    shutil.rmtree(mkref_dir)

# In count
sample_outdir = os.path.join(outdir, sample_id)
if os.path.exists(sample_outdir):
    import shutil
    shutil.rmtree(sample_outdir)
# Don't pre-create — let cellranger create it
```

Also clean up `.mri.tgz` files from failed runs:
```bash
rm -f <outdir>/*.mri.tgz
```
