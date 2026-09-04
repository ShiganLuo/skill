# PacVar (PacBio Variant Calling) Debugging Guide

Common errors, fixes, and run commands for the PacVar workflow.

## How to run

```bash
# Activate the snakemake environment first
conda activate smk

# Run from the project root
cd /data/pub/zhousha/20260207_Exome
bash workflow/Omics/run.sh
```

The `run.sh` invokes `run.py` with:
```bash
python run.py \
    -m data/PacBio/samplesheet.csv \
    -w PacVar \
    -o output \
    -t 48 \
    --log log/PacVar.log \
    --conda-prefix /data/pub/zhousha/env/mutation_0.1 \
    --genome.fasta /path/to/genome.fa \
    --rerun-triggers mtime
```

## Log files to check

1. **Main log**: `log/PacVar.log` — run.py + snakemake output
2. **Per-sample logs**: `output/PacVar/log/{sample_id}/{rule}.log` — individual rule outputs
3. **Snakemake log**: `output/PacVar/.snakemake/log/*.snakemake.log` — snakemake execution details

## Common errors and fixes

### 1. MissingInputException: `.sorted.bai` missing

**Symptom**: All 28 jobs re-run despite most outputs existing.

**Root cause**: `pbmm2_align` declares `.sorted.bam` + `.sorted.bai` as outputs. If `.bai` is missing, pbmm2_align must re-run → cascades to ALL downstream rules.

**Fix**:
```bash
SAMTOOLS=/data/pub/zhousha/env/mutation_0.1/66824805e456bbd570af6201a9405108_/bin/samtools
$SAMTOOLS index -@ 4 input.bam output.bai
```

**Verify**: `find output/PacVar -name "*.bai" | wc -l` — compare against expected count.

### 2. All rules re-run with `--rerun-triggers input`

**Symptom**: Every rule shows "Missing output files" or "Updated input files" despite outputs existing.

**Root cause**: `.snakemake/metadata/` is empty (no previous successful run). `--rerun-triggers input` needs metadata for hash comparison. Without it, all rules re-run.

**Fix**: Use `--rerun-triggers mtime` instead (timestamp-based, works without metadata).

### 3. hifiasm: `counted 0 distinct minimizer k-mers` then crash

**Symptom**: hifiasm produces 0 k-mers, then segfaults or "Illegal instruction".

**Root cause**: hifiasm 0.25.0 expects FASTQ input, not BAM. Passing aligned BAM produces 0 reads.

**Fix**: Add `samtools fastq` conversion step before hifiasm:
```python
cmd0 = ["samtools", "fastq", "-@", str(threads), input.bam, "|", "gzip", "-c", ">", fq_gz]
cmd1 = ["hifiasm", "-o", prefix, "-t", str(threads), fq_gz]
cmd_cleanup = ["rm", "-f", fq_gz]
```

Also: hifiasm 0.25.0 removed `--hifi` flag — use positional args only.

### 4. hifiasm: `samtools: command not found`

**Symptom**: `samtools fastq` fails because samtools is not in the conda environment.

**Fix**: Add `samtools>=1.20` to `centromere.yaml` dependencies.

### 5. telogator2: `the following arguments are required: -i, -o`

**Symptom**: telogator2 doesn't recognize `--reads`/`--output` flags.

**Root cause**: telogator2 uses `-i`/`-o`/`-r hifi` flags, not `--reads`/`--output`/`--threads`.

**Fix**:
```python
cmd = ["telogator2", "-i", input.bam, "-o", output.dir, "-r", "hifi", "-c", str(threads)]
```

### 6. RepeatMasker: `Search engine ( ) is unknown`

**Symptom**: RepeatMasker fails with "Search engine unknown".

**Root cause**: `DEFAULT_SEARCH_ENGINE` is empty in `RepeatMaskerConfig.pm`.

**Fix**:
```bash
# Find the config file
find /data/pub/zhousha/env -name "RepeatMaskerConfig.pm" -path "*/share/*"

# Set search engine to rmblast
sed -i "s/'value' => ''/'value' => 'rmblast'/" /path/to/RepeatMaskerConfig.pm
```

### 7. RepeatMasker: input file appears empty

**Symptom**: "File appears to be empty" in repeatmasker.log.

