# Extracting run: block logic into standalone scripts

Use this reference when a Snakemake `run:` block grows beyond ~40 lines of business logic. The user's standing preference is: extract the logic into a standalone Python script under `bin/`, and have the `.smk` rule construct a CLI argument list and call it. Do not pile everything inside the `run:` block.

## Two-layer architecture: smk follows modules.md, bin/ uses direct subprocess

This is a critical distinction. There are TWO execution layers, each with a DIFFERENT command-construction pattern:

- **`.smk` layer**: MUST follow `modules/modules.md` spec. Construct `cmd = [...]` list, write `" ".join(cmd)` into a timestamped `.sh` script, execute via `shell(f"bash {script} >> {log_path} 2>&1")`. This records the complete call command for reproducibility. Do NOT use `shell(shlex.join(cmd))` in the `.smk`.
- **`bin/` script layer**: Executes commands directly via `subprocess.run(cmd)`. Does NOT generate `.sh` files. Writes a `.cmd.log` for reproducibility.

The user explicitly corrected this: "snakefile还是要用shell记录完整调用命令,遵循module.md规范". The `.smk` must use the shell-script pattern per modules.md, NOT `shell(shlex.join(cmd))`.

## When to extract

- The `run:` block builds a multi-command pipeline with complex branching (PE vs SE, multi-pass loops, conditional overrides).
- Helper functions (e.g. `star_options`, `samtools_fastq`) are defined inside the `run:` block, making it hard to test independently.
- The same logic cannot be unit-tested without a full Snakemake context.

## Architecture

```
modules/<tool>/
├── <tool>.smk              # thin wrapper: reads config, builds cmd list, writes .sh, executes
└── bin/
    └── <tool>_align.py     # all business logic: argparse, build_steps(), main()
```

### .smk layer (follows modules.md spec)

The `.smk` file follows the standard `modules.md` template exactly:

1. `open(log_path, "w").close()` - clear old log
2. `setup_logger("rule_name", log_file=log_path)` - unified logging
3. `current_time = time.strftime(...)` - timestamp
4. `script = os.path.join(sample_outdir, f"tool_{current_time}.sh")`
5. Constructs `cmd = ["python", HELPER, "--fastq", ..., "--param", value, ...]` list
6. `with open(script, "w") as f: f.write(" ".join(cmd) + "\n")`
7. `shell(f"bash {script} >> {log_path} 2>&1")`
8. `try/except` with `raise e`

Key: the `.smk` uses `" ".join(cmd)` (not `shlex.join`), and executes via `shell(f"bash {script} >> {log} 2>&1")` (not `shell(shlex.join(cmd))`). No `import shlex` in the `.smk`.

### bin/ script layer (direct subprocess execution)

The `bin/` script:
1. Defines `argparse` with explicit typed parameters and literature defaults.
2. `build_steps(args)` returns a `list[Step]` - each Step is a command to execute directly.
3. `main()` executes each Step via `subprocess.run(cmd)` and writes a `.cmd.log` for reproducibility.

## Direct subprocess execution, NOT shell-script generation

This is a hard rule from the user. Do not generate a `.sh` file and then run it with `subprocess.run(["bash", script])`. That is an unnecessary indirection — Python constructing shell strings to feed back to bash. Instead:

- Each command is a `list[str]` executed directly via `subprocess.run(cmd, ...)`.
- Pipelines (`cmd1 | cmd2`) use `subprocess.Popen` with `stdout=PIPE` → `stdin=PIPE`.
- Stdout redirects (`cmd > file`) use `subprocess.run(cmd, stdout=open(file, "wb"))`.
- For reproducibility, write `shlex.join(cmd)` lines into a `.cmd.log` file — this is a record only, never the execution path.

### Step dataclass pattern

```python
from dataclasses import dataclass

@dataclass
class Step:
    cmd: list[str]
    desc: str = ""
    pipe_to: list[str] | None = None    # if set, cmd stdout pipes into pipe_to
    stdout: str | None = None           # if set, redirect final stdout to this file
    skip_log: bool = False              # if True, don't log stdout/stderr
```

### _run_step: direct execution

```python
def _run_step(step: Step, log_handle) -> None:
    # Log the command for reproducibility
    cmd_str = shlex.join(step.cmd)
    if step.pipe_to:
        cmd_str += " | " + shlex.join(step.pipe_to)
    if step.stdout:
        cmd_str += " > " + shlex.quote(step.stdout)
    log_handle.write(f"\n{'=' * 60}\n{step.desc}\n$ {cmd_str}\n")

    if step.pipe_to:
        p1 = subprocess.Popen(step.cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(step.pipe_to, stdin=p1.stdout,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.stdout.close()
        stdout, stderr = p2.communicate()
        # check return codes...
    elif step.stdout:
        with open(step.stdout, "wb") as out:
            subprocess.run(step.cmd, stdout=out, stderr=log_handle, check=True)
    else:
        subprocess.run(step.cmd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, check=True)
```

### Gene loops in Python, not bash

When the old code used a bash `while IFS=$'\t' read -r ...` loop over a manifest TSV, replace it with a Python loop:

