# Snakemake shell.py auto-script generation modification

## Problem

Every `run:` block that calls `shell()` needs manual boilerplate to save the
executed command to a script file for debugging/reproducibility:

```python
# Repeated in EVERY run: block
current_time = time.strftime("%Y%m%d_%H%M%S")
script = os.path.join(outdir, f"{sid}/tool_{current_time}.sh")
cmd = [...]
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(cmd) + "\n")
shell(f"bash {script} >> {log} 2>&1")
```

This is ~10 lines of pure boilerplate per rule, and the saved script only contains
the **raw** command — not the conda/singularity-wrapped version that actually executes.

## Solution: two-layer architecture

### Layer 1: `run_wrapper` (executors/local.py) — all rule types

Generates top-level reproducible script BEFORE rule execution. Handles shell, run,
script, and wrapper rules.

### Layer 2: `shell.__new__` (shell.py) — supplementary capture

Captures individual `shell()` calls within `run:` blocks, saved to
`{logdir}/shell_commands/` for debugging.

---

## Layer 2: shell.__new__ modification

File: `workflow/snakemake/src/snakemake/shell.py`

Added automatic script saving in `shell.__new__()`, after the command is fully
constructed (with conda/singularity wrapping) but before `subprocess.Popen`.

### Changes

1. Added `import time as _time` at top
2. Added auto-save block after line ~195 (after SHELLCMD log event):

```python
# Supplementary: log individual shell() calls from run: blocks
if func_context.get(RULEFUNC_CONTEXT_MARKER) and not context.get("is_shell"):
    try:
        _log = context.get("log")
        _rule = context.get("rule", "unknown")
        _wildcards = context.get("wildcards")
        if _log is not None:
            _log_path = str(_log[0]) if hasattr(_log, "__getitem__") else str(_log)
            _log_dir = os.path.dirname(_log_path)
            _cmd_dir = os.path.join(_log_dir, "shell_commands")
            os.makedirs(_cmd_dir, exist_ok=True)
            _wc_str = ".".join(
                f"{k}={v}" for k, v in sorted(_wildcards.items())
            ) if hasattr(_wildcards, "items") else str(_wildcards or "")
            _ts = _time.strftime("%Y%m%d_%H%M%S")
            _fname = f"{_rule}.{_wc_str}.{_ts}.cmd" if _wc_str else f"{_rule}.{_ts}.cmd"
            with open(os.path.join(_cmd_dir, _fname), "w") as _cf:
                _cf.write(f"# rule: {_rule}\n")
                _cf.write(f"# wildcards: {_wc_str}\n")
                _cf.write(f"# timestamp: {_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                _cf.write(cmd + "\n")
    except Exception:
        pass
```

### Key design decisions

1. **Only for `run:` blocks** — `shell:` rules already have their command in the
   Snakefile. The `not context.get("is_shell")` check skips them.
2. **Saves the WRAPPED command** — includes conda activation, singularity wrapping,
   etc. The saved script can be directly replayed with `bash script.sh`.
3. **Never breaks execution** — entire save logic is in try/except with pass.
4. **Script location**: `{log_dir}/shell_commands/{rule}.{wildcards}.{timestamp}.cmd`
5. **Metadata in comments**: rule name, wildcards, timestamp.

---

## Layer 1: run_wrapper modification (comprehensive)

### New file: `src/snakemake/script_save.py`

Script generation module with:
- `ScriptHeader` enum: BASH, SLURM, PBS, SGE
- `generate_header()` — generates HPC job scheduler headers
- `save_rule_script()` — main function, dispatches by rule type:
  - `shell:` → saves the shell command with conda activation
  - `run:` → extracts Python source via `inspect.getsource()`, injects
    concrete variable values, generates `.py` + `.sh` wrapper
  - `script:` / `wrapper:` → generates reference script with re-run instructions

### Modified: `src/snakemake/settings/types.py`

