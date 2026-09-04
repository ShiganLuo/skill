# Splitting Monolithic Tools into Snakemake Sub-Modules

When a tool has multiple sequential stages (e.g. mimseq with tRNAtools→align→clusters→mods→coverage→deseq), splitting into independent Snakemake modules enables better error recovery, parallelism, and debugging.

## Architecture Pattern

```
modules/<tool>/
├── bin/
│   ├── serialize.py         # pickle/JSON state utilities
│   ├── utils.py             # shared helpers (e.g. extract_condition)
│   ├── stage1/run.py        # wrapper for stage 1
│   ├── stage2/run.py        # wrapper for stage 2
│   └── ...
├── stage1/stage1.smk        # Snakemake rule for stage 1
├── stage2/stage2.smk        # Snakemake rule for stage 2
├── <tool>.smk               # main module (includes all sub-smk, defines meta-rule)
├── <tool>.yaml              # conda environment
└── <tool>/                  # copied/modified source code
```

## State Passing Between Modules

Use pickle for complex objects (dataframes, dicts), JSON for simple metadata:

```python
# bin/serialize.py
import pickle, json

def save_state(state: dict, outdir: str, prefix: str):
    with open(f"{outdir}state/{prefix}_state.pkl", "wb") as f:
        pickle.dump(state, f)

def load_state(indir: str, prefix: str) -> dict:
    with open(f"{indir}state/{prefix}_state.pkl", "rb") as f:
        return pickle.load(f)
```

Each stage loads state from previous stage, adds its own outputs, saves updated state.

## Main Module Pattern (<tool>.smk)

```python
# Include all sub-module rules
include: "stage1/stage1.smk"
include: "stage2/stage2.smk"
...

# Meta-rule that depends on final .done file
rule <tool>_all:
    input: outdir + "<tool>.done"

# Final stage creates the .done sentinel
rule result:
    input: outdir + "deseq.done"
    output: outdir + "<tool>.done"
    shell: "touch {output}"
```

## Subworkflow Integration

In the subworkflow .smk, import ALL intermediate rules via `use rule`:

```python
use rule <tool>_all from <tool> as <tool>_<workflow>_all
use rule stage1 from <tool> as <tool>_<workflow>_stage1 with:
    ...
use rule stage2 from <tool> as <tool>_<workflow>_stage2 with:
    ...
```

## Wrapper Script Pattern (bin/stageN/run.py)

```python
#!/usr/bin/env python
"""Wrapper for <tool> stage N — bridges Snakemake I/O with tool internals."""
import os, sys

# CRITICAL: Use MIMSEQ_PARENT (parent of mimseq package), NOT MIMSEQ_DIR
MIMSEQ_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, MIMSEQ_PARENT)

# Import as module to avoid relative import errors
import mimseq.stage_module as stage_module

def main(args):
    stage_module.run_function(...)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    # Add --indir, --outdir, --sample-data, etc.
    args = parser.parse_args()
    main(args)
```

## Critical: Import Pattern for Sub-Packages

When the tool package contains a file with the same name as the package (e.g. `mimseq/mimseq.py`),
relative imports like `from . import version` will fail when using `from mimseq.X import func`.

**Solution**: Use `import mimseq.X as X_module` instead of `from mimseq.X import func`.

This avoids triggering the relative import in `mimseq/mimseq.py` line 16 (`from . import version`).

## Critical: MIMSEQ_DIR vs MIMSEQ_PARENT

Wrapper scripts often set:
```python
MIMSEQ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```
This points to `modules/mimseq/` (the sub-module parent), NOT the mimseq package directory.

**Solution**: Use `MIMSEQ_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` to get the parent of the mimseq package.

## Critical: Global Variables in Source Code

Some tools use global variables that must be set before importing submodules (e.g. `ssAlign.stkname`).
Set these in the wrapper script before calling the main function:

```python
# Find and set stkname from existing .stk file
stk_files = glob.glob(f"{outdir}*_align.stk")
if stk_files:
    ssAlign_module.stkname = stk_files[0]
```

## Critical: Module Prefix for Function Calls

When using `import mimseq.X as X_module`, all function calls MUST use the module prefix:
```python
# WRONG — NameError: name 'generateModsTable' is not defined
generateModsTable(...)

# CORRECT
X_module.generateModsTable(...)
```

When splitting monolithic code, it's easy to forget the prefix since the original code called
functions bare. Every `from mimseq.X import func` → `import mimseq.X as X_module` conversion
requires updating ALL call sites to `X_module.func(...)`.

## Critical: Argparse Empty String in Shell Commands

When a .smk file generates a bash script with `"--param", some_var`, if `some_var` is `""`,
the generated command becomes `--param --next-param`, and argparse consumes `--next-param`
as the value of `--param`.

**Fix**: Conditionally add the argument only when non-empty:
```python
cmd = ["python", "script.py", "--other-arg", "value"]
if params.optional_param:
    cmd += ["--param", params.optional_param]
```

And in the run.py, use `default=""` not `required=True` for that parameter.
