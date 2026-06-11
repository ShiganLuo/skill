# Snakemake Omics Workflow — Full Implementation Detail

## Module .smk Template

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

## Module .json Template

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

## Module .yaml Template

```yaml
name: <tool>
channels:
  - bioconda
  - conda-forge
  - defaults
dependencies:
  - <tool>>=<version>
```

## Subdirectory Module Pattern

For sub-tools with shared conda env:

```
modules/<tool>/
  <tool>.yaml           # Shared conda env
  <tool>.smk
  <tool>.json
  <subtool>/
    <subtool>.smk       # conda: "../<tool>.yaml"
    <subtool>.json
```

## Subworkflow Template

```python
shell.prefix("set -x; set -e;")
from snakemake.logging import logger

indir = config.get("indir", "data/fastq")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "logs")
outfiles = config.get("outfiles", [])
samples = config.get("samples", [])

rule all:
    input: outfiles

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

## run.py Integration

### Function Signature

```python
def run<Workflow>(
    datajson: Dict[str, Any],
    samples_info_dict: Dict[str, Any],
    indir: str,
    outdir: str,
):
```

### Inside run<Workflow>()

1. Set `datajson["ROOT_DIR"]`, `indir`, `outdir`, `logdir`
2. Build `outfiles` list by iterating `samples_info_dict`
3. Set `datajson["samples"]`, `datajson["outfiles"]`
4. Write `raw.json` to outdir

### Wiring into Main Block

```python
# In parse_args():
parser.add_argument('-w', '--workflow_name', type=str,
    choices=["...", "<Workflow>"], ...)

# In __main__:
elif args.workflow_name == "<Workflow>":
    input_json = run<Workflow>(deepcopy(workflow_config), samples_info_dict, raw_fastq_dir, abs_outdir)
    smk = "<Workflow>.smk"
```

## Aggregation Report Rules

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
        cmd = ["python", params.script,
               "-p", ",".join(input.passed),
               "-d", ",".join(input.discarded),
               "-o", outdir + "/<tool>_report"]
        shell(" ".join(cmd) + " > {log} 2>&1")
```

## Nextflow-to-Snakemake Porting

1. Read main workflow (`workflows/<name>.nf`) for the DAG
2. Read subworkflows (`subworkflows/local/*/main.nf`) for step sequences
3. Map operators:
   - `process` → `rule` in module .smk
   - `workflow` → subworkflow .smk
   - `Channel.join()` → rule input dependencies
   - `if (params.X)` → `if not config.get("Params", {}).get("skip_X")`
4. Map modules (`modules/nf-core/*/main.nf`) → Snakemake modules
5. Preserve step order: align → sort → index → call → phase → etc.

## Pitfalls

1. Don't use `execute_code` with triple-quoted Snakemake syntax — use `write_file` directly
2. Patch insertion position: verify with `read_file` + `py_compile` after patching
3. Subdirectory rules: `conda: "../<parent>.yaml"` (not full path)
4. Rule name conflicts when importing same module twice — use distinct aliases
5. `outfiles` paths must exactly match rule outputs
6. Workflows without design pairs don't need `designPair` parameter
