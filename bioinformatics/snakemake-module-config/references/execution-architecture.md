# Omics Execution Architecture

## run.py: The Sole Entry Point

`workflow/Omics/run.py` is the only correct way to launch Omics workflows.
Never call `snakemake` directly -- run.py builds the command with correct
config, bind paths, and environment backend.

## build_snakemake_cmd()

Constructs the snakemake CLI command:

```
snakemake
  -s <root_dir>/subworkflow/<workflow>.smk
  --configfile <outdir>/raw.json
  --cores <threads>
  --rerun-triggers <code input mtime params software-env>
  [--conda-prefix <dir> --use-conda --conda-frontend mamba]   # conda mode
  [--sdm apptainer --singularity-args '--bind ...']           # container mode
  [--dry-run]
  [<snakemake_args>]                                          # passthrough
```

## Two environment backends

1. **Conda** (`--use-conda`, default): Each rule's `conda: "xxx.yaml"` directive
   creates/uses a conda env. Requires `--conda-prefix <dir>`.
2. **Apptainer/SIF** (`--sdm apptainer`): Each rule's `container: sif("xxx.yaml")`
   directive uses a pre-built SIF image. Omits `--use-conda` entirely. SIF paths
   resolved by `sif()` in `modules/common/common.smk` via `config["env"]` mapping.

## sif() resolution (modules/common/common.smk)

```python
def sif(yaml_filename: str) -> str:
    stem = os.path.splitext(os.path.basename(yaml_filename))[0]
    # 1. Explicit mapping: config["env"]["<stem>"] -> "/path/to/<stem>.sif"
    if stem in _ENV_MAP:
        return _ENV_MAP[stem]
    # 2. Fallback: config["env"]["env_dir"] / <module_dir> / <stem>.sif
    env_dir = _ENV_MAP.get("env_dir")
    module_dir = os.path.basename(workflow.basedir)
    return os.path.join(env_dir, module_dir, f"{stem}.sif")
```

Config JSON `env` section example:
```json
{
  "env_dir": "/home/user/Database/env",
  "star": "/home/user/Database/env/star/star.sif",
  "cutadapt": "/home/user/Database/env/cutadapt/cutadapt.sif"
}
```

## Bind path auto-collection

When using `--sdm apptainer`, run.py automatically:

1. Scans `raw.json` recursively for path-like strings (anything containing `/`)
2. Collapses subdirectories into parents to minimise the bind list
3. Always adds `/tmp`
4. Merges with user-provided `--singularity-args --bind ...`
5. JSON-derived bind paths are always preserved; user paths are additive

Functions: `_collect_bind_paths()`, `_merge_singularity_args()`

## Rule execution pattern: run: + .sh script

ALL 175 rules use `run:` blocks (zero use `shell:` directive). 83 .smk files
generate `.sh` scripts containing bare commands (no env activations, no
`apptainer exec`). Environment isolation is handled entirely by snakemake's
`--sdm apptainer` or `--use-conda` at the rule level.

Pattern in .smk files:
```python
rule example:
    input: ...
    output: ...
    conda: "tool.yaml"
    container: sif("tool.yaml")
    run:
        cmd = ["python", params.script, "-arg", value, ...]
        script = os.path.join(outdir, f"sample_{timestamp}.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("set -euo pipefail\n")
            f.write(shlex.join(cmd) + "\n")
        shell(f"bash {script} >> {log_path} 2>&1")
```

The .sh scripts **cannot be executed independently** without manual environment
setup. This is by design -- snakemake wraps the entire rule execution in the
correct container/conda env.

## DAG and target control

### How outfiles defines the DAG boundary

Each subworkflow's `rule all` has `input: outfiles`, where `outfiles` is set
by `run<Workflow>()` in run.py. This means `outfiles` determines which jobs are
in the DAG:

- If a rule's output is a direct or transitive dependency of an entry in
  `outfiles`, it is in the DAG.
- If a rule's output is NOT reachable from `outfiles`, it is excluded from the
  DAG and will not run.

When no explicit target is given on the command line, snakemake defaults to
`rule all`, so the DAG is exactly what `outfiles` defines.

### Snakemake target mechanisms (CLI)

| Mechanism | Syntax | DAG effect |
|-----------|--------|------------|
| `--forcerun` | `--forcerun RULE:WILDCARD=VALUE` | Forces rerun of target. Downstream reruns IF their outputs need updating. |
| `--until` | `--until RULE` | Truncates DAG: runs everything up to and including this rule, skips downstream |
| `--target-jobs` | `--target-jobs RULE:WILDCARD=VALUE` | Internal API use; same as positional target. Not for CLI use. |
| Positional target | `RULE:WILDCARD=VALUE` | Treated as FILE PATH by snakemake, not rule name. Raises MissingRuleException for rule names. |

Key distinction:
- **`--forcerun`** forces the target to rerun. Downstream jobs are NOT forced
  but MAY rerun if their outputs need updating (per rerun-triggers).
- **`--until`** truncates the DAG so downstream isn't in the graph at all.
- **Positional targets** are treated as file paths, NOT rule names. This is
  a critical pitfall -- see below.

### Forcerun and outfiles interaction

`--forcerun` only works on jobs that are already in the DAG (i.e., reachable
from `outfiles` via `rule all`). If a rule's output is not in the `outfiles`
dependency chain, `--forcerun` cannot trigger it. In practice, all pipeline
intermediate steps (cutadapt, alignment, quantification, etc.) are upstream of
`outfiles`, so `--forcerun` works correctly for rerunning specific samples/steps.

### Forcerun and downstream rerun

