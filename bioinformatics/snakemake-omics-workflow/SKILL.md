---
name: snakemake-omics-workflow
description: Add new modules, subworkflows, and pipelines to the Omics Snakemake project — including porting from Nextflow
---

# When to use

- User asks to implement a new workflow/pipeline in the Omics Snakemake project
- User asks to port a Nextflow (nf-core) pipeline to Snakemake
- User asks to add a new tool module to `workflow/Omics/modules/`
- User asks to create a new subworkflow in `workflow/Omics/subworkflow/`

# Prerequisites — read these first

Before writing any code, load and read these project files:

1. `skill.md` — project overview, run.py responsibilities, extension checklist
2. `subworkflow/subworkflow.md` — subworkflow conventions (module + use rule pattern, config dict naming)
3. `modules/modules.md` — module conventions (3-file structure, config dict, rule naming)

These are project-local markdown files, not Hermes skills. Read them with `read_file`.

# Extension checklist (from skill.md)

When adding a new workflow:

1. Add model template JSON in `config/<WorkflowName>.json`
2. Add `run<WorkflowName>()` function in `run.py`
3. Add workflow name to `--workflow_name` choices in `parse_args()`
4. Add elif branch in `__main__` block to call `run<WorkflowName>()`
5. Create subworkflow snakefile in `subworkflow/<WorkflowName>.smk`
6. Create required modules in `modules/<tool>/`

# Module 3-file pattern

Every module directory needs:

```
modules/<tool>/
  <tool>.smk    # Snakemake rules
  <tool>.json   # Config template (default values)
  <tool>.yaml   # Conda environment spec
```

For sub-tools with shared conda env, use subdirectories:

```
modules/<tool>/
  <tool>.yaml           # Shared conda env
  <tool>.smk            # Main rules
  <tool>.json
  <subtool>/
    <subtool>.smk       # Sub-tool rules, conda: "../<tool>.yaml"
    <subtool>.json
```

## Module .smk template

```python
from snakemake.logging import logger
indir = config.get("indir", "input")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")

rule <tool>_<action>:
    input:
        infile = indir + "/{sample_id}/{sample_id}.<ext>"
    output:
        outfile = outdir + "/{sample_id}/{sample_id}.<ext>"
    log:
        logdir + "/{sample_id}/<tool>_<action>.log"
    threads: 4
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>"
    shell:
        """
        mkdir -p $(dirname {output.outfile})
        {params.tool} ... > {log} 2>&1
        """
```

## Module .json template

```json
{
    "indir": "input",
    "outdir": "output",
    "logdir": "logs",
    "samples": [],
    "Procedure": {
        "<tool>": null
    },
    "genome": {
        "fasta": null
    }
}
```

## Module .yaml template

```yaml
name: <tool>
channels:
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - <tool>>=<version>
```

# Subworkflow pattern

```python
shell.prefix("set -x; set -e;")
from snakemake.logging import logger

indir = config.get("indir", "data/fastq")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "logs")
outfiles = config.get("outfiles", [])
samples = config.get("samples", [])

rule all:
    input:
        outfiles

# Module config dict — name: <module>_config
tool_config = {
    "indir": indir,
    "outdir": f"{outdir}/<tool>",
    "logdir": logdir,
    "samples": samples,
    "Procedure": {
        "<tool>": config.get("Procedure", {}).get("<tool>")
    },
    "genome": {
        "fasta": config.get("genome", {}).get("fasta")
    }
}
module <tool>:
    snakefile: "../modules/<tool>/<tool>.smk"
    config: <tool>_config
logger.info(f"<tool>_config: {<tool>_config}")
use rule <rule_name> from <tool> as <Workflow>_<rule_name>
```

Key conventions:
- Config dict named `<tool>_config`
- Rule aliasing: `use rule X from Y as <Workflow>_X`
- Conditional modules: wrap in `if not skip_<X>:` blocks
- Chain outputs: module B's `indir` = module A's `outdir`

# run.py integration

## run<Workflow>() function signature

```python
def run<Workflow>(
    datajson: Dict[str, Any],
    samples_info_dict: Dict[str, Any],
    indir: str,
    outdir: str,
):
```

Note: workflows without design pairs (like PacVar for PacBio) don't need `designPair` parameter. Only Mutation-style workflows need it.

## Inside run<Workflow>()

