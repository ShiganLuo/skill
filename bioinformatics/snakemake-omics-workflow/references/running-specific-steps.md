# Running Specific Steps in Snakemake

When debugging or re-running parts of a workflow, Snakemake provides several
mechanisms to target specific rules, samples, or job subsets.

## Quick Reference

| Goal | Command |
|------|---------|
| Run until rule X | `--until X` |
| Run specific job | `--target-jobs 'rule:X:wildcards.sample=S1'` |
| Force re-run rule X | `--forcerun X` |
| Skip rule X and downstream | `--omit-from X` |
| Run only rule X (no downstream) | `--target-jobs ... --no-infer-dependencies` |
| Dry-run with reasons | `--dry-run --reason` |
| Show shell commands | `--dry-run --printshellcmds` |

## 1. --until: Run until a specific rule

Runs the workflow up to and including the specified rule, then stops.

```bash
snakemake --snakefile workflow.smk --configfile raw.json \
  --until align --cores 8
```

Use case: Debug early pipeline steps without running the full workflow.

## 2. --target-jobs: Run specific jobs (most precise)

Targets exact rule + wildcard combinations. This is the most precise way
to run individual jobs.

```bash
# Single job
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' --cores 8

# Multiple jobs
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' 'rule:align:wildcards.sample=S2' \
  --cores 8

# Multiple wildcards
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:call:wildcards.sample=S1:wildcards.chr=chr1' --cores 8
```

Wildcard format: `rule:<name>:wildcards.<key>=<value>:wildcards.<key2>=<value2>`

**Note**: `--target-jobs` is marked "Internal use only" in `--help` because it's
primarily for Snakemake's internal use (HPC job submission spawns child processes
with `--target-jobs`). However, it's fully functional for advanced users who want
to run specific jobs directly.

Use case: Re-run a specific sample's alignment without touching other samples.

## 3. --forcerun: Force re-run specific rules

Re-runs the specified rules even if outputs exist and are up-to-date.

```bash
snakemake --snakefile workflow.smk --configfile raw.json \
  --forcerun align --cores 8
```

Use case: Re-run after changing tool parameters without modifying input files.

## 4. --omit-from: Skip rules and downstream

Skips the specified rule and all rules that depend on its output.

```bash
snakemake --snakefile workflow.smk --configfile raw.json \
  --omit-from qc --cores 8
```

Use case: Skip QC steps during development/testing.

## 5. --no-infer-dependencies: Run only targeted rules

When combined with `--target-jobs`, only runs the targeted rules without
inferring or running downstream dependencies.

```bash
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --no-infer-dependencies --cores 8
```

Use case: Run alignment only, don't run variant calling that depends on it.

## 6. --batch: Run a subset of jobs

Batches jobs of a specific rule by index. Useful for distributing work
across multiple machines.

```bash
# Run batch 1 of 4 for the align rule
snakemake --snakefile workflow.smk --configfile raw.json \
  --batch align=1/4 --cores 8

# Run batch 2 of 4
snakemake --snakefile workflow.smk --configfile raw.json \
  --batch align=2/4 --cores 8
```

Use case: Split a large cohort across multiple cluster jobs.

## 7. --dry-run: Preview without execution

Always combine with other flags to preview what would run:

```bash
# Preview with execution reasons
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --dry-run --reason

# Show shell commands that would execute
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --dry-run --printshellcmds
```

## 8. DAG and Rule Graph Visualization

```bash
# DAG (file-level dependencies)
snakemake --snakefile workflow.smk --configfile raw.json \
  --dag | dot -Tpng > dag.png

# Rule graph (rule-level dependencies)
snakemake --snakefile workflow.smk --configfile raw.json \
  --rulegraph | dot -Tpng > rulegraph.png

# File graph
snakemake --snakefile workflow.smk --configfile raw.json \
  --filegraph | dot -Tpng > filegraph.png
```

Filter to specific targets:
```bash
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --dag | dot -Tpng > dag_subset.png
```

## 9. HPC Job Submission

### How Snakemake handles HPC

For remote executors (SLURM, PBS, etc.), Snakemake generates a jobscript
that calls `python -m snakemake --target-jobs ...` on the compute node.
This is a two-layer architecture:

```
Local Snakemake (scheduler)
  └─ Generates jobscript.sh
       └─ Submits to SLURM/PBS (sbatch/qsub)
            └─ Compute node runs: python -m snakemake --target-jobs ...
                 └─ run_wrapper → actual execution
```

### Running a single job on HPC

```bash
# Generate the jobscript content (dry-run + printshellcmds)
snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --dry-run --printshellcmds

# Submit directly via sbatch
sbatch --wrap="snakemake --snakefile workflow.smk --configfile raw.json \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --cores 8 --use-conda"
```

### Understanding jobscript generation

The jobscript is generated in `remote.py:232-254`:

```python
def write_jobscript(self, job, jobscript):
    exec_job = self.format_job_exec(job)  # generates: python -m snakemake ...
    content = self.jobscript.format(
        properties=job.properties(),
        exec_job=exec_job,
    )
    with open(jobscript, "w") as f:
        print(content, file=f)
```

The default jobscript template is minimal:
```bash
#!/bin/sh
# properties = {properties}
{exec_job}
```

Where `{exec_job}` expands to something like:
```bash
cd /workdir && python -m snakemake --snakefile Snakefile \
  --target-jobs 'rule:align:wildcards.sample=S1' \
  --local-groupid default \
  --mode subprocess \
  --quiet all
```

## 10. Integration with run.py

For the Omics project, pass snakemake args via `--snakemake-args`:

```bash
# Run until specific rule
python workflow/Omics/run.py \
  -m data/meta/fastq -w CLIP -o output \
  --snakemake-args --until align

# Force re-run specific rule
python workflow/Omics/run.py \
  -m data/meta/fastq -w CLIP -o output \
  --snakemake-args --forcerun align

# Skip rules
python workflow/Omics/run.py \
  -m data/meta/fastq -w CLIP -o output \
  --snakemake-args --omit-from qc
```

Note: `--target-jobs` requires calling snakemake directly (not via run.py)
because run.py constructs its own target list from samples.

## 11. Debugging Workflow

When a rule fails, the most efficient debugging workflow is:

1. **Identify the failing job** from Snakemake's error output
2. **Find the generated script** (if using auto-script modification):
   ```bash
   ls -lt output/<workflow>/<module>/ | head -5
   ```
3. **Test the script directly**:
   ```bash
   bash output/<workflow>/<module>/tool_20260620_170000.sh
   ```
4. **Fix the issue** in the .smk file
5. **Re-run just that job**:
   ```bash
   snakemake --snakefile workflow.smk --configfile raw.json \
     --target-jobs 'rule:tool:wildcards.sample=S1' \
     --forcerun tool --cores 8
   ```

This avoids re-running the entire DAG for a single rule fix.

## 12. Audit logging for reproducibility

With the audit logging modification (see `references/snakemake-audit-logging.md`),
each output directory contains `.audit.sh` with the actual executed commands.
This is useful for:

- **Auditing**: Verify what commands actually ran
- **Reproducibility**: Re-run commands outside Snakemake
- **Debugging**: See the exact wrapped command (with conda/singularity)

```bash
# View audit log for a specific output directory
cat output/<workflow>/<module>/.audit.sh

# Re-run a specific command from the audit log
bash output/<workflow>/<module>/.audit.sh
```
