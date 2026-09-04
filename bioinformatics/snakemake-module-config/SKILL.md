---
name: snakemake-module-config
description: Understand and modify Snakemake module configuration in this bioinformatics pipeline project
tags: [snakemake, pipeline, config, bioinformatics]
---

# Snakemake Module Config Architecture

## Purpose
Understand how configuration flows through this Snakemake-based bioinformatics pipeline, from user-facing JSON templates to module execution.

## Architecture Overview

```
User CLI args (run.py)
    ↓
Module JSON template (e.g., mimseq.json)
    ↓
run.py::run<Workflow>() function - populates datajson with runtime values
    ↓
raw.json - written to output dir, passed to Snakemake as --configfile
    ↓
Subworkflow .smk (e.g., tRNAseq.smk) - reads config, constructs module-specific config dict
    ↓
module .smk (e.g., mimseq.smk) - receives config dict via `module X: config: ...`
    ↓
Sub-module .smk (e.g., tRNAtools.smk) - reads from config.get()
    ↓
Python scripts - invoked via shell with CLI args from params
```

## Key Files Per Module

Each module has:
1. `<module>.json` - Default config template (in `workflow/Omics/modules/<module>/`)
2. `<module>.smk` - Main module Snakefile
3. `bin/<submodule>/run.py` - Python wrapper scripts
4. Sub-module `.smk` files in subdirectories

## Config Flow Details

### 1. JSON Templates Are Just Defaults
The module's `.json` file provides default values. It is NOT the actual config used at runtime.

### 2. run.py Is The Source Of Truth
`workflow/Omics/run.py` contains `run<Workflow>()` functions (e.g., `runtRNAseq`, `runMutation`) that:
- Load the JSON template via `_load_model_json()`
- Set `datajson["ROOT_DIR"] = os.path.dirname(__file__)` (resolves to `workflow/Omics/`)
- Set other runtime values (indir, outdir, logdir, samples, etc.)
- Write the populated dict to `<outdir>/raw.json`

### 3. Subworkflows Construct Module Configs
Subworkflow `.smk` files (in `subworkflow/`) create module-specific config dicts:
```python
mimseq_config = {
    "indir": ...,
    "outdir": ...,
    "ROOT_DIR": ROOT_DIR,
    "data_dir": config.get("data_dir", ""),
    "Params": {"mimseq": config.get("Params", {}).get("mimseq", {})},
    ...
}
module mimseq:
    snakefile: "../modules/mimseq/mimseq.smk"
    config: mimseq_config
```

### 4. Modules Read Via config.get()
Module `.smk` files read values using `config.get()` with defaults:
```python
ROOT_DIR = config.get("ROOT_DIR", ".")
species = config.get("Params", {}).get("mimseq", {}).get("species", "")
```

## Import Path Conventions

All Python scripts under the Omics project that reference `src/common/util/`
modules must use `from src.common.util.<Module> import <symbol>` (not
`from common.util.*` or `from common.X`). This matches `run.py`'s convention
and requires the Omics root directory in `sys.path`.

Each script must compute the correct `os.path.dirname()` nesting depth to reach
the Omics root. The depth depends on the script's directory depth:

- `modules/<mod>/bin/*.py` → x4 dirname
- `modules/<mod>/bin/utils/*.py` → x5 dirname
- `src/download/*.py` → x3 dirname
- `src/common/ml/MSI/data/*.py` → x6 dirname
- Deeper nested scripts need proportionally more dirname calls

Always verify: `os.path.isdir(os.path.join(target, "src", "common", "util"))`.

Snakemake invokes scripts via `python /abs/path/script.py args` with cwd set to
the output directory (NOT Omics root). No PYTHONPATH is set. The only way
imports work is via explicit `sys.path` manipulation in each script.

`src/common/ml` is a git submodule (repo: ShiganLuo/ML.git). Changes under it
must be committed and pushed in the submodule first, then the parent Omics repo
updated with the new submodule commit hash.

See `snakemake-omics-workflow` skill `references/import-path-conventions.md`
for the full depth cheat sheet and per-location patterns.

## Pitfalls

### ❌ Wrong: Modifying Only The Module's JSON Template
The JSON template is just defaults. Changing it alone does nothing at runtime.

### ❌ Wrong: Modifying Only The Python Script
Adding a CLI arg to `bin/*/run.py` without passing it from the smk accomplishes nothing.

### ❌ Wrong: Modifying Only The Sub-Module .smk
Adding a config read in `tRNAtools.smk` without the subworkflow passing it through won't work.

### ✅ Correct: Full Stack Modification
To add a new config parameter:
1. Add default to `modules/<module>/<module>.json`
2. Add to `run<Workflow>()` in `run.py` (sets actual value)
3. Add to module config dict in `subworkflow/<workflow>.smk`
4. Read in module/sub-module `.smk` via `config.get()`
5. Pass as param to Python script in the rule