```python
@dataclass
class ScriptSaveSettings(SettingsBase):
    enabled: bool = True
    script_dir: Optional[Path] = None   # default: {logdir}/scripts/
    header: str = "bash"                 # bash/slurm/pbs/sge
    header_extra: str = ""               # extra SBATCH/PBS directives

# Added to ExecutionSettings:
    script_save: ScriptSaveSettings = field(default_factory=ScriptSaveSettings)
```

### Modified: `src/snakemake/cli.py`

4 new arguments in OUTPUT group:
- `--script-dir DIR` — output directory for scripts
- `--script-header {bash,slurm,pbs,sge}` — HPC header preset
- `--script-header-extra TEXT` — extra header directives
- `--no-script-save` — disable auto-save

Wired via `ScriptSaveSettings(...)` in `ExecutionSettings(...)` construction.

### Modified: `src/snakemake/executors/local.py`

- `job_args_and_prepare()` returns `self.workflow.execution_settings.script_save`
- `run_wrapper()` accepts `script_save_settings=None` parameter
- Before the `try:` block, calls `save_rule_script(...)` if enabled
- Header type resolved via `ScriptHeader(script_save_settings.header)`

---

## Usage

```bash
# Default (auto-enabled, saves to {logdir}/scripts/)
snakemake --snakefile ...

# SLURM cluster
snakemake --snakefile ... --script-dir /scratch/scripts --script-header slurm

# With extra SBATCH directives
snakemake --snakefile ... --script-header slurm \
  --script-header-extra "#SBATCH --partition=gpu"

# Disable
snakemake --snakefile ... --no-script-save
```

## Output structure

```
{logdir}/
  scripts/                              # Layer 1: run_wrapper scripts
    HaplotypeCaller.sample_id=DMSO_P20.20260620_170000.sh
    HaplotypeCaller.sample_id=DMSO_P20.20260620_170000.py  (run: rules)
  shell_commands/                       # Layer 2: individual shell() calls
    HaplotypeCaller.sample_id=DMSO_P20.20260620_170001.cmd
```

## For `run:` rules — Python source extraction

`save_rule_script()` uses `inspect.getsource(run_func)` to extract the Python
source code, then generates a self-contained `.py` file with:
1. Concrete variable values injected (input, output, params, wildcards, etc.)
2. A simplified `shell()` replacement that calls `subprocess.run`
3. The original run block source code

The `.sh` wrapper activates conda and calls `python script.py`.

Fallback: if `inspect.getsource()` fails (lambda, closure), generates a stub
with a warning.

## How shell.__new__ works internally

In `shell.__new__()`:
1. `func_context = inspect.currentframe().f_back.f_locals` captures the caller's locals
2. `RULEFUNC_CONTEXT_MARKER` check determines if called from a `run:` block
3. `context.get("log")`, `context.get("rule")`, `context.get("wildcards")` extract
   the rule metadata that Snakemake passes to every `run:` block function
4. The `cmd` variable (line ~219) contains the fully resolved command after all
   conda/singularity/env wrapping — this is what gets saved

## Effect on run: blocks

After this modification, `run:` blocks no longer need manual script generation.
The simplified pattern becomes:

```python
run:
    log_path = str(log)
    try:
        open(log_path, "w").close()
        logger = setup_logger(logger_name="my_rule", log_file=log_path)
        logger.info(f"Start for sample {wildcards.sample_id}")
        cmd = ["tool", "-i", input.fasta, "-o", output.vcf]
        shell(" ".join(cmd) + " >> {log_path} 2>&1")
    except Exception as e:
        with open(log_path, "a") as f:
            f.write(f"Error: {e}\n")
        raise
```

The script is auto-saved to `{log_dir}/scripts/my_rule.sample_id=XXX.20260620_124752.sh`.

## Maintenance note

This modification lives in the project-local Snakemake source at
`workflow/snakemake/`. If Snakemake is upgraded, these patches need to be
re-applied. Files to patch:
- `src/snakemake/shell.py` (~30 lines)
- `src/snakemake/executors/local.py` (~35 lines)
- `src/snakemake/settings/types.py` (~25 lines)
- `src/snakemake/cli.py` (~40 lines)
- `src/snakemake/script_save.py` (new file, ~400 lines)
