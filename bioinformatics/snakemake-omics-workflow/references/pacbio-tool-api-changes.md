# Tool API Changes — PacBio Assembly Tools

## hifiasm 0.25.0

**Removed flags**: `--hifi` (use positional args)

**Input format**: Expects FASTQ, NOT BAM. Passing BAM produces `counted 0 distinct minimizer k-mers` then crash.

**Correct usage**:
```bash
hifiasm -o prefix -t 48 input.fq.gz
```

**Conversion step** (BAM → FASTQ):
```bash
samtools fastq -@ 8 input.bam | gzip -c > input.fq.gz
hifiasm -o prefix -t 48 input.fq.gz
rm -f input.fq.gz
```

## hiphase 1.7.0

**Changed flags** (from older versions):
- `--num-threads` → `--threads` (or `-t`)
- `--input-bam` → `--bam` (or `-b`)
- `--input-vcf` → `--vcf` (or `-c`)

**Correct usage**:
```bash
hiphase --threads 8 \
        --reference ref.fa \
        --bam input.bam \
        --output-bam output.phased.bam \
        --vcf input.vcf.gz \
        --output-vcf output.phased.vcf
```

**Error symptom**: `error: Found argument '--num-threads' which wasn't expected, or isn't valid in this context`

**Affected files**: `workflow/Omics/modules/hiphase/hiphase.smk` (cmd1 construction)

**Multi-command script pitfall**: When hiphase fails due to wrong parameters, the
subsequent `bgzip` command still runs on the non-existent `.vcf` file, producing a
corrupted `.vcf.gz` with negative block length. Fix: delete corrupted `.gz` + `.csi`
files before re-running. See pitfall #45 in SKILL.md.

**Multi-environment PATH issue**: hiphase and bgzip (htslib) may be in different conda
environments. The script needs BOTH in PATH:

```bash
# Find environments
find /path/to/envs -name "hiphase" -type f 2>/dev/null
find /path/to/miniforge3 -name "bgzip" -type f 2>/dev/null

# Run with combined PATH
export PATH="/path/to/hiphase/env/bin:/path/to/htslib/bin:$PATH"
bash output/.../hiphase_*.sh
```

**Root cause**: Snakemake's `conda:` directive only activates for `shell:` commands,
not for scripts executed via `shell("bash script.sh")` from `run:` blocks. The script
inherits the main Snakemake process environment.

**Fix options** (see pitfall #47 in SKILL.md for full details):
1. Add htslib to hiphase.yaml dependencies (preferred, permanent fix)
2. Use `shell("which bgzip", read=True)` in run block to find bgzip in conda env
3. Use full paths in the generated script

**Workflow fix**:
```bash
# Find the generated script
ls -lt output/<workflow>/variation/germline_snv_indel/<sample>/hiphase_*.sh | head -1

# Edit: replace --num-threads with --threads, --input-bam with --bam, --input-vcf with --vcf

# Also fix the .smk source to prevent future occurrences
```

## telogator2

**Flags** (short only):
- `-i` — input reads (fa/fa.gz/fq/fq.gz/bam)
- `-o` — output directory
- `-r hifi` — read type (hifi/ont)
- `-c` — threads

**Dependencies**: minimap2 must be in PATH

**Correct usage**:
```bash
telogator2 -i input.bam -o output/ -r hifi -c 16
```

## RepeatMasker 4.1.0

**Configuration**: `DEFAULT_SEARCH_ENGINE` must be set in `RepeatMaskerConfig.pm`

**Available engines**: rmblast, nhmmer, crossmatch, abblast

**Fix**:
```bash
find /path/to/env -name "RepeatMaskerConfig.pm" -path "*/share/*"
sed -i "s/'value' => ''/'value' => 'rmblast'/"/path/to/RepeatMaskerConfig.pm
```
