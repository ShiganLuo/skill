# Snakemake Debugging Patterns

## MissingInputException — Systematic Diagnosis

When Snakemake reports `MissingInputException`, follow this sequence:

### Step 1: Identify the missing files
From the error message, extract:
- The rule name (e.g., `PacVar_hiphase_snp`)
- The affected files (e.g., `DMSO_P20.filtered.vcf.gz`)
- The expected paths

### Step 2: Check if files exist on disk
```bash
find <outdir> -type f -name "*.bam" -o -name "*.vcf*" -o -name "*.bai" -o -name "*.csi" | sort
```
Compare against what the rules expect. Common mismatches:
- File exists but wrong name (`.bai` vs `.bam.bai`)
- File exists in different directory (old vs new directory structure)
- File was `temp()` and cleaned up by upstream rule

### Step 3: Check declared outputs vs actual files
For each rule in the chain, compare `output:` declarations against files on disk.
One missing output cascades to ALL downstream rules.

### Step 4: Check `.snakemake/metadata/`
```bash
ls .snakemake/metadata/ | wc -l
```
If empty: no hash baseline exists. `--rerun-triggers input` will re-run everything.

### Step 5: Check timestamps
```bash
stat -c '%y %n' <output_file>   # when was output created?
stat -c '%y %n' <smk_file>      # when was rule file modified?
```
If `.smk` is newer than output → rule code changed → may trigger re-run.

## Full Cascade Re-run Diagnosis

When ALL rules show in dry-run (not just the broken ones):

1. **Missing upstream output**: One rule's declared output doesn't exist → that rule re-runs → all downstream get "input files updated by another job"
2. **Empty metadata + `--rerun-triggers input`**: No hash baseline → re-run everything
3. **`.smk` files modified**: Code trigger detects changes → re-run affected rules

The #1 cause is usually a missing index file (`.bai`, `.tbi`, `.csi`) that a rule declared as output but never created.

## Index File Naming Conventions

| Tool | Command | Output Name |
|------|---------|-------------|
| GATK | `--CREATE_INDEX true` | `{name}.bai` |
| samtools | `samtools index file.bam` | `{name}.bam.bai` |
| samtools | `samtools index file.bam -o out.bai` | `out.bai` |
| bcftools | `bcftools index file.vcf.gz` | `{name}.vcf.gz.csi` |
| tabix | `tabix -p vcf file.vcf.gz` | `{name}.vcf.gz.tbi` |

When writing input functions, always check which convention the upstream rule uses.

## `--rerun-triggers` Behavior

| Flag | Checks | Needs Metadata? |
|------|--------|-----------------|
| `mtime` (default part) | input mtime vs output mtime | No |
| `input` | input file content hash | YES |
| `code` | rule code (.smk) hash | YES |
| `params` | rule params hash | YES |
| `software-env` | conda env hash | YES |

Snakemake 8.x default: `mtime` only (when `--rerun-triggers` is NOT passed).

When `--rerun-triggers` IS passed, you choose which triggers to enable.
With empty metadata: `input`/`code`/`params`/`software-env` all fail to compare → re-run.
`mtime` still works without metadata (timestamp comparison).

Note: this project's `run.py` defaults to `--rerun-triggers input`.
Do NOT modify this parameter without user direction.

## Touch as Temporary Fix

```bash
find <outdir> -type f \( -name "*.bam" -o -name "*.bai" -o -name "*.vcf*" \) -exec touch {} +
```

This updates timestamps so `mtime`-based checks pass. But:
- Does NOT create missing files (touch can't create files that don't exist)
- Does NOT update `.snakemake/metadata/` hashes
- `--rerun-triggers input` still re-runs (no hash baseline)

Only useful as a temporary workaround when switching to `--rerun-triggers mtime`.

## Touch Without Metadata Causes Cascade

When `.snakemake/metadata/` is empty, `touch` on output files makes Snakemake treat them as "updated" (new timestamp, no hash baseline to verify). This triggers "Updated input files" for all downstream rules — the opposite of the intended effect.

**Session example**: Touching `sorted_markdup.bam` caused `pbsv_discover` → `pbsv_call` → `hiphase_sv` cascade (6 extra jobs). The touch was meant to SKIP those rules but instead forced them to re-run.