```python
genes = _read_manifest(manifest_path)  # parse TSV into list[dict]
for gene in genes:
    gene_id = gene["gene_id"]
    fq1, fq2 = gene["fastq1"], gene["fastq2"]
    # PE/SE detection via file size, not bash [ -s "$fq2" ]
    read_files = [fq1]
    if os.path.getsize(fq2) > 0:
        read_files.append(fq2)
    # execute STAR, samtools, Tailer directly...
```

This eliminates all shell-variable quoting issues (`"$index"`, `$reads` word-splitting) because variables are native Python strings passed as list elements to `subprocess.run`.

### Command log for reproducibility

```python
cmd_log = os.path.join(outdir, f"three_pass_{stamp}.cmd.log")
with open(cmd_log, "w") as cmd_handle:
    for step in steps:
        line = shlex.join(step.cmd)
        if step.pipe_to:
            line += " | " + shlex.join(step.pipe_to)
        if step.stdout:
            line += " > " + shlex.quote(step.stdout)
        cmd_handle.write(line + "\n")
```

## Parameter passing: explicit typed CLI args, never JSON blobs

This is a hard rule from the user. Do not pass structured parameters (STAR options, tool configs) as a `--pass-params '{"key": "value"}'` JSON string. Every tunable parameter must be a dedicated CLI argument with:

- A clear `--name` (kebab-case, e.g. `--pass1-out-filter-multimap-nmax`).
- An explicit `type=` (int, float, str, or choices).
- A default value (literature-derived) set via `parser.set_defaults()` or `default=`.
- A `help=` string referencing the underlying tool flag (e.g. `"STAR --outFilterMultimapNmax"`).

Group related parameters with `parser.add_argument_group()` so `--help` is organized.

### Pattern: per-pass parameters with shared structure

When a tool has per-pass or per-stage parameters with the same names, use a shared list and a helper:

```python
_PASS_PARAMS = [
    ("out_filter_multimap_nmax", "--outFilterMultimapNmax", int),
    ("out_filter_mismatch_nover_lmax", "--outFilterMismatchNoverLmax", float),
    ("align_ends_type", "--alignEndsType", str),
]

def _add_pass_args(group, prefix):
    for attr, flag, cast in _PASS_PARAMS:
        group.add_argument(f"--{prefix}-{attr.replace('_', '-')}", ...)

def _collect_pass_options(pass_name, paired, args, ...):
    opts = {}
    for attr, flag, cast in _PASS_PARAMS:
        val = getattr(args, f"{pass_name}_{attr}")
        if val is not None:
            opts[flag] = cast(val)
    ...
```

### Pattern: PE/SE-dependent defaults

When a parameter's default depends on paired/single-end mode (e.g. STAR `clip5pNbases` is `"20 0"` for PE, `"20"` for SE), set the argparse default to `None` and apply the paired-dependent default in the option-collection function:

```python
# argparse: default=None
parser.add_argument("--pass2-clip5p-nbases", default=None, ...)

# in _collect_pass_options:
if opts.get("--clip5pNbases") is None:
    opts["--clip5pNbases"] = "20 0" if paired else "20"
```

This preserves the user's ability to explicitly override for either mode.

## .smk -> script parameter forwarding

The `.smk` reads from the config dict and only forwards keys that are present. Parameters not in the config fall back to the script's built-in defaults:

```python
p1 = three_pass_params.get("pass1", {})
cmd = ["python", HELPER, "--fastq", *fastqs, ...]
if "outFilterMultimapNmax" in p1:
    cmd += ["--pass1-out-filter-multimap-nmax", str(p1["outFilterMultimapNmax"])]
if "alignEndsType" in p1:
    cmd += ["--pass1-align-ends-type", str(p1["alignEndsType"])]
```

This keeps the config schema as the source of truth while the script owns the defaults.

## Python 3.9 compatibility: use typing module, not PEP 604

This is a hard rule from the user. The project's Python environments include 3.9, which does not support PEP 604 union syntax (`X | None`) or `dict[str, str]` / `list[str]` as runtime annotations outside of `__annotations__`. Use the `typing` module instead:

```python
from typing import Dict, List, Optional, Set

# CORRECT
def load_updown_sets(path: str) -> Dict[str, Set[str]]: ...
def write_file_inventory(..., intersection_data: Optional[Dict[str, List[str]]] = None) -> None: ...

# WRONG - will crash on Python 3.9
def write_file_inventory(..., intersection_data: dict[str, list[str]] | None = None) -> None: ...
```

This applies to ALL function signatures and variable annotations in scripts under `bin/`.

## Reusing existing project libraries

Before implementing a plotting or analysis utility from scratch, check `src/common/` for existing reusable code. The user explicitly corrected this: use the existing library rather than reimplementing. Do NOT hand-draw Venn circles with matplotlib patches when venn.py is available.

### Scripts must not embed environment paths

The user explicitly corrected this: do not embed any environment in scripts, use plain python to not affect portability. Scripts must use plain `#!/usr/bin/env python3` shebangs and `python` invocations. Do NOT hardcode paths like `#!/home/luosg/miniconda3/envs/DNA/bin/python` in shebangs or subprocess calls. Activate the conda environment in the shell before running the script. This keeps scripts portable across machines and users.

