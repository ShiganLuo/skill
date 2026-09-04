# scTE Patch Patterns — Exact Text for Container Patches

These are the exact strings found in the INSTALLED scTE package inside the container.
Source repo may differ. Always verify with `apptainer exec <sif> grep -n ...` first.

## 1. base.py splitAllChrs — BAM processing

**Old (original)**:
```python
            # Force chrMT -> chrM
            if chrom == 'MT':
                chrom = 'M'
            else:
                continue
```

**New (bidirectional)**:
```python
            # Handle M<->MT mitochondrial naming mismatch (UCSC chrM vs Ensembl MT)
            if chrom == 'M' and 'MT' in chromosome_list:
                chrom = 'MT'
            elif chrom == 'MT' and 'M' in chromosome_list:
                chrom = 'M'
            else:
                continue
```

**Scope**: Only affects `splitAllChrs()` — the SINGLE-THREAD path. Multi-thread path uses `split_chr()` which doesn't have M/MT logic. This patch has NO effect on cell count when running with `-p > 1`.

## 2. scTE_build chr_list — Index building

**Old**:
```python
chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M']
```

**New**:
```python
chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M', 'MT']
```

## 3. scTE_build readGtf — Gene chromosome check

**Old**:
```python
            if chrom.replace('chr','') not in chr_list:
                continue
```

**New**:
```python
            _chr = chrom.replace('chr','')
            if _chr not in chr_list:
                if _chr == 'M' and 'MT' in chr_list:
                    pass
                elif _chr == 'MT' and 'M' in chr_list:
                    pass
                else:
                    continue
```

## 4. scTE_build TE processing — TE chromosome check (NO-OP in 1.6.1)

**Old pattern looked for by post.sh**:
```python
            if chr not in chr_list:
                continue
```

**Reality in scte-quant 1.6.1**: The TE processing uses `active_chr_set` (not `chr_list`), and the code structure is different. This patch pattern does NOT match — it's a silent no-op.

## Verification Commands

```bash
# Check base.py patch
apptainer exec <sif> grep -c "Handle M<->MT" /opt/conda/envs/scTE/lib/python3.14/site-packages/scTE/base.py

# Check scTE_build chr_list
apptainer exec <sif> grep "chr_list.*=.*range" /opt/conda/envs/scTE/bin/scTE_build

# Check readGtf fix
apptainer exec <sif> grep -c "_chr.*not in chr_list" /opt/conda/envs/scTE/bin/scTE_build

# Full diff: PyPI original vs container installed
pip download scte-quant==1.6.1 --no-deps -d /tmp/scte_fresh
unzip /tmp/scte_fresh/*.whl -d /tmp/scte_fresh_pkg
diff /tmp/scte_fresh_pkg/scTE/base.py /tmp/container_base.py
```

## Key Findings (2026-08-27)

- All M/MT patches are about mitochondrial naming only — they don't change quantification logic
- Patch #4 is a no-op in scte-quant 1.6.1 (code uses `active_chr_set`, not `chr_list`)
- The M/MT patches don't affect cell count: they only matter when BAM has `chrM` but index has `MT` (or vice versa)
- When debugging cell count differences, the cause is NEVER the M/MT patches — look at Bam2bed, filter_crs, or count_expression instead

## samtools vs pysam Bam2bed Path (CRITICAL)

scte-quant 1.6.1 has two Bam2bed implementations in `base.py`:

**`_bam2bed_cmd`** (samtools path, line ~660):
```bash
samtools view -@ N input.bam | awk '{... extract CR/UR ...}' | sed 's/CR:Z://g' | sed 's/UR:Z://g' | sed 's/^chr//g' | awk '!x[$4$5]++' | zstd > output.bed.zst
```
The `awk '!x[$4$5]++'` deduplicates by barcode ($4) + UMI ($5). This reduces ~120M reads to ~29M unique barcode+UMI pairs.

**`_bam2bed_pysam`** (pysam fallback, line ~257):
```python
for read in bam:
    line = f"{chr_name}\t{pos}\t{pos+100}\t{bc}\t{umi}\n"
    oh.write(line)
```
Writes EVERY read to BED — NO dedup at all. All 120M reads go into the BED file.

**Impact on cell count**:
- Samtools path: ~29M BED lines, ~1.13 reads per barcode → 111 barcodes pass ≥400 filter
- Pysam path: ~120M BED lines, ~4.7 reads per barcode → many more barcodes pass ≥400 filter

**How to check which path was used**:
```bash
grep "samtools" <log_file>
# "samtools found — using samtools for BAM processing" → _bam2bed_cmd
# "samtools not found — falling back to pysam" → _bam2bed_pysam
```

**Root cause**: The pysam fallback was added for environments without samtools. It replicates the awk field extraction but forgot the dedup step. This is a bug in scte-quant 1.6.1 — the pysam path should include dedup logic.

**Reproduction pitfall**: When testing scTE outside the container (e.g., in a pip venv), if samtools is not installed, the pysam fallback is used silently. This produces completely different results from the container (which has samtools). Always install samtools when reproducing container results:
```bash
conda install -y samtools  # or apt install samtools
```