**Lesson**: With empty metadata, touch is counterproductive. Let the full run complete first to generate metadata.

## BAM Header Quick Check

```bash
samtools view -H file.bam | head -5     # header + SQ lines
samtools quickcheck file.bam             # exit 0 = valid, non-zero = issues
```

`quickcheck` catches: missing EOF marker, truncated files, missing @SQ lines.
For PacBio uBAM: expect `SO:coordinate` in @HD but NO @SQ lines (unaligned). `quickcheck` reports "had no targets in header" — this is normal for uBAM.

## Empty Log File + Subprocess Exit Status 1

When Snakemake reports `SpawnedJobError` / `CalledProcessError` with exit status 1,
and the rule's log file is **empty** (0 bytes), the actual error is hidden in the
subprocess's stderr — which Snakemake's `--quiet progress rules host` flag suppresses.

**Debugging path**:

1. Check if the generated `.sh` script exists in the output directory
2. Check the rule's log file — if empty, the `run:` block or the tool itself failed
3. **Re-run the subprocess command manually WITHOUT `--quiet`** to see the actual error.
   Extract the command from the Snakemake log (it's the `Command '...'` string in the
   `CalledProcessError` traceback), remove `--quiet progress rules host`, and run it:

```bash
# From the Snakemake log, the failing command looks like:
# Command 'cd <outdir> && python -m snakemake --snakefile ... --quiet progress rules host ...'
# Remove --quiet progress rules host, reduce --cores to 1, and re-run:
cd <outdir> && python -m snakemake --snakefile <smk> \
  --target-jobs '<rule:wildcard>' --allowed-rules <rule> \
  --cores 1 --force --rerun-triggers mtime \
  --deployment-method conda --conda-prefix <prefix> \
  --configfiles <config.json> 2>&1 | tail -50
```

This reveals the actual tool error (e.g., RepeatMasker species not found, missing
search engine, malformed input, etc.) that the `--quiet` flag was hiding.

**Session example**: RepeatMasker `-species "mouse"` failed with exit 255. The main
Snakemake log showed only `SpawnedJobError` — no tool output. The repeatmasker.log
was empty because Snakemake's `shell()` wrapped the command with `set -e` and
`source activate`, and the RepeatMasker stderr went to the tool's log (which was
created but empty since RepeatMasker wrote its error to the redirected log path
but the exit code 255 caused the shell to abort before writing completed).

**Key insight**: In subprocess mode, Snakemake spawns a child process with
`--quiet progress rules host`. Errors from the child's rule execution are captured
in the `CalledProcessError` but the actual tool output is suppressed. Manual
reproduction without `--quiet` is the only reliable way to see the root cause.

**Session example 2**: Snakemake v9 `log` object TypeError. The main log showed
`SpawnedJobError` for `PacVar_HaplotypeCaller` and `PacVar_repeatmasker_run`.
Rule logs were empty. Manual reproduction revealed:

```
TypeError in file "gatk_germline.smk", line 55:
expected str, bytes or os.PathLike object, not Log
```

Root cause: `open(log, "w").close()` — in Snakemake v9, `log` in `run:` blocks
is a `Log` object, not a string. Fix: `open(str(log), "w").close()`. The error
happens at Python level before any shell command executes, which is why the rule
log stays empty (the `open()` call that would create/initialize it is the very
thing that fails).

## Bare `python` in generated .sh scripts — ImportError for conda packages

When a `run:` block generates a `.sh` script and uses bare `"python"` as the
interpreter, it resolves to `/usr/bin/python` (system Python), not the conda
environment's Python. This causes `ModuleNotFoundError` for conda-installed
packages (pysam, pandas, numpy, etc.).

**Symptoms**:
- `ModuleNotFoundError: No module named 'pysam'` in rule log
- `samtools: command not found` in rule log
- Snakemake reports `CalledProcessError` exit status 1
- Script appears to run but produces empty/incomplete output

**Root cause**: In `run:` blocks, `shell("bash script.sh")` inherits the
Snakemake process's PATH, which does NOT include the conda env's bin directory.
The `conda:` directive only activates for `shell:` blocks, not `run:` blocks.

**Fix**: Use full conda python path in cmd list AND add `export PATH` to
generated script. See `references/generate-shell-scripts-from-run-blocks.md`.