### Example: venn.py integration

`workflow/Omics/src/common/plot/Python/venn.py` provides `venn2` through `venn6` functions supporting 2-6 set Venn diagrams. Import it via sys.path manipulation:

```python
import os, sys
_VENN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "common", "plot", "Python")
if os.path.isdir(_VENN_DIR) and _VENN_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_VENN_DIR))
try:
    import venn as venn_lib
except ImportError:
    venn_lib = None
```

Usage pattern: call `venn_lib.get_labels(sets, fill=["number"])` to get region counts, then `venn_lib.vennN(labels_dict, names=labels)` to get `(fig, ax)`.

**Critical pitfall**: venn.py uses `plt.figure(0, ...)` internally with a fixed figure number. When called multiple times in sequence (e.g. 4 Venn diagrams), the global figure state leaks and corrupts subsequent matplotlib figures. Must wrap with `plt.close("all")` before and after every venn.py call:
```python
plt.close("all")
fig, _ax = venn_func(labels_dict, names=labels, ...)
path = img_store.save_fig(fig, stem)
plt.close("all")
```

For 7+ sets where venn.py has no corresponding function, fall back to an UpSet-style bar chart (pairwise intersection sizes). Do NOT reimplement Venn circle drawing when venn.py is available.

### Gene source for Venn: .name.tsv with padj/log2FC filtering

When building Venn diagrams of DE genes/TEs across contrasts, read from `TEcount_Gene.name.tsv` / `TEcount_TE.name.tsv` (gene symbols, first column). These files do NOT have a `sig` column - filter by `padj < 0.05` (strict <) and `|log2FoldChange| >= 0.58` to define up/down sets, matching DESeq2.r `ScreenFeature` defaults (`lfc_cut=0.58`, `padj_cut=0.05`). See `references/rnaseq-report-module.md` for the full pattern.

## shlex.quote for space-containing values in .smk shell scripts

**Pitfall**: When a config value contains spaces (e.g. STAR `clip5pNbases="20 0"`), writing it into a `.sh` script with `" ".join(cmd)` produces `--pass2-clip5p-nbases 20 0`. The shell splits `20 0` into two tokens, and argparse reports `unrecognized arguments: 0 20`.

**Symptom**: `three_pass_align.py: error: unrecognized arguments: 0 20` in the snakemake log. The rule fails immediately at the argparse stage.

**Fix**: Use `shlex.quote` when joining the command list into the shell script:

```python
import shlex

with open(script, "w") as f:
    f.write(" ".join(shlex.quote(str(x)) for x in cmd) + "\n")
```

`shlex.quote("20 0")` produces `'20 0'` (single-quoted), which the shell preserves as a single argument. Values without spaces (e.g. `"1000"`) are returned unquoted, so the output remains readable.

**Important**: This applies to ALL `.smk` files that write command lists into shell scripts. Both `star_3pass.smk` and `star_3pass_gene.smk` were fixed. The `bin/` scripts are unaffected because they use `subprocess.run(cmd_list)` directly (no shell interpolation).

This revises the earlier rule "no `import shlex` in `.smk`". The `.smk` DOES need `import shlex` for the `shlex.quote` call in the join. The rule was originally about not using `shlex.join()` as the execution method (use `shell(f"bash {script} ...")` instead). That rule still holds - `shlex.quote` is only for the script-writing step, not for execution.

## Verification

Ad-hoc verification for extracted scripts should check:

### .smk layer (modules.md compliance)
1. `open(log_path, "w").close()` present
2. `setup_logger(...)` called
3. `current_time` timestamp used for script filename
4. `cmd = [...]` list construction
5. `with open(script, "w"): f.write(" ".join(shlex.quote(str(x)) for x in cmd) + "\\n")` - uses `shlex.quote` to handle space-containing values
6. `shell(f"bash {script} >> {log_path} 2>&1")` - NOT `shell(shlex.join(cmd))`
7. `try/except` with `raise e`
8. `import shlex` present in `.smk` for the `shlex.quote` call

### bin/ script layer (direct subprocess)
1. `--help` output lists all parameters with types, no JSON blob arguments remain.
2. Literature defaults are correct (e.g. PE `clip5pNbases="20 0"`, SE `clip5pNbases="20"`).
3. Config overrides flow through: pass an explicit `--pass1-out-filter-multimap-nmax 500` and confirm it appears in the Step list.
4. `force_end_to_end` and `hard_clip_5p` override flags still work.
5. `build_steps()` returns correct count of Steps with correct pipe_to/stdout attributes.
6. `_run_step` executes simple commands, pipelines, and redirects correctly.
7. `.cmd.log` is written with `shlex.join` for every step.
8. No `build_script` function, no `["bash", script]` execution in source.
9. For gene-specific scripts: `_read_manifest` parses TSV correctly, gene loop runs in Python, PE/SE detected via `os.path.getsize`.

### Integration
1. `snakemake --dry-run` reaches "Building DAG of jobs" with no SyntaxError/NameError/AttributeError.