## Finding Config References

To find all files that need modification for a config change:
```bash
# Find which subworkflow imports the module
grep -r "module <name>:" workflow/Omics/subworkflow/*.smk

# Find config dict construction
grep -r "<module>_config" workflow/Omics/subworkflow/*.smk

# Find run<Workflow> function
grep -r "def run<Workflow>" workflow/Omics/run.py
```

## Adding New Config Parameters

Pattern for adding a configurable path (e.g., data_dir):

1. **JSON template**: Add `"data_dir": ""`
2. **run.py**: `datajson["data_dir"] = os.path.join(os.path.dirname(__file__), "modules", "<module>", "<module>", "data")`
3. **Subworkflow**: Add `"data_dir": config.get("data_dir", ""),` to module config dict
4. **Module smk**: `data_dir = config.get("data_dir", "") or os.path.join(ROOT_DIR, ...)`
5. **Python script**: Add `--data-dir` argument, use with fallback

## Removing Config Parameters

Removing a parameter is the reverse of adding -- every layer that reads or
passes it must be cleaned. Use `search_files` with the param name (both
snake_case and kebab-case CLI forms) to find all references before editing.

Full-stack removal checklist:
1. **JSON config**: Delete the key from `config/<workflow>.json`
2. **Schema**: Delete the key's schema entry from `config/<workflow>.schema.json`
3. **Subworkflow .smk**: Delete the key from any module config dict
4. **Module .smk**: Delete the variable definition (`x = config.get(...)`) and
   the CLI arg (`"--x", str(x)`) in the rule's `cmd` list
5. **Python script**: Delete the argparse `add_argument`, any function
   parameter that received it, and all call sites passing it
6. **Verify**: `search_files` for both `param_name` and `param-name` returns
   zero hits; `python -m py_compile` passes; argparse `--help` no longer
   shows the flag; argparse rejects the old flag as unrecognized

### Pitfall: redundant parameters that duplicate STAR flags

Before adding a new config field that wraps or overrides an existing STAR
parameter, check whether the per-pass config already controls it. For example,
`hard_clip_5p` was a standalone integer that `three_pass_align.py` converted
to `--clip5pNbases` at runtime, overriding the pass2 `clip5pNbases` config --
pure duplication. The fix is to remove the wrapper and let the per-pass
config be the sole control. See `snakemake-omics-workflow` skill
`references/star-3pass-gene-alignment.md` for the full case study.

### Pitfall: misclassified parameters in wrong config section

Index-build parameters (e.g., `genomeSAindexNbases` for STAR
`genomeGenerate`) must NOT be nested under `passes.pass1` alongside alignment
parameters. They belong in a dedicated `index` sub-key so that index-build
and alignment configs are cleanly separated. When relocating a parameter
across config sections, update all layers: JSON config, schema, .smk variable
reads, CLI arg names (rename `--pass1-genome-sa-index-nbases` to
`--index-genome-sa-index-nbases`), argparse definitions, and the Python
script's attribute access. The verification is the same as removal -- old
references must be zero, argparse must reject the old flag.

### Pitfall: SIF container missing the conda environment

When a SIF is built from a Dockerfile that runs `conda env create -f env.yaml`,
the build can silently produce an incomplete image if conda fails during the
Docker build (e.g., channel conflicts, package resolution failures). The
resulting SIF has only the base conda environment — no R, no Rscript, no
tool-specific binaries — but the SIF file exists and appears valid.

Symptom: `Rscript: command not found` (or similar) inside the container, exit
status 127, even though the SIF file exists and singularity can exec into it.

Diagnosis: `singularity exec <sif> bash -c 'ls /opt/conda/envs/'` — if empty,
the conda env was never created. Also check: `singularity exec <sif> bash -c
'which Rscript'`.

Fix: rebuild the SIF. Use `EnvUtil.py` to regenerate the Dockerfile, then
rebuild the Docker image and convert to SIF. After rebuilding, verify the
key binary exists inside the container before running the pipeline.

This is not unique to DESeq2 — any module using the `conda env create` pattern
in its Dockerfile can have this issue.

## Relocating Config Parameters

When a parameter needs to move from one config section to another (not
removed, just restructured), apply the full-stack checklist:

1. **JSON config**: Move the key to its new parent section
2. **Schema**: Move the schema entry to match the new nesting
3. **Module .smk**: Update the `config.get()` path to read from the new
   location; update the CLI arg name if renaming
4. **Python script**: Rename the argparse arg, the attribute access
   (`args.new_name`), and all call sites
5. **Verify**: `search_files` for old name returns zero; argparse `--help`
   shows new flag; argparse rejects old flag

## Execution Architecture

### run.py: The Sole Entry Point

`workflow/Omics/run.py` is the only correct way to launch Omics workflows.
Never call `snakemake` directly -- run.py builds the command with correct
config, bind paths, and environment backend.