1. Set `datajson["ROOT_DIR"]`, `indir`, `outdir`, `logdir`
2. Build `outfiles` list by iterating `samples_info_dict`
3. Set `datajson["samples"]`, `datajson["outfiles"]`
4. Write `raw.json` to outdir

## Wiring into main block

```python
# In parse_args():
parser.add_argument('-w', '--workflow_name', type=str,
    choices=["...", "<Workflow>"], ...)

# In __main__:
elif args.workflow_name == "<Workflow>":
    input_json = run<Workflow>(deepcopy(workflow_config), samples_info_dict, raw_fastq_dir, abs_outdir)
    smk = "<Workflow>.smk"
```

# Nextflow-to-Snakemake porting pattern

When porting an nf-core Nextflow pipeline:

1. **Read the main workflow** (`workflows/<name>.nf`) to understand the DAG
2. **Read each subworkflow** (`subworkflows/local/*/main.nf`) for step sequences
3. **Map Nextflow operators to Snakemake**:
   - `process` → `rule` in a module .smk
   - `workflow` → subworkflow .smk
   - `Channel.join()` → Snakemake rule input dependencies
   - `Channel.combine()` → may need separate rules or config
   - `if (params.X)` → `if not config.get("Params", {}).get("skip_X")`
4. **Map Nextflow modules** (`modules/nf-core/*/main.nf`) → Snakemake modules
5. **Preserve the step order**: align → sort → index → call → phase → etc.

# Pitfalls

## 1. execute_code with Snakemake content

Do NOT use `execute_code` with triple-quoted strings containing Snakemake syntax — the shell backslash escapes and nested quotes cause SyntaxError. Use `write_file` tool directly for each file.

## 2. Patch insertion position

When inserting a new function before an existing one in run.py via `patch`, be precise about the context. A bad `old_string` match can corrupt the file. Always verify with `read_file` after patching, and compile-check with:
```bash
python -c "import py_compile; py_compile.compile('run.py', doraise=True)"
```

## 3. Module conda env path in subdirectories

Subdirectory rules must use `conda: "../<parent>.yaml"` (relative path to parent's yaml), not `"../modules/<tool>/<tool>.yaml"`.

## 4. Rule name conflicts

When importing the same module twice (e.g., hiphase for SNP and SV), use distinct aliases:
```python
module hiphase_snp:
    snakefile: "../modules/hiphase/hiphase.smk"
    config: hiphase_snp_config
module hiphase_sv:
    snakefile: "../modules/hiphase/hiphase.smk"
    config: hiphase_sv_config
use rule hiphase_phase from hiphase_snp as PacVar_hiphase_snp
use rule hiphase_phase from hiphase_sv as PacVar_hiphase_sv
```

## 5. outfiles path consistency

The `outfiles` in `run<Workflow>()` must exactly match the output paths in the rules. A mismatch causes Snakemake to fail silently or rebuild everything.

## 6. Aggregation report rules

When a module produces per-sample outputs that need a cross-sample summary, add an aggregation rule that collects all sample outputs and runs a summary script. The summary script should live in the module's `bin/` directory and accept explicit file paths (not directory scanning):

```python
rule <tool>_report:
    input:
        passed = expand(outdir + "/{sid}/{sid}_passed.tsv", sid=samples),
        discarded = expand(outdir + "/{sid}/{sid}_discarded.tsv", sid=samples),
    output:
        report = outdir + "/<tool>_report/per_sample_summary.tsv"
    params:
        script = os.path.join(ROOT_DIR, "modules/<tool>/bin/summarize.py")
    run:
        cmd = [
            "python", params.script,
            "-p", ",".join(input.passed),
            "-d", ",".join(input.discarded),
            "-o", outdir + "/<tool>_report",
        ]
        shell(" ".join(cmd) + " > {log} 2>&1")
```

Key points:
- The summary script uses `-p` (comma-separated passed files) and `-d` (discarded files), not `--indir`
- The script can ALSO support `--indir` as an alternative for standalone use (mutually exclusive argparse group)
- Output goes to a subdirectory (e.g. `<tool>_report/`) not a single flat file, since the script produces multiple outputs (TSV tables, HTML report, figures)
- The rule's `output` points to one representative file (e.g. `per_sample_summary.tsv`) for Snakemake dependency tracking
