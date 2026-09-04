# Omics Execution Architecture & Single-Step Execution

## run.py: The Sole Entry Point

`workflow/Omics/run.py` is the only correct way to launch Omics workflows.
Never call `snakemake` directly -- run.py builds the command with correct
config, bind paths, and environment backend.

### Execution flow

```
parse_args() → setup_test_args() or setup_normal_args()
    → execute_workflows()
        → for each workflow:
            1. MetadataUtils.run() → samples_info_dict, sample_pairs, group_pairs
            2. _load_model_json(config/<wf>.json) → workflow_config
            3. WORKFLOW_DISPATCH[wf] → (smk_filename, raw.json path)
            4. run<wf>() populates datajson, writes raw.json
            5. build_snakemake_cmd() → cmd list
            6. _run_cmd(cmd) or _run_cmds_parallel() for multi-workflow
```

### WORKFLOW_DISPATCH

Maps workflow name → (subworkflow .smk, run function). Every workflow must
be registered here:

```python
WORKFLOW_DISPATCH = {
    "RNAseq": lambda cfg, sid, sp, gp, indir, outdir, meta: (
        "RNAseq.smk", runRNAseq(cfg, sid, gp, indir, outdir)
    ),
    ...
}
```

### build_snakemake_cmd()

Constructs the snakemake CLI invocation. Two environment backends:

**Conda backend** (default, `--use-conda`):
```python
cmd = [
    "snakemake", "-s", f"{root_dir}/subworkflow/{smk}",
    "--configfile", input_json,
    "--cores", str(threads),
    "--rerun-triggers", *rerun_trigger,
    "--conda-prefix", conda_prefix,
    "--use-conda",
    "--conda-frontend", conda_frontend,  # "mamba" or "conda"
]
```

**Apptainer/SIF backend** (`--sdm apptainer`):
```python
cmd = [
    "snakemake", "-s", f"{root_dir}/subworkflow/{smk}",
    "--configfile", input_json,
    "--cores", str(threads),
    "--rerun-triggers", *rerun_trigger,
    "--sdm", "apptainer",
    "--singularity-args", "--bind <auto-collected-paths>",
]
```

When `--sdm apptainer` is set, `--use-conda` is omitted entirely. Snakemake
uses the `container:` directive in each rule to select the SIF image.

### Bind path auto-collection

`_collect_bind_paths(input_json)` recursively scans all string values in the
config JSON. Strings containing `/` are treated as paths. Files yield their
parent directory; directories are kept as-is. Subdirectories are collapsed
into parents. `/tmp` is always added. User-provided `--singularity-args`
`--bind` paths are merged with auto-collected paths.

## Rule execution pattern: run: + .sh script

ALL 175 rules across the project use `run:` blocks (zero use `shell:`
directive). Of these, 83 .smk files generate `.sh` scripts:

```python
rule example:
    ...
    conda: "tool.yaml"
    container: sif("tool.yaml")
    run:
        cmd = ["python", script_path, "--arg", value]
        script = os.path.join(outdir, f"tool_{timestamp}.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("set -euo pipefail\n")
            f.write(shlex.join(cmd) + "\n")
        shell(f"bash {script} >> {log_path} 2>&1")
```

The .sh scripts contain **bare commands** -- no `conda activate`, no
`apptainer exec`. Environment isolation is handled entirely by snakemake's
`--sdm apptainer` or `--use-conda` at the rule level. The .sh scripts
**cannot be executed independently** without manual environment setup.

## sif() resolution (common.smk)

The `sif()` function in `modules/common/common.smk` resolves SIF paths:

1. Explicit mapping: `config["env"][<yaml_stem>]` → absolute SIF path
2. Fallback: `config["env"]["env_dir"] / <module_dir> / <yaml_stem>.sif`

Config JSON `env` section example:
```json
"env": {
    "env_dir": "/home/luosg/Database/env",
    "star": "/home/luosg/Database/env/star/star.sif",
    "cutadapt": "/home/luosg/Database/env/cutadapt/cutadapt.sif"
}
```

## Single-step execution: snakemake --until (recommended)

### The problem

run.py runs the full DAG (all targets in `rule all`). Users sometimes need
to run only one step (e.g., just cutadapt, just alignment).

### Option A: snakemake --until (RECOMMENDED)

Forward `--until` to snakemake via `--snakemake-args`:

```bash
python run.py -m meta.tsv -w RNAseq -o output -t 10 \
    --sdm apptainer \
    --snakemake-args --until trimming_Paired
```

Or add a convenience `--until` arg to run.py that forwards to snakemake.

Advantages:
- **Minimal change**: run.py adds one argparse param, or zero changes (use
  `--snakemake-args`). All .smk files unchanged.
- **Correct dependencies**: snakemake resolves the DAG; if the step's inputs
  don't exist, upstream rules run automatically.
- **Consistent path**: Same execution mechanism whether full or partial run.
  .sh script content is identical.
- **Environment handled**: `--sdm apptainer` / `--use-conda` applies to
  each rule automatically.

### Option B: Embed apptainer exec in .sh scripts (NOT recommended)

Would require changing 83 .smk files to wrap commands with
`apptainer exec <sif> bash {script}`.

Disadvantages:
- Massive change surface (83 files, non-uniform .sh generation patterns)
- .sh content differs between snakemake-run and standalone-run (snakemake
  already wraps in container; double-wrapping if both active)
- SIF path hardcoded in .sh, breaks portability
- No dependency resolution (input missing = crash, not auto-upstream)
- Two execution paths to maintain

### Design decision

Always prefer Option A. The .sh scripts are an implementation detail of the
`run:` block, not a standalone execution format. Environment isolation is
snakemake's job, not the script's.

## run.py CLI reference

```
python run.py \
    -m <meta.tsv or fastq_dir> \
    -w <workflow_name> [workflow_name2 ...] \
    -o <output_dir> \
    -t <threads> \
    [--dry-run] \
    [--test [WORKFLOW|all]] \
    [--conda-prefix <dir>] \          # required when NOT using --sdm
    [--sdm apptainer] \               # use SIF containers
    [--singularity-args '--bind /path'] \
    [--rerun-trigger code input mtime params software-env] \
    [--conda-frontend mamba|conda] \
    [--snakemake-args <extra snakemake args>] \
    [--key.value extra_config=value]  # dotted notation for config overrides
```

Key behaviors:
- Multiple `-w` workflows run in parallel (threads split evenly)
- `--test` auto-discovers meta files from `assests/test/meta_<wf>.tsv`
- `--test` implies `--dry-run` and auto-creates test paths via SchemaValidator
- Extra `--key=value` args override config via dotted notation (e.g. `--genome.fasta=/path`)