### Two environment backends

1. **Conda** (`--use-conda`, default): Each rule's `conda: "xxx.yaml"` directive
   creates/uses a conda env. Requires `--conda-prefix <dir>`.
2. **Apptainer/SIF** (`--sdm apptainer`): Each rule's `container: sif("xxx.yaml")`
   directive uses a pre-built SIF image. Omits `--use-conda` entirely. SIF paths
   resolved by `sif()` in `modules/common/common.smk` via `config["env"]` mapping.

### Rule execution pattern: run: + .sh script

ALL 175 rules use `run:` blocks (zero use `shell:` directive). 83 .smk files
generate `.sh` scripts containing bare commands (no env activation, no
`apptainer exec`). Environment isolation is handled entirely by snakemake's
`--sdm apptainer` or `--use-conda` at the rule level. The .sh scripts
**cannot be executed independently** without manual environment setup.

### Single-step execution and target control

run.py provides `--forcerun` as a first-class argument for precise job reruns.
It accepts snakemake target syntax (`RULE` or `RULE:WILDCARD=VALUE`).

**Auto-prefixing:** Subworkflows rename rules via `use rule ... as <wf>_...`
(e.g., `function_gsea` becomes `RNAseq_function_gsea`). run.py auto-prefixes
forcerun targets with the workflow name, so users write the original rule name.
Already-prefixed names and `all` are passed through unchanged.

**DAG semantics:** `--forcerun` alone forces the target to rerun AND triggers
downstream reruns if their outputs need updating. To rerun ONLY the target
(without downstream), run.py emits BOTH `--until` and `--forcerun` with the
same targets -- `--until` truncates the DAG so downstream isn't in the graph.

```bash
# Rerun a specific sample's trimming (no downstream)
python run.py -m meta.tsv -w RNAseq -o output -t 10 \
    --sdm apptainer \
    --forcerun trimming_Paired:sample_id=S1

# Rerun a rule without wildcards
python run.py -m meta.tsv -w RNAseq -o output -t 10 \
    --sdm apptainer \
    --forcerun function_gsea

# Multiple targets
python run.py -m meta.tsv -w RNAseq -o output -t 10 \
    --sdm apptainer \
    --forcerun trimming_Paired:sample_id=S1 trimming_Paired:sample_id=S2
```

Generated snakemake command:
```
snakemake -s .../RNAseq.smk --configfile raw.json --cores 10 \
    --sdm apptainer --singularity-args '--bind ...' \
    --until RNAseq_trimming_Paired:sample_id=S1 \
    --forcerun RNAseq_trimming_Paired:sample_id=S1
```

**Pitfall: positional targets don't work for rule names.** Snakemake treats
bare positional targets as file paths. `function_gsea` as a positional target
raises `MissingRuleException`. Always use `--forcerun` (which accepts rule names).

### How outfiles defines the DAG boundary

Each subworkflow's `rule all` has `input: outfiles`, where `outfiles` is set
by `run<Workflow>()` in run.py. Only rules whose outputs are direct or
transitive dependencies of `outfiles` entries are in the DAG. `--forcerun`
only works on jobs already in the DAG. In practice, all pipeline intermediate
steps (cutadapt, alignment, quantification, etc.) are upstream of `outfiles`,
so `--forcerun` works correctly for rerunning specific samples/steps.

### Why not embed apptainer exec in .sh scripts

Embedding `apptainer exec` in .sh scripts would require changing 83 .smk files,
create two execution paths (snakemake-wrapped vs standalone), hardcode SIF
paths, and lose dependency resolution. Using snakemake's native target/force
mechanisms is strongly preferred.

### Pitfall: --snakemake-args REMAINDER vs positional targets

`--snakemake-args` uses `argparse.REMAINDER`, consuming ALL subsequent args.
This conflicts with bare positional targets (`RULE:WILDCARD=VALUE`). Use
`--snakemake-args --forcerun RULE:WILDCARD=VALUE` (works because forcerun is
a named flag inside REMAINDER) or add `--forcerun` as a first-class run.py arg.

Additionally, the extra_args parsing loop (which collects `--key value` pairs
for config override) will swallow bare `RULE:WILDCARD=VALUE` tokens as values
for the preceding `--key`. Use `--` separator or named args to avoid this.

See `references/execution-architecture.md` for full details on
build_snakemake_cmd(), bind path auto-collection, sif() resolution,
DAG/target semantics, and the complete run.py CLI reference.

## Reference Files

- `workflow/Omics/run.py` - Main entry point, all `run<Workflow>()` functions
- `workflow/Omics/subworkflow/*.smk` - Subworkflow definitions
- `workflow/Omics/modules/*/` - Module implementations
- `references/schema-format.md` - Custom schema format (NOT JSON Schema) for `config/*.schema.json`
