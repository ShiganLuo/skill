# Snakemake shell.py audit logging modification

## Problem

Need to capture the ACTUAL executed commands (with conda/singularity/envmodules
wrapping) for auditing and reproducibility. Manual script generation in every
`run:` block is boilerplate-heavy and only saves the raw command, not the wrapped
version.

## Solution: two-layer audit logging

### Layer 1: shell.__new__ (shell.py) — captures shell: commands

File: `workflow/snakemake/src/snakemake/shell.py`

Insert after `cmd = '"{}" {} {}'.format(...)` (before `proc = sp.Popen`):

```python
# ===== Audit: write executed command to .audit.sh =====
output = context.get("output", None)
if output:
    output_dir = None
    try:
        first_output = next(iter(output))
        output_dir = os.path.dirname(str(first_output))
    except (StopIteration, TypeError):
        pass

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        audit_file = os.path.join(output_dir, ".audit.sh")
        rule_name = context.get("rule", "unknown")
        wildcards = context.get("wildcards", {})
        jobid = context.get("jobid", "unknown")

        with open(audit_file, "a") as f:
            f.write(f"\n# ===== Rule: {rule_name} | JobID: {jobid} =====\n")
            f.write(f"# Wildcards: {wildcards}\n")
            f.write(f"# Timestamp: $(date '+%Y-%m-%d %H:%M:%S')\n")
            if conda_env:
                f.write(f"# Conda: {conda_env}\n")
            if container_img:
                f.write(f"# Singularity: {container_img}\n")
            if env_modules:
                f.write(f"# EnvModules: {env_modules}\n")
            f.write(f"set -euo pipefail\n")
            f.write(cmd + "\n")
# ===== Audit end =====
```

Key: `cmd` at this point includes conda/singularity/envmodules wrapping —
this is the ACTUAL command that gets executed.

### Layer 2: run_wrapper (local.py) — captures run: commands

File: `workflow/snakemake/src/snakemake/executors/local.py`

In `run_wrapper()`, after `is_shell = job_rule.shellcmd is not None`:

```python
# ===== Audit: write run: rule metadata to .audit.sh =====
if not is_shell and output:
    output_dir = None
    try:
        first_output = next(iter(output))
        output_dir = os.path.dirname(str(first_output))
    except (StopIteration, TypeError):
        pass

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        audit_file = os.path.join(output_dir, ".audit.sh")

        import json
        with open(audit_file, "a") as f:
            f.write(f"\n# ===== Rule: {rule} | JobID: {jobid} =====\n")
            f.write(f"# Type: run (Python)\n")
            f.write(f"# Wildcards: {json.dumps(dict(wildcards) if wildcards else {})}\n")
            f.write(f"# Input: {json.dumps([str(i) for i in input])}\n")
            f.write(f"# Output: {json.dumps([str(o) for o in output])}\n")
            f.write(f"# Params: {json.dumps(dict(params) if params else {})}\n")
            f.write(f"# Threads: {threads}\n")
            if conda_env:
                f.write(f"# Conda: {conda_env}\n")
            if container_img:
                f.write(f"# Singularity: {container_img}\n")
            if env_modules:
                f.write(f"# EnvModules: {env_modules}\n")

            # Save Python source
            if job_rule.run_func_src:
                py_file = os.path.join(output_dir, f".audit_{rule}.py")
                with open(py_file, "w") as pf:
                    pf.write(job_rule.run_func_src)
                f.write(f"# Python source: {py_file}\n")
# ===== Audit end =====
```

## Output structure

```
output/<workflow>/<module>/
├── .audit.sh              # All commands for this directory
├── .audit_process.py      # Python source for run: rules
└── actual_output.bam
```

## .audit.sh example

```bash
# ===== Rule: align | JobID: 12345 =====
# Wildcards: {'sample': 'S1'}
# Timestamp: $(date '+%Y-%m-%d %H:%M:%S')
# Conda: /path/to/conda/envs/align
set -euo pipefail
bwa mem -t 8 ref.fa S1_R1.fq S1_R2.fq | samtools sort -o S1.bam

# ===== Rule: process | JobID: 12346 =====
# Type: run (Python)
# Wildcards: {"sample": "S1"}
# Input: ["S1.bam"]
# Output: ["S1.vcf"]
# Params: {"threshold": 0.9}
# Threads: 1
# Python source: /path/to/output/.audit_process.py
```

## Using modified Snakemake source code

The project has a local Snakemake source at `workflow/snakemake/`.

### Option A: PYTHONPATH (temporary)

```bash
export PYTHONPATH=/data/pub/zhousha/20260207_Exome/workflow/snakemake/src:$PYTHONPATH
snakemake --snakefile ... --cores 8
```

### Option B: pip install -e (permanent, recommended)

```bash
conda activate smk
cd /data/pub/zhousha/20260207_Exome/workflow/snakemake
pip install -e .
```

Creates a symlink — modifications take effect immediately without re-install.

### Verify

```bash
conda activate smk
python -c "import snakemake; print(snakemake.__file__)"
# Should output: /data/pub/zhousha/20260207_Exome/workflow/snakemake/src/snakemake/__init__.py
```

### Restore original

```bash
conda activate smk
pip install snakemake==9.23.0
```

## Snakemake execution architecture (two paths)

Understanding the execution flow helps know WHERE to add modifications:

```
shell: directive
  └─ run_single_job → run_wrapper (direct) → shell.__new__() → sp.Popen

run: directive (no shadow)
  └─ run_single_job → run_wrapper (direct) → job_rule.run_func()

run: directive (with shadow)
  └─ run_single_job → spawn_job → subprocess: python -m snakemake ...
       └─ (child process) → run_wrapper → job_rule.run_func()

script:/wrapper:/notebook:
  └─ run_single_job → run_wrapper (direct) → job_rule.run_func()
```

**Key insight**: `run_wrapper` is the convergence point for ALL execution
paths. `spawn_job` generates a subprocess that eventually calls `run_wrapper`
too. So modifying `run_wrapper` covers everything.

The `shell.__new__` modification captures the FINAL command after all
wrapping (conda, singularity, envmodules) — this is what actually runs.

## Design: full ScriptSaveSettings approach (not implemented)

The full approach adds CLI args (`--script-dir`, `--script-header`, etc.)
and a `script_save.py` module with HPC header generation. Files to modify:
- `src/snakemake/settings/types.py` (~25 lines)
- `src/snakemake/cli.py` (~40 lines)
- `src/snakemake/script_save.py` (new file, ~400 lines)

This is overkill for audit logging — the simpler two-layer approach above
is sufficient for most use cases.

## Maintenance note

This modification lives in the project-local Snakemake source at
`workflow/snakemake/`. If Snakemake is upgraded, these patches need to be
re-applied. Files to patch:
- `src/snakemake/shell.py` (~30 lines — audit logging)
- `src/snakemake/executors/local.py` (~35 lines — audit logging)