**Root cause**: hifiasm failed to produce assembly output (see #3 above). The `.fa` file is 0 bytes.

**Fix**: Fix hifiasm first (see #3), then re-run.

### 8. `current_time` format causes shell path truncation

**Symptom**: `bash: .../tool_2026-06-14: No such file or directory`

**Root cause**: `time.strftime("%Y-%m-%d %H:%M:%S")` contains a space, breaking `shell(f"bash {script} ...")`.

**Fix**: Use `time.strftime("%Y%m%d_%H%M%S")` — no spaces or colons.

### 9. BAI naming mismatch: GATK vs samtools

**Symptom**: MissingInputException for `.bai` file.

**Root cause**: GATK `--CREATE_INDEX true` creates `{name}.bai`, `samtools index` creates `{name}.bam.bai`.

**Fix**: Match the input function's BAI path to the upstream rule's convention:
```python
# GATK convention:
in_dict["bai"] = f"{dir}/{sid}.{substring}.bai"
# samtools convention:
in_dict["bai"] = f"{dir}/{sid}.{substring}.bam.bai"
```

### 10. Missing `use rule` for intermediate rules

**Symptom**: MissingInputException — Snakemake can't find a rule to produce an expected file.

**Root cause**: Module has multiple rules (A → B → C) but only A was imported via `use rule`. B's output is needed by another module.

**Fix**: Import ALL rules in the dependency chain:
```python
use rule HaplotypeCaller from gatk_germline as PacVar_HaplotypeCaller
use rule filterHaplotypeCallerVcf from gatk_germline as PacVar_filterHaplotypeCallerVcf
```

### 11. GATK HaplotypeCaller: exit code 245, no error in log

**Symptom**: HaplotypeCaller log ends abruptly mid-progress with no GATK error message, no Java stack trace, no "Shutting down engine". Only the wrapper reports `exit status 245`.

**Root cause**: GATK's Python launcher uses `check_call()`. When the Java process dies from a signal, `CalledProcessError.returncode` is the negative signal number. `sys.exit(-N)` gets truncated to 8-bit: `exit code = 0xFF & -N`.

| Exit code | Negative value | Signal | Meaning |
|-----------|---------------|--------|---------|
| 245 | -11 | SIGSEGV | Segmentation fault (native crash) |
| 247 | -9 | SIGKILL | OOM killer or external kill |
| 246 | -10 | SIGBUS | Bus error |

**Fix**:
```bash
# Disable native PairHMM, use Java fallback
gatk --java-options "-Xms20g -Xmx80g" HaplotypeCaller \
  -R ref.fa -I input.bam -O output.vcf.gz \
  --pair-hmm-implementation VECTOR_LOGLESS_CACHING

# Or reduce native threads
gatk ... --native-pair-hmm-threads 4
```

### 12. DeepVariant: `run_deepvariant: command not found`

**Symptom**: DeepVariant log shows `run_deepvariant: command not found` despite `conda list` showing `deepvariant 1.10.0` installed.

**Root cause**: The bioconda `deepvariant` package is a **stub/wrapper** — it registers in conda but does NOT contain the actual `run_deepvariant` binary or Python module. DeepVariant requires a complex TensorFlow runtime and is officially distributed only via Docker/Singularity containers.

**Fix options**:
1. **Use Singularity container** — modify the rule to run via `singularity exec`
2. **Switch to Clair3** — conda-installable, designed for PacBio HiFi, comparable accuracy

### 13. GATK `-XX:GCTimeLimit=50` not a valid command

**Symptom**: `'-XX:GCTimeLimit=50' is not a valid command` (shell error).

**Root cause**: Java JVM options containing spaces are not quoted in the generated `.sh` script.

**Fix**: Wrap `javaOptions` in quotes when building the cmd list:
```python
cmd = [params.gatk, "--java-options", f'"{params.javaOptions}"', "HaplotypeCaller", ...]
```

## Debugging workflow

### Principle: unit-test first, don't re-run the whole DAG

Each `run:` block rule generates a `.sh` script in the output directory. Test it directly:

```bash
# Find the latest script
ls -lt output/PacVar/repeat/centromere/hifiasm_*.sh | head -1

# Run it directly (unit test)
bash output/PacVar/repeat/centromere/hifiasm_20260614_191519.sh

# Check the log
cat output/PacVar/log/DMSO_P20/hifiasm.log
```

### Step-by-step debugging

1. Check `log/PacVar.log` for the error message
2. Identify the failing rule and sample from the error
3. Read the per-sample log: `output/PacVar/log/{sample_id}/{rule}.log`
4. Find the generated script: `ls -lt output/PacVar/**/tool_*.sh`
5. Run the script directly to reproduce the error
6. Check if input files exist: `ls -la` the input paths from the error
7. Check if output files exist and are non-empty
8. If cascade re-run, find the ROOT CAUSE (first rule in the chain that fails)
9. Fix the root cause, not the symptoms