When `--forcerun RULE:WILDCARD=VALUE` is used alone:
- The matched job is force-rerun regardless of whether its output exists.
- Upstream dependencies are rerun if needed (determined by rerun-triggers).
- Downstream jobs that depend on the force-rerun output MAY also rerun if
  their outputs need updating (per rerun-triggers). This is usually NOT desired.

To prevent downstream rerun, run.py combines `--until` + `--forcerun` with
the same targets. `--until` removes downstream from the DAG entirely, so
`--forcerun` only affects the target + its upstream dependencies.

### Forcerun: first-class run.py argument

`--forcerun` is a first-class run.py argument (not passed via --snakemake-args).

**Auto-prefixing:** Subworkflows rename rules via `use rule ... as <wf>_...`.
run.py auto-prefixes forcerun targets with the workflow name so users write
the original module rule name. For targets with wildcards
(`RULE:WILDCARD=VALUE`), only the rule part (before `:`) is prefixed.
Already-prefixed names and `all` pass through unchanged.

```python
# In execute_workflows(), before build_snakemake_cmd():
if ":" in t:
    rule_part, rest = t.split(":", 1)
    rest = ":" + rest
else:
    rule_part, rest = t, ""
if rule_part == "all" or rule_part.startswith(f"{wf_name}_"):
    pass  # already correct
else:
    t = f"{wf_name}_{rule_part}{rest}"
```

**DAG semantics -- --until + --forcerun combination:**

`--forcerun` alone forces the target to rerun AND triggers downstream reruns
if their outputs need updating. To rerun ONLY the target without downstream,
run.py emits BOTH `--until` and `--forcerun` with the same targets:

```python
# In build_snakemake_cmd():
if forcerun:
    cmd.append("--until")
    cmd.extend(forcerun)
    cmd.append("--forcerun")
    cmd.extend(forcerun)
```

`--until` truncates the DAG so downstream jobs aren't in the graph at all.
`--forcerun` then forces the target within that truncated DAG.

**Pitfall: positional targets don't work for rule names.** Snakemake treats
bare positional targets as file paths. `function_gsea` as a positional target
raises `MissingRuleException` (it looks for a file named `function_gsea`).
Always use `--forcerun` which accepts rule names directly.

### Choosing the right mechanism

| Use case | Mechanism |
|----------|-----------|
| Rerun a specific sample's step (no downstream) | `--forcerun trimming_Paired:sample_id=S1` |
| Rerun a rule without wildcards | `--forcerun function_gsea` |
| Multiple targets | `--forcerun r1:w1=v1 r2:w2=v2` |
| Run pipeline up to a certain step, skip rest | `--snakemake-args --until DESeq2_TEcount` |
| Rerun entire pipeline from scratch | `--forcerun all` or delete output + rerun |

## run.py CLI reference

### Core arguments

| Arg | Type | Description |
|-----|------|-------------|
| `-m` / `--meta` | str | Meta input file or fastq directory |
| `-w` / `--workflow_name` | str+ | Workflow name(s), supports parallel execution |
| `-o` / `--output_dir` | str | Output directory |
| `-t` / `--threads` | int | Total threads (split across parallel workflows) |
| `--dry-run` | flag | Dry run |
| `--test` | str? | Test mode: run dry-run for a workflow or "all" |
| `--log` | str | Log file path |
| `--forcerun` | str+ | Force rerun specific jobs (auto-prefixed with workflow name). See below. |

### Environment backend

| Arg | Type | Description |
|-----|------|-------------|
| `--sdm` | flag | Use apptainer container backend (SIF images) |
| `--conda-prefix` | str | Conda prefix (required when NOT using --sdm) |
| `--conda-frontend` | str | conda or mamba (default: mamba) |
| `--singularity-args` | str | Extra singularity/apptainer args (e.g., --bind) |
| `--rerun-trigger` | str+ | Snakemake rerun-triggers |

### Config override (dot notation)

Unknown `--` args are collected as config overrides:
- `--key value` -> `config["key"] = value`
- `--key v1 v2 v3` -> `config["key"] = [v1, v2, v3]`
- `--key=value` -> `config["key"] = value`
- `--Params.cutadapt.quality 20` -> `config["Params"]["cutadapt"]["quality"] = 20`

Types are auto-cast: "true"/"false" -> bool, "20" -> int, "1.5" -> float.

### Snakemake passthrough

`--snakemake-args REMAINDER` forwards all remaining args to snakemake. This
conflicts with positional targets (see pitfall below).

## Pitfalls

### --snakemake-args REMAINDER vs positional targets

`--snakemake-args` uses `argparse.REMAINDER`, which consumes ALL subsequent
arguments. For target control, use the first-class `--forcerun` argument
instead of `--snakemake-args --forcerun ...`. The `--forcerun` argument is
parsed before the extra_args loop, so it won't be swallowed.

### Extra args parsing swallows bare targets

The extra_args parsing loop (lines 811-831 in run.py) collects all non-`--`
tokens after an unknown `--key` as its values. So:

```
--Params.cutadapt.quality 20 trimming_Paired:sample_id=S1
```

Both `20` AND `trimming_Paired:sample_id=S1` get swallowed as values for
`Params.cutadapt.quality`. The target is lost. The `--forcerun` first-class
argument avoids this because it's a registered argparse argument, so it's
parsed before the extra_args loop sees it.

### Positional targets are file paths, not rule names (critical pitfall)

Snakemake treats bare positional targets as FILE PATHS. Passing
`function_gsea` as a positional target raises `MissingRuleException` because
snakemake looks for a file named `function_gsea`. This is true even with
`--force` flag. Always use `--forcerun` which accepts rule names.

### --target-jobs is internal-only

Snakemake marks `--target-jobs` as "Internal use only". It works from CLI but
is intended for programmatic API use. Use `--forcerun` instead.
