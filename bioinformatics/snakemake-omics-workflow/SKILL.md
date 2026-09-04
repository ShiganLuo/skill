---
name: snakemake-omics-workflow
description: Add new modules, subworkflows, and pipelines to the Omics Snakemake project — including porting from Nextflow
---

# When to use

- New Omics workflow/pipeline/module/subworkflow work.

# Core workflow discipline

Trace the full DAG first. Keep modules atomic, subworkflows orchestration-only. For proteomics/DIA work, treat vendor `.raw` ingestion as a front-end conversion problem: add a thin `raw2mzml` module and keep `QuantMS` on mzML. Use a manifest keyed by `sample_id` + `raw_path` + assay metadata, then pass `raw_files`/`mzml_files` through `node.runQuantMS()`. Design principle: YAML filename stem for lookups, NOT file content parsing. the `name:` field inside the YAML (user corrected: avoid unnecessary I/O). When stem != SIF name, user adds explicit config mapping.

For vendor `.raw` proteomics ingress, see `references/proteomics-raw2mzml.md`. For QuantMS `MissingInputException` / path-contract debugging, see `references/quantms-dag-path-contracts.md`. For SIF container build failures (conda PATH leakage, plugin errors, solver issues, openms vs openms-thirdparty), see `references/apptainer-sif-build-pitfalls.md`. For `use rule` pitfalls (variable scoping, empty input, argparse), see `references/use-rule-pitfalls.md`. For dual-mode rules (resource-based vs download-based index building), see `references/dual-mode-rules.md`. For OpenMS module consolidation (shared SIF for identical-env modules), see `references/openms-module-consolidation.md`.
- **Subworkflows only orchestrate.** A `subworkflow/<workflow>.smk` may construct `*_config` dictionaries, declare `module`, expose rules with `use rule`, select optional branches, derive `outfiles`, and define `rule all`. It must not contain executable analysis rules.
- **Extend the correct parent module.** If an existing tool module is close but has incompatible semantics, add a focused submodule under that tool (for example, `modules/gatk/gatk_population/` sharing `../gatk.yaml`) rather than bypassing the module layer with direct rules.
- **Package every new module.** Add the `.smk`, `.json`, and `.yaml` files unless it is a documented child module sharing its parent's environment.
- **Use the canonical `run:` body visibly in each rule.** Preserve log clearing, `setup_logger`, timestamped script names, list-based command construction, conditional `cmd += [...]`, `try/except`, and re-raise. Do not hide these project conventions behind a generic helper merely to shorten the file.
- **Verify architecture as well as syntax.** A focused check should assert that the subworkflow has only `rule all`, implementation rules live in atomic modules, old mega-modules are absent, and a fully enabled optional-feature DAG dry-runs successfully.

See `references/population-pipeline-module-boundaries.md` for a concrete multi-tool population-genomics decomposition and the GATK joint-genotyping compatibility check.

In this Omics repository, put executable `rule` definitions in `modules/<module>/`.
A `subworkflow/<workflow>.smk` should only assemble the module configuration,
declare the `module` path, expose rules with `use rule`, and define `rule all`.
Do not implement analysis rules directly in a subworkflow. This separation is
important for reuse, namespacing, and consistent module testing.

When a workflow needs a behavior that an existing module cannot provide, add a
new rule to the appropriate module rather than duplicating it in the
subworkflow. For example, population joint genotyping needs per-sample
`HaplotypeCaller -ERC GVCF`, `GenomicsDBImport`, and `GenotypeGVCFs`; an
existing per-sample filtered-VCF germline module cannot be reused unchanged.

## Project-specific execution style: `run:` is mandatory

Read `references/atomic-module-and-verification.md` before implementation; it is the compact checklist for atomic module boundaries, full config flow, standard `run:`, optional output wiring, and fresh verification.

For this Omics repository, executable rules in new or modified modules/subworkflows must use `run:` blocks, not top-level `shell:` blocks. Within `run:`:

1. Build the command with the available `params`, `input`, `output`, and `threads` values.
2. Write a reproducible command script under the rule output/log area.
3. Execute it with `shell()` and redirect to the rule log.
4. Check expected outputs when the tool produces indexes or marker files.

Follow neighboring modules such as `gatk_prepare.smk` and `gatk_germline.smk`. Keep `ROOT_DIR` in every module config and include the common utilities when a standalone subworkflow needs `setup_logger` or shared imports.

### Joint germline calling is not the existing germline module

The existing `modules/gatk/gatk_germline/gatk_germline.smk` emits per-sample filtered VCFs and does not use `-ERC GVCF`; it is therefore not a drop-in implementation for population-genomics joint genotyping. For a population workflow, implement or reuse a compatible chain:

`HaplotypeCaller -ERC GVCF → GenomicsDBImport → GenotypeGVCFs → population-level filtering`.

Reuse the existing GATK environment and preparation modules where their input/output contracts match, but do not force the per-sample germline module into a joint-calling DAG merely to claim module reuse.

### Verification gate for new subworkflows

When Snakemake is available, run a dry-run against temporary placeholder BAM/reference/index files and a minimal config containing at least two populations. Also inspect the generated DAG/shell rendering for unresolved inline Python expressions. If the repository has no canonical test, create a temporary `/tmp/hermes-verify-*` probe, clean it up, and report it as ad-hoc verification rather than suite green.
2. **Never modify a running process's files** — changes won't take effect until restart. Read the error, understand it, then propose the fix for the next run. See pitfall #20.
3. **Get approval before major structural changes** — removing `conda:`, changing `run:` to `shell:`, or restructuring a module should be discussed, not done silently. See pitfall #19.
4. **Read the CORRECT log** — snakemake execution log at `.snakemake/log/`, not just the application log. See pitfall #22.
5. **Match log timestamps to process start time** — old errors from previous runs are noise. See pitfall #23.

# Prerequisites — read these first

Before writing any code, load and read these project files:

1. `skill.md` — project overview, run.py responsibilities, extension checklist
2. `subworkflow/subworkflow.md` — subworkflow conventions (module + use rule pattern, config dict naming)
3. `modules/modules.md` — module conventions (3-file structure, config dict, rule naming)

These are project-local markdown files, not Hermes skills. Read them with `read_file`.

For ChIP-seq specific patterns (peaks_indir, nested Procedure config, FRiP): see `references/chipseq-module-patterns.md`.
For ChIP-seq QC report PPT generation (data collection, 9-slide structure, pptxgenjs): see `references/chipseq-report-pptx.md`.
For Python-based report module (python-pptx + matplotlib, modular bin/ scripts): see `references/chipseq-report-python.md`.
For RNA-seq FASTQ integrity debugging (empty reads, STAR read-input failures, cutadapt minimum_length): see `references/rna-seq-fastq-integrity.md`.
For serving IGV track HTML via nginx (internal IP access, URL mapping): see `references/nginx-igv-serving.md`.
For IGV track module modes (single vs iCLIP, auto-grouping): see `references/igv-track-modes.md`.

For ncRNAseq small RNA three-pass STAR alignment (canonical gene extraction, multi-pass re-alignment): see `references/ncrna-three-pass-star.md`.
For SRA data download scripts (ascp vs prefetch, meta file format, run.sh integration): see `references/sra-download-scripts.md`.

For comparison-group semantics and `design` reuse (group-style vs ctr/exp-style workflows, many-to-many grouping, compatibility derivatives): see `references/comparison-groups.md`.
For converting legacy `shell:` rules to `run:` blocks (batch migration checklist, pitfalls, verification): see `references/shell-to-run-conversion.md`.
For config schema validation and test path generation via SchemaValidator: see `references/schema-validator.md`.
For metadata grouping vs comparison design semantics (`group` vs `design`), see `references/meta-group-design-separation.md`.
For conda channel-resolution / strict-priority triage and STAR FASTQ sanity checks: see `references/conda-triage-and-fastq-qc.md`.
For standalone helper-script pitfalls (argparse vs snakemake.config, proper re-raise): see `references/deseq2-helper-script-and-index-exception.md`. For Cell Ranger scRNAseq module (ref + count + h5ad) and sed-escaping-in-bash pitfall: see `references/cellranger-scrnaseq-module.md`.

# Extension checklist (from skill.md)

When adding a new workflow:

1. Add model template JSON in `config/<WorkflowName>.json` — must cover ALL keys the .smk reads via `config.get()`. An empty `.json` file is NOT acceptable.
2. Add `run<WorkflowName>()` function in `run.py` — sets ROOT_DIR, indir, outdir, logdir, builds outfiles, writes raw.json.
3. Add workflow name to `--workflow_name` choices in `parse_args()`.
4. Add entry in `WORKFLOW_DISPATCH` dict: `"<Name>": lambda cfg, sid, dp, indir, outdir, meta: ("<Name>.smk", run<Name>(cfg, sid, indir, outdir))`.
5. Create subworkflow snakefile in `subworkflow/<WorkflowName>.smk`.
6. Create required modules in `modules/<tool>/`.

# New module checklist (create ALL 3 files together, never piecemeal)

When creating a new module, produce all files in one pass:
- [ ] `modules/<tool>/<tool>.smk` — rules
- [ ] `modules/<tool>/<tool>.json` — config template with EVERY key the .smk reads via `config.get()`
- [ ] `modules/<tool>/<tool>.yaml` — conda env

Verify: `ls modules/<tool>/` must show exactly 3 files. If .json is missing, the module is incomplete.

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

## Module .smk template — unified run: block style

ALL rules use `run:` blocks. Pure `shell:` blocks are NOT allowed. See `modules/modules.md` for the authoritative spec.

`conda:` + `run:` can coexist. Always include `conda:`.

```python
include: "../common/common.smk"
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
indir = config.get("indir", "input")

rule <tool>_<action>:
    input:
        bam = indir + "/{sample_id}/{sample_id}.bam"
    output:
        result = outdir + "/{sample_id}/{sample_id}_<result>.txt"
    log:
        logdir + "/{sample_id}/<tool>_<action>.log"
    threads: N
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>"
    run:
        log_path = str(log)
        try:
            open(log_path, "w").close()
            logger = setup_logger(logger_name="<tool>_<action>", log_file=log_path)
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            logger.info(f"Start <tool> <action> for sample {wildcards.sample_id} at {current_time}")
            script = os.path.join(outdir, f"{wildcards.sample_id}/<tool>_<action>_{current_time}.sh")
            cmd = [
                params.tool, "<action>",
                ...
            ]
            with open(script, "w") as f:
                f.write(" ".join(cmd) + "\n")
            shell(f"bash {script} >> {log_path} 2>&1")
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"<tool> <action> failed for sample {wildcards.sample_id} with error: {e}\n")
            logger.error(f"<tool> <action> failed for sample {wildcards.sample_id} with error: {e}")
            raise e
        finally:
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            logger.info(f"successfully activated <rule> for sample {wildcards.sample_id} at {current_time}")
```

Key points:
- `log_path = str(log)` — NOT `log[0]` or `str(log[0])`
- `include: "../common/common.smk"` imports `setup_logger`, `time`, `os`, `ROOT_DIR`
- `open(log_path, "w").close()` clears stale log before starting
- `cmd` list builds parameters, conditional args via `if`
- `shell(f"bash {script} >> {log_path} 2>&1")` — append stdout+stderr to log
- `try/except/finally` — always log completion in finally block

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
  - conda-forge
  - bioconda
  - defaults
dependencies:
  - <tool>>=<version>
```

> **Channel order matters**: `conda-forge` MUST come before `bioconda`. bioconda depends on conda-forge packages; reversing the order causes dependency resolution failures.

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

## CLI dot-notation for nested config overrides

`run.py` supports overriding any nested config key from the command line using dot notation. Unknown `--key` args are parsed by `parse_dot_args()` which splits on `.` and calls `dict_set_by_path()` to set the value in the workflow config dict.

**Syntax:**
```bash
# Boolean flag (no value → True)
--Params.macs3.cutoff_analysis

# Key=value
--Params.macs3.pvalue=1e-5
--Params.macs3.genome_size mm

# Top-level flat key
--genome_size mm
```

**How it works internally:**
1. `parse_known_args()` collects unknown `--key` args into `extra_args` dict
2. `parse_dot_args(extra_args)` extracts keys with `.` → `{("Params","macs3","pvalue"): "1e-5"}`
3. `dict_set_by_path(workflow_config, ["Params","macs3","pvalue"], "1e-5")` sets nested value
4. Flat args (no `.`) are merged via `workflow_config.update(flat_args)`

**Pitfall — string values:** Without `--no-schema-validate`, `cast_extra_args()` auto-casts values per schema type. `smart_cast()` lives in `SchemaValidatorUtil.py`.

**Use case:** Override workflow config without editing JSON files:
```bash
python run.py -m meta.tsv -w PeakCalling -o output \
    --Params.macs3.pvalue=1e-5 \
    --Params.macs3.cutoff_analysis \
    --Params.bamCoverage.binSize=25
```

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

## i18n (Chinese/English) Support

The report script supports `--lang zh` (default) or `--lang en` for PPT text. Matplotlib chart titles are always in English for font compatibility.

**Pattern:** Define an `I18N` dict with all user-facing strings keyed by language code. A `t(key, lang)` helper returns the translated string. All slide builders accept `lang` parameter.

```python
I18N = {
    "zh": {
        "report_title": "ChIP-seq Peak Calling 分析报告",
        "workflow_title": "分析流程概览",
        "alignment_title": "Bowtie2 比对统计",
        "summary_title": "总结与 QC 评估",
        "conclusions": "结论",
        # ... all strings
    },
    "en": {
        "report_title": "ChIP-seq Peak Calling Report",
        "workflow_title": "Workflow Overview",
        # ...
    },
}
def t(key, lang="zh"):
    return I18N.get(lang, I18N["zh"]).get(key, key)
```

The `--lang` parameter is passed through the Snakemake config:
```json
{"Params": {"report": {"lang": "zh"}}}
```

## Image Aspect Ratio Preservation

`add_picture()` with both width AND height distorts images. Use `_add_picture()` helper with PIL:

def _add_picture(slide, img_path, left, top, max_width, max_height):
    """Add picture preserving aspect ratio. Returns actual height used."""
    from PIL import Image as PILImage
    img = PILImage.open(img_path)
    img_w, img_h = img.size
    aspect = img_w / img_h
    w = max_width; h = w / aspect
    if h > max_height: h = max_height; w = h * aspect
    left_emu = left + (max_width - w) / 2
    slide.shapes.add_picture(img_path, Inches(left_emu), Inches(top), Inches(w), Inches(h))
    return h  # MUST return actual height for Layout tracking

All image slides use `_add_picture()` and update Layout with actual height:
```python
alloc = lay.allocate(img_h)
if alloc:
    actual_h = _add_picture(slide, img, MARGIN_L, alloc[0], CONTENT_W, alloc[1])
    lay.y = alloc[0] + actual_h  # snap to actual image bottom, not allocated max
lay.gap(0.05)
```
Without this, images shorter than `max_h` leave a large gap before the conclusion text.
Requires `pillow` in conda env.

## Additional Data Loaders

Beyond the core loaders, the report can also parse:
- `load_macs3_params(log_dir, sample)` — extract pvalue, bw, genome_size, fragment_length from `macs3.log`
- `load_peak_annotation_xlsx(path)` — optional openpyxl-based loader for `Peak_Annotation.xlsx` (Summary, Top30, Promoter_Peaks sheets)
- TSS distance distribution — parsed from `annotatePeaks.txt` column 10 (Distance to TSS), plotted as histogram

For cellranger_ref example (rule-only-validates pattern), see `references/cellranger-module-pattern.md`.

## Pitfalls

- **Wrong dirname depth**

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

## 8. Forgetting module .json config template

Every module MUST have a `.json` file. The .json defines the config template with default values — it's what `run.py` reads to build the workflow config dict. Without it, the module has no documented config contract.

After creating a module, grep the .smk for all `config.get("key"` calls and ensure each top-level key appears in the .json. Nested keys (e.g. `config.get("Procedure", {}).get("samtools")`) map to nested JSON objects.

If a module is meant to be reusable across workflows, keep the .json minimal but explicit: include every user-facing knob the .smk reads, and avoid relying on implicit defaults hidden in the workflow layer.

## 10. markdup vs dedup in ChIP-seq / ATAC-seq

**Use `gatk_prepare.smk`** for markdup — it already has `AddOrReplaceReadGroups` + `MarkDuplicates` (GATK4). Do NOT create a new markdup module from scratch. Do NOT use `samtools markdup` as a substitute.

- **markdup** (GATK MarkDuplicates via `gatk_prepare.smk`): adds read groups + flags duplicates, does NOT remove. MACS3 `--keep-dup auto` handles flagged dups correctly. Output: `.sorted_markdup.bam`
- **dedup** (samtools markdup -r in `igv.smk`): removes duplicates entirely. Use ONLY for visualization tracks (BigWig), NEVER for peak calling input. Output: `.dedup.bam`

Config pattern in subworkflow:
```python
gatk_prepare_config = {
    "indir": bowtie2_config["outdir"],
    "outdir": f"{outdir}/common/4_markdup_bam",
    "logdir": logdir,
    "input_bam_substring": "",
    "Procedure": {
        "gatk": config.get("Procedure", {}).get("gatk") or "gatk",
        "samtools": config.get("Procedure", {}).get("samtools") or "samtools"
    },
    "Params": {"gatk": config.get("Params", {}).get("gatk", {})},
    "addReadsGroup": config.get("addReadsGroup", {}),
    "genome": {"fasta": config.get("genome", {}).get("fasta")}
}
module gatk_prepare:
    snakefile: "../modules/gatk/gatk_prepare.smk"
    config: gatk_prepare_config
use rule addReadsGroup from gatk_prepare as <Workflow>_addReadsGroup
use rule MarkDuplicates from gatk_prepare as <Workflow>_MarkDuplicates
```

Downstream (macs3, frip_score) must reference `.sorted_markdup.bam` (not `.markdup.bam` or `.bam`).

See `references/chipseq-module-patterns.md` for the full ChIP-seq DAG.

## 11. Reuse before create — check existing modules first

Before creating a new module, scan `modules/` for existing modules that already implement the needed functionality (or a superset). The user will correct you if you create a redundant module.

This session: `modules/markdup/` was created from scratch, then the user said "直接使用gatk_prepare.smk" — the existing `gatk_prepare.smk` already had AddOrReplaceReadGroups + MarkDuplicates. Wasted effort.

Pattern: `search_files(target='files', path='workflow/Omics/modules', pattern='*')` first. Check if any existing module covers the same tool or step.

## 9. os.makedirs before writing scripts in run: blocks

When a `run:` block writes a shell script to a sample-specific directory, the directory may not exist yet (Snakemake only auto-creates the `output:` paths, not arbitrary working directories). Always `os.makedirs` before `open(script, "w")`:

```python
run:
    sample_outdir = os.path.join(outdir, wildcards.sample_id)
    os.makedirs(sample_outdir, exist_ok=True)       # <-- MUST have this
    script_path = os.path.join(sample_outdir, f"tool_{current_time}.sh")
    with open(script_path, "w") as f:
        f.write(f"#!/bin/bash\n{cmd}\n")
```

Without this, the rule fails with `[Errno 2] No such file or directory` when writing the script — a confusing error that looks like a missing input file.

## 12. Friendly ValueError for required config keys

At the top of each module `.smk`, validate required config values and raise `ValueError` with a clear message. This prevents Snakemake's cryptic `Input and output files have to be specified as strings` when a required path is `None`:

```python
fasta = config.get("genome", {}).get("fasta")
if not fasta:
    raise ValueError(
        "bowtie2 module requires 'genome.fasta' in config. "
        "Please provide a valid reference genome FASTA path."
    )
```

Apply this pattern for: `genome.fasta` (bowtie2, gatk_prepare), `genome.gtf` (homer), and any other path that Snakemake would try to use as an input file.

## 13. .smk files are not valid Python

Snakemake `.smk` files use DSL keywords (`rule`, `input:`, `output:`, `shell:`, `run:`, etc.) that are not valid Python syntax. Do NOT use `py_compile.compile()` or `ast.parse()` to validate them. Instead, verify by:
- Checking required content patterns exist (rule names, tool invocations, config access)
- Using `re.findall(r'^rule\\s+(\\\\w+):', content, re.MULTILINE)` to confirm rule definitions
- Running `snakemake --lint` or a dry-run when test data is available

**Structural verification script:** After refactoring a module, use `scripts/verify-smk-structure.py` to run automated checks. It verifies: rule names match consumers (`use rule X from <module>`), all rules use `run:` with `setup_logger`/`try:except`/`os.makedirs`/log-clear, no `conda:` + `run:` conflicts, input references are correct (e.g. no stale `input.plus_bw` when input declares `bigwigs`), .json covers all `config.get()` keys, 3-file structure intact. Usage: `python scripts/verify-smk-structure.py <path/to/module.smk> [expected_rule1,rule2,...]`

## 14. Common bugs when editing `run:` block cmd lists

When editing `run:` blocks that build shell command lists (`cmd = [...]`), watch for these frequent errors:

**Missing commas between list elements.** A missing comma between two string literals silently concatenates them in Python (`"a" "b"` → `"ab"`). Always verify each element (except the last) ends with `,`.

**Type mismatch: numeric params need `str()`.** Config values like `binSize` arrive as `int`. Passing them raw to `" ".join(cmd)` works but `"--binSize", 50` looks odd; more critically, some tools expect string args. Wrap: `str(params.binSize)`.

**Case sensitivity on params.** Snakemake `params:` are plain Python variables — `params.offset` and `params.Offset` are different. Always match the exact case from the `params:` declaration.

**Boolean param checked but not appended.** A subtle variant: the `if params.X:` branch contains a `rule_logger.info()` call describing the flag, but the actual `cmd.append("--X")` is missing. The code *looks* complete because the log message reads as if the action was taken. Always verify that every conditional branch that mentions a flag in its log message also appends it to `cmd`. Example bug (macs3 `cutoff_analysis`):

```python
# BUG: logs but doesn't append
if params.cutoff_analysis:
    rule_logger.info("use --cutoff-analysis ...")

# FIX: append the flag
if params.cutoff_analysis:
    rule_logger.info("use --cutoff-analysis ...")
    cmd.append("--cutoff-analysis")
```

**Flag-like params that may be bool OR int.** Some params (e.g. `extendReads`) can be `True` (flag-only), an integer value (flag + value), or `False`/`None` (omit). In Python, `bool` is a subclass of `int` — `isinstance(True, int)` returns `True`. So you MUST check `bool` BEFORE `int`:

```python
if isinstance(params.extendReads, bool):
    if params.extendReads:
        cmd += ["--extendReads"]
elif isinstance(params.extendReads, int) and params.extendReads > 0:
    cmd += ["--extendReads", str(params.extendReads)]
```

Never use a bare `if params.extendReads:` — this treats `200` the same as `True` (adds `--extendReads` without the value). And never `"--extendReads", params.extendReads` (this passes the literal string "False" or "True").

## 16. Check cross-references before modifying a module

## 16b. Logging calls are not `print()` — use f-strings or `%s` placeholders

When adding debug output in Python modules (especially `MetaUtil.py`, `run.py`, or helper scripts), do **not** write logging like:

```python
logger.info("group_pairs:", group_pairs)
logger.info("sample_pairs:", sample_pairs)
```

`logging` treats extra positional args as formatting arguments. Without `%s` placeholders, the message is not rendered the way you expect and may never appear in the log file.

Use one of these patterns instead:

```python
logger.info(f"group_pairs: {group_pairs}")
logger.info("group_pairs: %s", group_pairs)
logger.info(f"sample_pairs: {sample_pairs}")
logger.info("sample_pairs: %s", sample_pairs)
```

Rule of thumb:
- `print(a, b)` style is valid for `print`, not for `logger.info`
- In this project, prefer **f-strings** for logging to match user style
- If a function clearly executed but expected debug lines are absent from the log, inspect the logging call signature before assuming the code path was skipped


When modifying a module `.smk`, always check which subworkflows reference it via `use rule X from <module>`. Changes to rule names, input/output signatures, or param names will break those subworkflows.

```bash
# Find all subworkflows referencing a module
search_files(pattern="use rule.*from <module>", path="workflow/Omics/subworkflow", target="content")
search_files(pattern="<module>\.smk", path="workflow/Omics/subworkflow", target="content")
```

Safe changes (won't break references):
- Fixing syntax errors inside `run:` blocks
- Changing internal variable names
- Adding new rules not yet referenced

Breaking changes:
- Renaming rules
- Changing `input:`/`output:` path patterns
- Changing `params:` names (consumers may override them)

**Never leave a bare `raise e` after a `try/except` in a `run:` block.** If the intent is to rethrow, it must live inside the `except` branch. A common copy/paste bug is:

```python
try:
    ...
except Exception as e:
    logger.error(f"... {e}")
raise e   # BUG: executes even after success, and `e` may be undefined
```

Correct pattern:

```python
try:
    ...
except Exception as e:
    logger.error(f"... {e}")
    raise
```

Also avoid `logger.error(f.write(...))`; `f.write()` returns an integer byte count, not the message.

## 15. Terminal rules need `output` with `touch()`

Rules that serve as final targets (e.g. `igv_result`) often have only `input:` and no `output:`. This breaks Snakemake's DAG — the rule is treated as always needing re-run. Add a `touch()` output:
```python
rule igv_result:
    input:
        bigwig = outdir + "/{sample_id}/{sample_id}.bigwig"
    output:
        touch(outdir + "/{sample_id}/igv.done")
```
This creates a sentinel file that Snakemake uses for up-to-date checking.

## 17. Verify input/output path chains end-to-end

When modifying a module's input/output paths, trace the **full path chain** through all consumers — not just check that the rule names match. A rule can be referenced correctly but still fail if the path pattern doesn't match what the upstream producer actually outputs.

**Real-world example (igv → exomePeak chain):**
- `igv.smk` `samtools_dedup` outputs: `{outdir}/{sample_id}/{sample_id}.dedup.bam` (nested)
- `exomePeak.smk` expected: `{indir}/{sample_id}.dedup.bam` (flat — missing `/{sample_id}/` directory)
- `MERIP.smk` had: `"indir": igv_config["outdir"] + "/dedup"` (extra `/dedup` suffix that didn't exist)

**Verification procedure after modifying a module:**

1. Find all consumers: `search_files(pattern="use rule.*from <module>", target="content")`
2. For each consumer, trace the path chain:
   ```python
   # Producer output pattern
   producer = "outdir + '/{sample_id}/{sample_id}.dedup.bam'"
   # Consumer input config
   consumer_indir = "igv_config['outdir']"  # = producer's outdir
   # Consumer's expected input pattern
   consumer = "indir + '/{sample_id}/{sample_id}.dedup.bam'"
   # Do they match? Expand wildcards and compare.
   ```
3. Check for common mismatches:
   - Extra subdirectory suffixes (e.g. `/dedup`, `/bam`) that don't exist in producer output
   - Flat vs nested structure (`{indir}/{sid}.bam` vs `{indir}/{sid}/{sid}.bam`)
   - Different file extensions (`.bam` vs `.sorted_markdup.bam`)
   - Different wildcard names (`{sample_id}` vs `{sid}`)

**When fixing a mismatch, modify the consumer, not the producer** — the producer's path pattern is the source of truth since other consumers may already depend on it.

## 18. f-string escaping for bash variables in `run:` blocks

When generating bash scripts via Python f-strings (triple-quoted `f"""..."""`), bash variables using `${VAR}` syntax MUST have their braces doubled: `${{VAR}}`. Otherwise Python interprets `{VAR}` as an f-string expression and raises `NameError: name 'VAR' is not defined`.

**Wrong:**
```python
script = f"""#!/bin/bash
SAMPLE_ID="{wildcards.sample_id}"
echo -e "${SAMPLE_ID}\t${FRIP}" > $OUT
"""
```

**Correct:**
```python
script = f"""#!/bin/bash
SAMPLE_ID="{wildcards.sample_id}"
echo -e "${{SAMPLE_ID}}\t${{FRIP}}" > $OUT
"""
```

Rules:
- `{wildcards.sample_id}`, `{input.bam}`, `{params.tool}` — Snakemake interpolations, use single braces (correct)
- `${SAMPLE_ID}`, `${FRIP}` — bash variables with braces, MUST use `${{...}}`
- `$SAMPLE_ID` — bash variables WITHOUT braces, no escaping needed
- `{{print $1}}` — awk braces inside f-string, already doubled (correct)

**Detection:** Grep the f-string block for `${` not followed by `{` — these are unescaped bash variables:
```bash
grep -n '\${[^{]' module.smk
```

## 19. conda: directive works with run: blocks (Snakemake 9.x+ ONLY)

`conda:` + `run:` can coexist **ONLY in Snakemake 9.x+**. Check version first:
```bash
snakemake --version  # Must be >= 9.0
```

**Snakemake 8.x REJECTS this combination:**
```
RuleException: Conda environments are only allowed with shell, script, notebook, or wrapper directives (not with run or template_engine).
```

**If on 8.x, upgrade first:** `pip install --upgrade snakemake>=9.0`

In 9.x+, the conda environment is activated before the `run:` block executes, so all tools from the conda env are available via `shell()` calls inside the block.

**Always include `conda:` in every rule** to ensure the correct environment is activated. This is critical for reproducibility and for users who don't pre-activate conda envs.

**Never remove `conda:` from existing modules** — this breaks environment isolation. The user will correct you: "你哪里来的错误知识" if you claim conda: + run: is incompatible without checking the version.

```python
rule my_rule:
    input: ...
    output: ...
    conda:
        "my_env.yaml"   # ALWAYS include this
    run:
        shell("samtools index {input}")  # samtools from conda env
```

**Never blindly remove `conda:` from existing modules** — this breaks environment isolation.

## 20. Never modify code of a running Snakemake process

When monitoring a running workflow, **do NOT edit the .smk files or config** while the process is active. Reasons:
- The running process has already loaded and parsed the files into memory — changes have no effect until restart
- Partial edits can corrupt files if the process reads them mid-write
- It creates confusion: the user sees your changes but the error persists

**Correct workflow:**
1. Read the logs to identify the error
2. Understand the full pipeline DAG and the failing step's role
3. Propose the fix and get user approval
4. **Kill the running process** (or wait for it to exit cleanly)
5. Apply the fix
6. Restart the process

## 22. Snakemake log location vs application log

There are TWO different logs — confusing them means reading stale/wrong data:

1. **Application log** (`--log` arg to `run.py`): e.g. `<project>/logs/PeakCalling.log`. This is `run.py`'s own logging — metadata setup, snakemake command invocation, stdout/stderr capture from snakemake. Useful for seeing the overall orchestration but contains old runs too.

2. **Snakemake execution log** (the REAL workflow log): `<workdir>/.snakemake/log/<ISO-timestamp>.snakemake.log`. This shows per-rule scheduling, job start/finish times, DAG progress, and error tracebacks. Each snakemake invocation creates a new file.

**To monitor a running workflow, always read the snakemake execution log, not the application log.**

Find it:
```bash
# workdir is the snakemake working directory (usually <outdir>/<Workflow>/)
ls -lt <workdir>/.snakemake/log/
# Latest file = current run
tail -f <workdir>/.snakemake/log/$(ls -t <workdir>/.snakemake/log/ | head -1)
```

**Match log files to running processes by timestamp.** If a process started at 07:20, look for the `.snakemake/log/` file created around 07:20, NOT the one from 07:10. The application log may contain errors from the 07:10 run that don't apply to the current 07:20 run.

## 23. Always check timestamps when reading logs

"日志永远要结合当下时间来看" — always read logs in context of the current time and the running process's start time.

Before reading any log file:
1. `date` — know the current time
2. `ps aux | grep snakemake` — find the running process and its start time
3. Match log file timestamps to the process start time
4. Only focus on log entries AFTER the current process started

Old log entries from previous (failed/crashed) runs are confusing noise. The same log file may contain entries from multiple runs if the application log is appended to.

## 24. Monitoring a running Snakemake workflow

Correct monitoring sequence:
1. `ps aux | grep snakemake` — confirm process alive, note start time and target jobs
2. Find the snakemake log: `ls -lt <workdir>/.snakemake/log/`
3. `tail -f` the latest `.snakemake.log` for real-time progress
4. For per-rule detail: check individual rule logs at `<logdir>/<sample_id>/<rule>.log`
5. To see what's actively running: `ps aux | grep <tool_name>` (e.g. gatk, macs3)

Progress indicators in snakemake log:
```
Finished jobid: 18 (Rule: PeakCalling_bigwig)
3 of 7 steps (43%) done
```

Error indicators:
```
Error in rule <name>:
    jobid: N
    ...
RuleException:
```

## 25. Examine existing outputs before creating new reports

When the user asks to "make a PPT" or "generate a report", **first examine any existing report in the output directory**. The user will correct you if you create a new PPT without understanding the existing one's structure, content, and design choices.

**Correct workflow:**
1. `search_files` for existing `*.pptx` in the output directory
2. Use `python-pptx` to read the existing PPT: iterate slides, extract text from shapes, check tables
3. Match or improve the existing structure — don't reinvent from scratch
4. If the existing PPT has 9 slides with specific content, your new PPT should cover the same ground (plus new samples if applicable)

**This session:** User said "建议仔细观看...内容,再做ppt" (carefully examine existing content before making PPT) after the agent created a PPT without reading the existing `ChIPseq_PeakCalling_Report.pptx`.

## 26. Save plotting scripts as reusable modules, not throwaway /tmp files

When the user asks to "save all plotting scripts", create a proper module under `modules/` with the standard 3-file structure (.smk + .yaml + bin/). Do NOT save scripts as `/tmp/hermes-*.py` — the user wants them integrated into the workflow for reproducibility.

**Report module pattern:**
```
modules/report/
├── report.smk          # Snakemake rule (generate_report)
├── report.yaml         # Conda env (python-pptx, matplotlib, etc.)
└── bin/
    └── generate_report.py  # All-in-one: data loading + plotting + PPT generation
```

The script should be a proper CLI tool with `argparse`, not a notebook-style inline script. This makes it runnable both standalone and via Snakemake.

For RNAseq PPT reports, see `references/rnaseq-report-module.md` for the module shape, wiring pattern, and ad-hoc verification recipe.

## 27. Image distortion in PPT — use _add_picture() helper

`slide.shapes.add_picture(path, left, top, width, height)` with BOTH width AND height **stretches images** to fit the box, destroying aspect ratio. Charts look squashed or stretched.

**Fix:** Use `_add_picture()` with PIL to calculate correct dimensions preserving aspect ratio:
```python
def _add_picture(slide, img_path, left, top, max_width, max_height):
    from PIL import Image as PILImage
    img = PILImage.open(img_path)
    img_w, img_h = img.size
    aspect = img_w / img_h
    w = max_width; h = w / aspect
    if h > max_height: h = max_height; w = h * aspect
    left_emu = left + (max_width - w) / 2  # center horizontally
    slide.shapes.add_picture(img_path, Inches(left_emu), Inches(top), Inches(w), Inches(h))
```

Requires `pillow` in conda env. ALL image slides must use this helper.

## 28. PPT element overlap — use Layout class, not hardcoded positions

Hardcoded positions cause overlap when content changes. Use a `Layout` class that tracks vertical position and prevents overflow.

**CRITICAL: NEVER bypass Layout.** ALL elements must go through `lay.allocate()`. Do NOT use `if lay.remaining > X:` then place directly — this skips Y tracking and causes overlap with later elements. Helper functions like `_bullet()` and `_note_list()` that accept raw `y` coordinates are DANGEROUS — they bypass Layout. Always `lay.allocate()` first, then place at the returned position.

```python
class Layout:
    """Tracks vertical position to prevent element overflow.
    Every multi-element slide uses a Layout instance."""
    def __init__(self, top=CONTENT_TOP, bottom=SLIDE_H - 0.2):
        self.y = top
        self.bottom = bottom

    @property
    def remaining(self):
        return max(0, self.bottom - self.y)

    def allocate(self, h):
        """Return (y, actual_h) clipped to remaining space, or None.
        Enforces minimum height of 0.15" to prevent zero/negative-height elements."""
        if self.remaining < 0.15:
            return None
        actual_h = min(max(h, 0.15), self.remaining)
        if actual_h < 0.15:
            return None
        y = self.y
        self.y += actual_h
        return y, actual_h

    def gap(self, size=0.1):
        self.y += min(size, self.remaining)
```

Layout constants:
```python
SLIDE_W = 10.0; SLIDE_H = 5.625
MARGIN_L = 0.5; CONTENT_W = SLIDE_W - MARGIN_L * 2
HEADER_H = 0.7; CONTENT_TOP = HEADER_H + 0.2
CONTENT_MAX_H = SLIDE_H - CONTENT_TOP - 0.3
```

Usage pattern — every multi-element slide builder:
```python
def slide_markdup(prs, ...):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _header(slide, title)
    lay = Layout()
    # Table
    alloc = lay.allocate(min(lay.remaining * .6, len(tbl) * .32))
    if alloc:
        _add_table(slide, tbl, Inches(MARGIN_L), Inches(alloc[0]), Inches(CONTENT_W), Inches(alloc[1]))
    lay.gap(0.1)
    # Notes below table
    _note_list(slide, notes, lay.y)
```

For warnings/notes below images, use fixed bottom position `SLIDE_H - 0.4` instead of `CONTENT_TOP + img_h` (which requires knowing the adjusted image height).

## 29. DPI 300 for publication figures

Use `DPI = 300` for all matplotlib outputs. Default 100-150 DPI produces blurry figures when printed or zoomed. Set as module-level constant:
```python
DPI = 300
def _save(fig):
    tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="rpt_", delete=False)
    fig.savefig(tmp.name, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return tmp.name
```

## 30. Full genomic coordinates — never abbreviate

When displaying genomic positions in tables or text, use full `chr:start-end` format. NEVER abbreviate to `chrX:105M` or similar — the user needs exact coordinates for manual verification.

```python
# WRONG
pos = f"{chr}:{int(start)//1_000_000}M"

# CORRECT
pos = f"{chr}:{start}-{end}"
```

This applies to: PPT tables, gene lists, peak annotations, any user-facing coordinate display.

## 31. --img-dir for saving plot images alongside PPT

When generating reports with matplotlib plots, support an `--img-dir` parameter to save plot images separately (for reuse in other reports, publications, or debugging). Default behavior: temp files auto-deleted.

```python
# In main():
ap.add_argument("--img-dir", default="", help="Directory to save plot images")
# ...
if args.img_dir:
    os.makedirs(args.img_dir, exist_ok=True)
    import shutil
    for name, path in all_imgs.items():
        if path and os.path.exists(path):
            shutil.copy2(path, os.path.join(args.img_dir, f"{name}.png"))
```

In the Snakemake rule, pass `--img-dir {params.img_dir}` where `params.img_dir = outdir + "/ppt_results"`.

## 33. Subworkflow refactoring checklist — common anti-patterns

When cleaning up ("规整") a subworkflow .smk, check for these issues found in `ncRNAseq.smk`:

1. **Missing preamble** — every subworkflow needs: `shell.prefix("set -x; set -e;")`, `from snakemake.logging import logger`, config extraction (`indir`/`outdir`/`logdir`/`samples`/`outfiles`/`ROOT_DIR`), and `rule all: input: outfiles`.

2. **Module gets bare `config` instead of dedicated dict** — `module X: config: config` passes the entire workflow config, bypassing the module's expected contract. Always pass the `<tool>_config` dict.

3. **Stale rule alias prefixes** — copied from another subworkflow without updating. E.g. `RNA_SNP_trimming_Paired` in ncRNAseq.smk should be `ncRNAseq_trimming_Paired`. Grep for cross-prefix contamination.

4. **`use rule` name mismatch** — `use rule hisat2_align from hisat2` fails if the target module only exports `hisat2_align_ncRNAseq_single`. Always verify actual rule names in the target .smk before writing use-rule. Use `search_files(pattern="^rule ", path="<target>.smk")`.

5. **Hardcoded Params instead of config reads** — star_config with literal `99999`, `0.1`, etc. should read from `config.get('Params',{}).get('STAR',{}).get('key') or default`.

6. **Path chain break** — module B's `indir` must equal module A's `outdir`. A common bug: featureCounts `indir` pointing at cutadapt output instead of aligner output. Trace: cutadapt -> aligner -> quantifier.

7. **`get_output_*()` function belongs in run.py, NOT in .smk** — The `get_output_ncRNAseq()` / `get_output_*()` pattern that builds the outfiles list must live in `run.py`'s `run<Workflow>()` function, NOT in the subworkflow .smk. Reasons: (a) .smk files are Snakemake DSL, not importable Python modules — `run.py` cannot call functions defined in .smk; (b) mixing Python control flow with Snakemake DSL (e.g. `include:` inside `def`) is fragile and confusing; (c) other subworkflows (RNAseq, tRNAseq) build outfiles directly in run.py — follow that pattern. The old `ncRNAseq.smk` had `get_output_ncRNAseq` with `include:` inside and undefined global references (`genomes`, `all_samples`) — the entire function was removed and should be reimplemented in `run.py`.

8. **Undefined global references** — function body referencing `genomes`, `paired_samples`, `all_samples` etc. that aren't in scope. Use the config-extracted variables from the preamble. If a function needs these, it should be in run.py where they're built from samples_info_dict.

9. **Missing logger.info** — every config dict should have `logger.info(f"<tool>_config: {<tool>_config}")` for debugging.

Use `scripts/verify-subworkflow.py <subworkflow.smk>` to check these automatically (see scripts/).

## 35. Never put concrete rules in a subworkflow .smk

**Subworkflows are orchestrators, not implementors.** A subworkflow .smk must ONLY contain:
- Preamble (shell.prefix, imports, config extraction, rule all)
- Module config dicts
- `module X: ...` declarations
- `use rule X from Y as Z` aliases
- Conditional branches (`if aligner == ...`)

**Never define `rule foo:` directly in a subworkflow** (except `rule all`). All concrete rules belong in `modules/`. The user will correct you: "为什么将具体规则也到subworkflow里面" (why did you put concrete rules in the subworkflow).

**What to do instead:** Create a module under `modules/<tool>/` with the rules, then import and alias them in the subworkflow.

## 36. Sub-module pattern for extending existing modules

When a pipeline needs auxiliary rules that extend an existing module (e.g., extract/merge steps wrapping STAR alignments), create a **sub-module directory** under the parent module:

```
modules/star/
  star.smk                    # Original module (reused via use rule)
  star_3pass/
    star_3pass.smk            # Auxiliary rules (extract, merge, etc.)
```

**Rules:**
- Sub-module uses the parent's tool binaries via its own config dict (not re-declaring them)
- Sub-module `.smk` reads tools from `config.get("Procedure", {}).get("samtools")` etc.
- Sub-module does NOT need .json or .yaml (it shares the parent's conda env)
- In the subworkflow, import both: `module star_passN: ...` for the main tool, `module star_3pass: ...` for aux rules

**Real example (ncRNAseq three-pass STAR):**
```python
# Subworkflow imports star module 4 times with different configs
module star_pass1:
    snakefile: "../modules/star/star.smk"
    config: star_pass1_config
use rule star_align from star_pass1 as ncRNAseq_star3p_pass1

# ... pass2, pass3a, pass3b same pattern ...

# Sub-module for auxiliary rules
module star_3pass:
    snakefile: "../modules/star/star_3pass/star_3pass.smk"
    config: star_3pass_config
use rule star_3p_extract_smallrna from star_3pass as ncRNAseq_star3p_extract_smallrna
use rule star_3p_merge from star_3pass as ncRNAseq_star3p_merge
```

## 37. Config key case sensitivity between subworkflow and module

When passing config dicts from subworkflow to module, the keys must match EXACTLY what the module reads. A common bug:

```python
# Subworkflow passes UPPERCASE keys
star_3pass_config = {
    "Procedure": {"SAMTOOLS": SAMTOOLS, "BEDTOOLS": BEDTOOLS}
}

# Module reads lowercase keys
SAMTOOLS = config.get("Procedure", {}).get("samtools") or "samtools"  # ← gets None!
```

**Fix:** Match the case. If the module reads `"samtools"`, the subworkflow must pass `"samtools"`:
```python
star_3pass_config = {
    "Procedure": {"samtools": SAMTOOLS, "bedtools": BEDTOOLS}
}
```

**Verification:** After writing a module, grep all `config.get("` calls in the .smk and ensure every key appears in the config dict the subworkflow passes. Check both top-level and nested keys.

## 34. Never swallow stderr in subprocess calls (download scripts, external tools)

`subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)` makes debugging impossible. When an external tool (ascp, wget, samtools) fails, the user sees only `[FAIL]` with zero diagnostic info.

**Rule:** Always capture stderr and log it on failure. Pattern for download/external-tool wrappers:

```python
def ascp_download(remote: str, dest: Path, key: Path, logger) -> bool:
    cmd = ["ascp", "-k", "1", "-T", "-l", "200m", "-P", "33001",
           "--overwrite=always", "-i", str(key), remote, str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"ascp failed (rc={result.returncode}): {result.stderr.strip()}")
        return False
    return True
```

Key: `capture_output=True, text=True` + log `result.stderr` on failure. This turns opaque `[FAIL]` messages into actionable errors (e.g. `ascp: failed to authenticate, exiting`).

The old pattern in `ascp_download.py` swallowed both stdout and stderr, hiding the actual authentication failure for 6+ retry attempts.

## 38. Optional inputs in run: blocks (e.g. conditional --sjdbGTFfile)

When a rule needs to conditionally include a parameter based on whether an input exists, move the optional input from `input:` to `params:` and handle it in the `run:` block:

```python
rule star_index:
    input:
        fasta = fasta,          # required
    output:
        index_file = directory(outdir + "/index")
    params:
        STAR = ...,
        gtf = gtf               # optional — moved from input to params
    run:
        cmd = [params.STAR, "--runMode", "genomeGenerate",
               "--genomeDir", ..., "--genomeFastaFiles", input.fasta]
        if params.gtf:
            cmd.extend(["--sjdbGTFfile", params.gtf])
            rule_logger.info(f"Using sjdbGTFfile: {params.gtf}")
        else:
            rule_logger.info("No GTF provided, skipping --sjdbGTFfile")
```

**Why not keep it in `input:`?** Snakemake treats `None` inputs as non-existent, but `{input.gtf}` in shell expands to the literal string "None". In a `run:` block you can use `if params.gtf:` to skip cleanly.

**When to use:** Any rule where a reference file is optional (GTF for indexing, BED for filtering, etc.). The `run:` block gives you Python control flow that `shell:` doesn't.

## 39. Python scripts for GTF/BED parsing instead of inline awk

For complex GTF parsing (e.g. extracting smallRNA genes by gene_type), use a Python script in `modules/<tool>/bin/` instead of inline awk in shell:. Benefits:
- Testable standalone (`python extract_smallrna.py --gtf ... --help`)
- Type-safe attribute parsing (awk regex on GTF attributes is fragile)
- Proper error messages and argparse help
- Reusable across workflows

Pattern:
```python
# modules/genome/bin/extract_smallrna.py
def main():
    p = argparse.ArgumentParser("Extract small RNA genes from GENCODE GTF")
    p.add_argument("--gtf", required=True)
    p.add_argument("--fasta", required=True)
    p.add_argument("--chrom-sizes", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--flank", type=int, default=50)
    p.add_argument("--types", nargs="+", default=[...])
    p.add_argument("--bedtools", default="bedtools")
    args = p.parse_args()
    # 1. Parse GTF → BED
    # 2. bedtools slop + getfasta → FASTA
```

In the .smk rule, use `params.script = os.path.join(ROOT_DIR, "modules", "<tool>", "bin", "script.py")` and call via `shell("python {params.script} ...")`.

**Output to `{cwd}/test/` (or `{--output-dir}/test/`):** Output goes to cwd, NOT root_dir:
```python
base_out = args.output_dir if args.output_dir else os.getcwd()
args.output_dir = os.path.join(base_out, "test")
```

## 40. Reusing module rules for different purposes (star_index for smallRNA)

When you need to run the same tool with different configs (e.g. STAR index for genome vs smallRNA), import the module multiple times with different config dicts:

```python
# Genome index (with GTF)
module star_genome_idx:
    snakefile: "../modules/star/star.smk"
    config: star_genome_idx_config

# SmallRNA index (no GTF)
module star_smallrna_idx:
    snakefile: "../modules/star/star.smk"
    config: {"indir": ..., "outdir": ..., "Procedure": {"STAR": STAR},
             "Params": {"STAR": {}}, "genome": {"fasta": smallrna_fasta, "gtf": None}}

use rule star_index from star_genome_idx as ncRNAseq_star_index_genome
use rule star_index from star_smallrna_idx as ncRNAseq_star_index_smallrna
```

The key insight: the `star_index` rule uses `if params.gtf:` to handle the optional GTF, so passing `gtf: None` works cleanly.

## 41. Legacy patterns to remove: configfile:, SNAKEFILE_DIR, workflow.snakefile

Old modules may contain these patterns that conflict with the `module` + `use rule` architecture:

```python
# OLD — remove these
SNAKEFILE_FULL_PATH = workflow.snakefile
SNAKEFILE_DIR = os.path.dirname(SNAKEFILE_FULL_PATH)
SomeYaml = get_yaml_path("Tool", SNAKEFILE_DIR)
configfile: SomeYaml                    # ← conflicts with module config: dict
script = SNAKEFILE_DIR + "/bin/foo.py"  # ← undefined when used via module
REPORT_SCRIPT = os.path.join(os.path.dirname(workflow.snakefile), "bin", "script.py")
```

**Replace with:**
```python
# NEW — use ROOT_DIR for module-local paths
MODULE_DIR = os.path.join(ROOT_DIR, "modules", "<tool>")
script = os.path.join(MODULE_DIR, "bin", "foo.py")
# or directly:
REPORT_SCRIPT = os.path.join(ROOT_DIR, "modules", "<tool>", "bin", "script.py")
```

**Detection:**
```bash
grep -rn "configfile:\|workflow\.snakefile\|SNAKEFILE_DIR\|SNAKEFILE_FULL_PATH\|get_yaml_path" --include="*.smk"
```

**Why:** When a module is loaded via `module X: snakefile: ..., config: ...`, the config is passed through the module declaration. `configfile:` overrides this and loads from a fixed YAML file, breaking the module's config contract. `SNAKEFILE_DIR` is undefined when the .smk is loaded as a module (it's only set when run directly).

**Also replace `config[]` with `config.get()`:** `config["key"]` raises `KeyError` if the key is missing. `config.get("key", default)` is safer and consistent with the project convention.

## 42. Test framework design — --test mode in run.py

When adding test infrastructure to the project, follow these rules (user-corrected):

**`__main__` block structure — extract into named functions:** The `if __name__ == "__main__":` block in `run.py` must be minimal (~12 lines). Extract logic into these canonical functions:

```python
def setup_test_args(args, root_dir: str):
    """Configure args for --test mode. Modifies args in-place."""
    # Resolve workflow names, output dir, meta files, test paths
    # Load SchemaValidator, call generate_test_paths()
    # Set args.conda_prefix, args.dry_run, args._test_meta_map
    return args

def setup_normal_args(args):
    """Validate args for normal (non-test) mode."""
    if not args.meta: exit(1)
    if not args.output_dir: exit(1)
    args._test_meta_map = None
    return args

def execute_workflows(args, root_dir: str, logger):
    """Execute all configured workflows."""
    # Metadata setup, workflow config, snakemake cmd building
    # Test mode: collect pass/fail results, call print_test_summary()
    # Normal mode: run directly or in parallel

def print_test_summary(test_results: Dict[str, tuple]):
    """Print pass/fail summary and exit(1) if any failed."""

if __name__ == "__main__":
    args = parse_args()
    ROOT_DIR = os.path.dirname(__file__)
    if args.test is not None:
        setup_test_args(args, ROOT_DIR)
    else:
        setup_normal_args(args)
    logger = setup_logger("root", level=logging.INFO, log_file=args.log)
    execute_workflows(args, ROOT_DIR, logger)
```

Key points:
- `__main__` block is ~12 lines — parse, setup, execute
- `execute_workflows` owns the metadata + workflow dispatch loop
- `setup_test_args` uses `SchemaValidator().load()` + `generate_test_paths()` (not inline heuristics)
- `print_test_summary` is called inside `execute_workflows` in test mode
- `ROOT_DIR` is passed as parameter, not used as global

**Test resources location:** `assests/test/` (NOT `test/` inside source tree). Consolidate with existing `assests/meta/` directory.

**Output to `{cwd}/test/` (or `{--output-dir}/test/`):** Output goes to cwd, NOT root_dir:
```python
base_out = args.output_dir if args.output_dir else os.getcwd()
args.output_dir = os.path.join(base_out, "test")
```
    shutil.rmtree(args.output_dir)  # clean previous run
os.makedirs(args.output_dir, exist_ok=True)
```

**Per-workflow path injection:** Schema defines which fields are paths; the actual config JSON structure determines WHERE to inject. In `execute_workflows`, read each workflow's config genome structure:
- Flat (`genome.fasta`) → inject flat paths
- Nested (`genome.GRCm39.fasta`) → inject nested paths per organism

```python
# In execute_workflows, per-workflow:
genome_cfg = workflow_config.get("genome", {})
nested_orgs = [k for k, v in genome_cfg.items()
               if nested_orgs:
                   # Nested: inject genome.<org>.field ONLY for fields that exist in the config
                   for org in nested_orgs:
                       org_cfg = genome_cfg.get(org, {})
                       for field in org_cfg.keys():
                           base_key = f"genome.{field}"
                           if base_key in base_paths:
                               wf_extra[f"genome.{org}.{field}"] = base_paths[base_key]
else:
    for k, v in base_paths.items():
        wf_extra[k] = v
```

**DO NOT** inject globally in `setup_test_args` — flat paths pollute nested configs and vice versa.

**Dynamic workflow discovery, not hardcoded:**
```python
ALL_WORKFLOWS = list(WORKFLOW_DISPATCH.keys())  # NOT a manual dict
args._test_meta_map = {wf: os.path.join(TEST_DIR, f"meta_{wf}.tsv") for wf in args.workflow_name}
```

**Output to `{cwd}/test/` (or `{--output-dir}/test/`):** Output goes to cwd, NOT root_dir:
```python
base_out = args.output_dir if args.output_dir else os.getcwd()
args.output_dir = os.path.join(base_out, "test")
```

**Local conda-prefix:** Override `args.conda_prefix` to test output dir to avoid permission issues with shared env paths.

**Use SchemaValidator for path generation:** The test framework MUST use `src/common/SchemaValidator.py` backed by per-workflow `config/<wf>.schema.json` files as the single source of truth for path-type fields. See `references/schema-validator.md` for the full API and schema format.

**Schema design: per-workflow, mirrors config structure:** Each workflow has its own `config/<wf>.schema.json` that mirrors the config JSON structure exactly. No inheritance, no merging, no override mechanism. Schema mirrors config: top-level fields = config top-level, `genome` section = config genome section. Organisms like GRCm39/GRCh38 are nested dicts inside genome.

```python
from src.common.SchemaValidator import SchemaValidator
import re  # needed for nested organism detection

sv = SchemaValidator()
sv._schema_dir = os.path.join(root_dir, "config")  # set dir, not load single file
test_paths = sv.generate_test_paths(test_data_dir, genome_name)
# test_paths = {"genome.fasta": "/abs/path/ref/GRCm39.fa", ...}
```

**Inject ALL path fields, not just genome.*:** The injection logic must handle ALL path-like values in the config, including `Params.arriba.blacklist`, `Procedure.gatk`, etc. Use recursive `_inject()` that walks the entire config dict, not just the genome section. For each field: if in schema paths → use schema path; else if value is null or contains "/" → generate test path.

```python
def _inject(cfg, prefix, wf_extra):
    for field, val in cfg.items():
        dotted = f"{prefix}.{field}" if prefix else field
        if isinstance(val, dict):
            _inject(val, dotted, wf_extra)
        elif _is_path(val):  # null or contains "/"
            wf_extra[dotted] = base_paths.get(dotted, _make_test_path(field, test_data, genome))

_inject(workflow_config, "", wf_extra)
```

Key advantages over the old inline approach:
- Schema declares path types explicitly (`"path": "file"|"dir"|"prefix"`), not inferred from key names
- Workflow-specific required-field overrides live in `schema.json`, not in Python code
- `validate()` catches missing/null/type errors before Snakemake runs
- Adding a new genome field = one line in schema.json, zero code changes

Test data structure under `assests/test/data/`:
```
data/
  ref/           # genome FASTA, GTF, fai, dict, known_sites, etc.
  index/         # hisat2/, star/, bowtie2/, bwa-mem2/ index files
  smallrna/      # smallRNA BED, FASTA
  fastq/         # touch FASTQ per sample (PE: _1.fq.gz + _2.fq.gz, SE: .fq.gz)
```

**Test summary with pass/fail reporting:** In test mode, wrap each workflow execution in try/except, collect results, then call `print_test_summary()`. The summary function handles the pass/fail display and `exit(1)` on any failure:

```python
def print_test_summary(test_results: Dict[str, tuple]):
    """Print pass/fail summary and exit(1) if any failed."""
    logger.info(f"[Results ({len(test_results)} workflows)")
    passed = [k for k, (ok, _) in test_results.items() if ok]
    failed = [k for k, (ok, _) in test_results.items() if not ok]
    for wf in sorted(test_results.keys()):
        ok, err = test_results[wf]
        status = "PASS" if ok else "FAIL"
        logger.info(f"  [{status}] {wf}")
        if not ok and err:
            logger.info(f"         {err.splitlines()[0] if err else 'unknown error'}")
    logger.info(f"\n  Passed: {len(passed)}, Failed: {len(failed)}, Total: {len(test_results)}")
    if failed:
        logger.error(f"  Failed workflows: {', '.join(failed)}")
        exit(1)
```

Called from `execute_workflows` after all workflows have run:
```python
if args._test_meta_map:
    for cmd, cwd in smk_cmds:
        wf = os.path.basename(cwd)
        try:
            _run_cmd(cmd, cwd=cwd)
            test_results[wf] = (True, "")
        except Exception as e:
            test_results[wf] = (False, str(e)[:200])
    print_test_summary(test_results)
```

**Key: one workflow failure must NOT abort the entire test run.** Each workflow is independent; continue testing others and report all results at the end.

## 44. ROOT_DIR must be in EVERY module config dict

`common.smk` imports `setup_logger` via `from common.LogUtil import setup_logger`, which requires `ROOT_DIR` to locate `src/common/`. If ROOT_DIR is missing from the module's config dict, the import fails:

```
ImportError: Failed to import common.LogUtil.setup_logger.
Original error: No module named 'common'
```

**Rule:** Every `<tool>_config` dict in a subworkflow MUST include `"ROOT_DIR": ROOT_DIR`:

```python
fastqc_config = {
    "ROOT_DIR": ROOT_DIR,    # ← MUST have this
    "indir": indir,
    "outdir": f"{outdir}/QC",
    "logdir": logdir,
    ...
}
```

**Systematic check:** After writing a subworkflow, grep for all `module <name>:` declarations and verify each one's config dict has `ROOT_DIR`. A missing ROOT_DIR on ANY module will crash the entire workflow at parse time.

**Affected modules:** Any module with `include: "../common/common.smk"` — which is ALL modules (after the shell: → run: conversion). The error manifests at the FIRST module that gets loaded without ROOT_DIR, not necessarily the one you just changed.

## 46. run.py __main__ block — extract functions, keep minimal

The `if __name__ == "__main__":` block should be a thin dispatcher, NOT contain inline logic. Extract into named functions:

```python
def setup_test_args(args, root_dir: str):
    """Configure args for --test mode. Modifies args in-place."""
    import shutil
    from src.common.SchemaValidator import SchemaValidator
    
    ALL_WORKFLOWS = list(WORKFLOW_DISPATCH.keys())
    if args.test == "all":
        args.workflow_name = ALL_WORKFLOWS
    elif args.test in ALL_WORKFLOWS:
        args.workflow_name = [args.test]
    else:
        print(f"[TEST] Unknown workflow: {args.test}\n  Available: {ALL_WORKFLOWS} or 'all'")
        exit(1)
    
    # Output to {cwd}/test/ (or {--output-dir}/test/)
    base_out = args.output_dir if args.output_dir else os.getcwd()
    args.output_dir = os.path.join(base_out, "test")
    if os.path.exists(args.output_dir):
        shutil.rmtree(args.output_dir)
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Store base paths for per-workflow injection in execute_workflows
    sv = SchemaValidator()
    sv.load(os.path.join(root_dir, "config", "schema.json"))
    test_data = os.path.join(root_dir, "assests", "test", "data")
    args._test_base_paths = sv.generate_test_paths(test_data, "GRCm39")
    
    args._test_meta_map = {
        wf: os.path.join(root_dir, "assests", "test", f"meta_{wf}.tsv")
        for wf in args.workflow_name
    }
    args.dry_run = True
    args.conda_prefix = os.path.join(args.output_dir, ".conda")
    os.makedirs(args.conda_prefix, exist_ok=True)

def setup_normal_args(args):
    """Validate required args for normal (non-test) mode."""
    if not args.meta:
        print("Error: -m/--meta is required (unless --test is used)")
        exit(1)
    if not args.output_dir:
        print("Error: -o/--output_dir is required (unless --test is used)")
        exit(1)
    args._test_meta_map = None

def execute_workflows(args, root_dir, logger):
    """Build and execute snakemake commands for all workflows."""
    # ... workflow loop, metadata loading, cmd building, execution ...

def print_test_summary(test_results):
    """Print PASS/FAIL summary table."""
    # ... summary logic ...

if __name__ == "__main__":
    args = parse_args()
    ROOT_DIR = os.path.dirname(__file__)
    if args.test is not None:
        setup_test_args(args, ROOT_DIR)
    else:
        setup_normal_args(args)
    logger = setup_logger("root", level=logging.INFO, log_file=args.log)
    execute_workflows(args, ROOT_DIR, logger)
```

Benefits:
- `__main__` block is ~12 lines (was ~75)
- Each function is testable independently
- Test mode logic is isolated from production logic
- Easy to add new modes (e.g., `--validate`)

## 45. Config JSON paths must be real paths, not null

Config JSON files (`config/<Workflow>.json`) should have actual path values for all `genome.*` keys, NOT `null`. Reasons:

1. **Test framework needs real paths to override** — `_generate_test_paths()` scans ALL `genome.*` keys (not just null) and replaces them with test paths. If the key is null, the test framework can still generate a path, but having a real path makes the config self-documenting.

2. **run.py validates paths** — Some `run<Workflow>()` functions check `os.path.isfile()` on config paths. Null paths crash with `TypeError: stat: path should be string`.

3. **Self-documenting config** — A config with `"genome.fasta": "/data/pub/genome/GRCm39.fa"` tells the user exactly what's expected. A null value gives no guidance.

**Convention:** Use placeholder paths that indicate the expected resource:
```json
{
    "genome": {
        "fasta": "/path/to/genome.fa",
        "gtf": "/path/to/genes.gtf",
        "star_index_dir": "/path/to/star_index"
    }
}
```

The test framework will override these with touch files during `--test` mode.

## 48. STAR index `MissingInputException` — `use rule` must import `star_index` alongside `star_align`

When `star_index` outputs `directory(outdir + "/index")` and `star_align` uses an input function `get_star_index()` that returns the same path, Snakemake fails with `MissingInputException`. The root cause is NOT `directory()` type — it's that `star_index` was never imported via `use rule`, so it doesn't exist in the DAG.

**Root cause:** `use rule star_align from star_passN as X` only imports `star_align`. The `star_index` rule from the same module is invisible to the DAG. When `get_star_index()` returns `{outdir}/index` (because `index_dir` is null), Snakemake can't find any rule to produce that path.

**Fix — auto-build when index_dir is null:** Create a dedicated index module and import its `star_index` rule, following the same pattern as `star_smallrna_idx`:

```python
# In subworkflow, BEFORE any config dicts that reference star_index_dir:
if not star_index_dir:
    star_genome_idx_config = {
        "ROOT_DIR": ROOT_DIR,
        "outdir": f"{outdir}/genome",       # or "{outdir}/common/3_raw_bam" for non-3pass
        "logdir": logdir,
        "Procedure": {"STAR": STAR},
        "Params": {"STAR": {}},
        "genome": {"fasta": genome_fasta, "gtf": config.get("genome", {}).get("gtf")}
    }
    module star_genome_idx:
        snakefile: "../modules/star/star.smk"
        config: star_genome_idx_config
    use rule star_index from star_genome_idx as ncRNAseq_star_index_genome
    star_index_dir = f"{outdir}/genome/index"

# THEN create pass configs that capture star_index_dir:
star_pass1_config = {..., "genome": {"fasta": genome_fasta, "index_dir": star_index_dir}}
```

**Critical ordering:** The auto-build block MUST execute BEFORE the config dicts are created. Python dict literals capture variable values at creation time (see pitfall #61). If you put the auto-build after the config dicts, they'll have `None`.

**When `star_index_dir` IS set:** The `if not star_index_dir:` block is skipped entirely. The pre-built index is used directly. User can also pre-build manually:
```bash
STAR --runMode genomeGenerate --runThreadN 20 \
     --genomeDir /path/to/star_index \
     --genomeFastaFiles genome.fa --sjdbGTFfile genes.gtf --sjdbOverhang 100
```

**Key config key:** `star.smk`'s `get_star_index()` reads `config.get('genome',{}).get('index_dir')`. The subworkflow passes `"index_dir"` in the config dict.

## 48b. `use rule` import scope — only explicitly imported rules exist in the DAG

When using `module X:` + `use rule Y from X as Z`, **only rule Y** is available in the calling workflow. Other rules from the same module (even those that Y depends on internally) are NOT automatically imported.

**Pattern that breaks:**
```python
module star_pass1:
    snakefile: "../modules/star/star.smk"
    config: star_pass1_config
use rule star_align from star_pass1 as ncRNAseq_star3p_pass1
# star_index is NOT imported → if star_align's input function returns
# a path only star_index produces, MissingInputException results
```

**Fix:** Import all rules that the DAG needs:
```python
use rule star_index from star_pass1 as ncRNAseq_star_index_pass1   # ← add this
use rule star_align from star_pass1 as ncRNAseq_star3p_pass1
```

Or (better) create a dedicated index module (see pitfall #48) to avoid redundant index builds across multiple passes.

**General rule:** After importing rules from a module, trace the full dependency chain. For each input function (`get_star_index`, `get_alignment_input`, etc.), check what path it returns and whether a rule in the current workflow can produce that path. If not, import the missing rule.

## 49. Copy-paste contamination in rule aliases

When subworkflows are copied from each other, stale rule alias prefixes persist:
```python
# BUG: copied from PeakCalling.smk, prefix not updated
use rule fastqc from fastqc_raw as PeakCalling_fastqc_raw
use rule trimming_Paired from trim_galore as PeakCalling_trimming_Paired

# FIX: use the correct subworkflow prefix
use rule fastqc from fastqc_raw as ncRNAseq_fastqc_raw
use rule trimming_Paired from trim_galore as ncRNAseq_trimming_Paired
```

**Detection after copying a subworkflow:**
```bash
grep -n "as [A-Z]" subworkflow/<new>.smk | grep -v "as <NewWorkflow>_"
```
Any alias not prefixed with the new workflow's name is likely stale.

## 50. Path chain bugs: featureCounts indir and double directory nesting

**Bug 1: indir mismatch.** featureCounts config `indir` must match the aligner's output path:
```python
# BUG: featureCounts looks in wrong directory
featureCounts_config = {"indir": f"{outdir}/ncRNAseq/bam"}  # no rule outputs here

# FIX: point to actual aligner output
featureCounts_config = {"indir": f"{outdir}/common/3_raw_bam"}  # star output
```

**Bug 2: double directory nesting.** When a subworkflow's `outdir` already includes the workflow name (e.g., `{output_dir}/ncRNAseq`), adding another level creates `ncRNAseq/ncRNAseq/`:
```python
# BUG: outdir is already .../ncRNAseq, adding ncRNAseq again
featureCounts_config = {"outdir": f"{outdir}/ncRNAseq/counts"}
# → .../ncRNAseq/ncRNAseq/counts  (double nesting!)

# FIX: outdir already contains the workflow prefix
featureCounts_config = {"outdir": f"{outdir}/counts"}
# → .../ncRNAseq/counts  (correct)
```

**Systematic check:** After defining all module configs in a subworkflow, print/log the full resolved paths and verify no path component appears twice.

## 51. Missing `/` separator in outdir concatenation

A common bug: `outdir + "filename"` instead of `outdir + "/filename"`:
```python
# BUG: missing /
rule featureCounts_result:
    input:
        paired = outdir + "all_paired_featureCounts.tsv",   # → ".../countsall_paired..."
        single = outdir + "all_single_featureCounts.tsv"

# FIX: add /
    input:
        paired = outdir + "/all_paired_featureCounts.tsv",
        single = outdir + "/all_single_featureCounts.tsv"
```

Also, terminal aggregation rules need `output: touch(...)` or Snakemake treats them as always dirty:
```python
rule featureCounts_result:
    input:
        paired = outdir + "/all_paired_featureCounts.tsv",
        single = outdir + "/all_single_featureCounts.tsv"
    output:
        touch(outdir + "/featureCounts.done")
```

## 52. Conda `TypeError` during `conda create` (conda 26.x)

Conda 26.1.1 (and possibly other 26.x versions) can fail during `conda create` with:
```
TypeError('expected str, bytes or os.PathLike object, not NoneType')
```
The transaction appears to complete but then rolls back. The exit code is 0 but the environment is NOT created.

When you see a Snakemake failure, always inspect the per-rule log before changing the workflow. The `.snakemake/log/*.log` file shows the real failing job; the top-level WorkflowError often only wraps several SpawnedJobError instances.

For jobs that shell out to nested tools (e.g. Tailer, STAR), check both the Snakemake execution log and the rule-local log under `logdir/<sample>/...` before concluding the root cause.

**Root cause:** Conda plugin issue. `CONDA_NO_PLUGINS=true` does NOT help (the env var is ignored by the subprocess chain).

**Pattern — which packages trigger it:** Envs with Python packages fail; non-Python envs (STAR, fastqc, samtools, bedtools) succeed. The TypeError occurs during `Executing transaction` → `Rolling back transaction` in conda's post-link hooks.\n\n**Workarounds (tried in order):**\n1. Relax version pins in `.yaml` — strict pins like `cutadapt=5.2` can trigger the solver bug; use `>=` ranges instead\n2. Change `--conda-frontend` default from `mamba` to `conda` in `run.py` (mamba frontend deprecated in snakemake 9.x and causes `Support for alternative conda frontends has been deprecated` warnings + separate errors)\n3. Pre-create the problematic env with `--no-deps` flag: `conda create -p <prefix>/<hash>_ -c conda-forge -c bioconda <tool> --no-deps -y`, then install Python deps via pip wrapper\n4. Install the tool via pip into an existing env: `pip install cutadapt` + create a shell wrapper script in the conda prefix bin/\n5. Downgrade conda: `conda install conda=24.x`\n6. Use `mamba` as standalone (not as conda frontend)\n\n**Additional conda 26.x gotcha — solver config:** If conda reports `You have chosen a non-default solver backend (libmamba) but it was not recognized`, fix with:\n```bash\nconda config --set solver classic\n```\nThis happens when `.condarc` references libmamba but the solver plugin is missing.

**Do not misdiagnose 'same YAML keeps redownloading' without checking the live process.** If a user says Snakemake has been 'downloading envs all night', first verify whether it is repeatedly recreating an existing env or simply stuck creating ONE new env.

Verification sequence:
```bash
ps -ef | grep -i '[s]nakemake'
ps -ef | grep -E '[c]onda|[m]amba|[p]ython.*snakemake'
ls -lt <workdir>/.snakemake/log/
# open the newest log matching the current snakemake start time
```

Then inspect the newest `.snakemake.log` and find the last `Creating conda environment ...` line. If the active child process is:
```bash
conda env create --file <conda-prefix>/<hash>_.yaml --prefix <conda-prefix>/<hash>_
```
read that generated `<hash>_.yaml` to identify the exact module env that is stuck. This often shows the workflow is blocked on one heavyweight env, not repeatedly failing to reuse an unchanged env.

**What commonly makes one env stall for hours:**
- too many channels in `.condarc`
- missing `channel_priority: strict`
- mixed old / niche channels (`r`, `cdat-forge`, `anaconda`, mirror `pkgs/free`, etc.)
- bundling optional plotting deps (e.g. `matplotlib-base`) into the runtime env for a tool that does not need them on the main execution path

**Additional conda 26.x gotcha — solver config:** If conda reports `You have chosen a non-default solver backend (libmamba) but it was not recognized`, fix with:
```bash
conda config --set solver classic
```
This happens when `.condarc` references libmamba but the solver plugin is missing.

**When a single env seems to run forever, inspect the generated yaml and the active child process before editing the workflow.** If the active process is `conda env create --file <conda-prefix>/<hash>_.yaml --prefix <conda-prefix>/<hash>_`, open that generated yaml to identify the exact module/env being solved. A "stuck overnight" report often means one heavyweight env is still resolving, not that Snakemake keeps redownloading the same env.

**When snakemake creates conda envs:** The prefix is `{conda-prefix}/{hash}_` and snakemake checks for `.env_setup_done` marker. If you pre-create the env at that path and touch the marker, snakemake skips creation.

## 54. `--no-conda` fallback when conda is broken

When conda env creation fails persistently (e.g. conda 26.x TypeError, broken plugins, network issues), bypass snakemake's `--use-conda` entirely:

```bash
# 1. Pre-create a consolidated bin directory with all needed tools
CONSOLIDATED=/path/to/output/.conda/bin
mkdir -p "$CONSOLIDATED"
ln -sf /path/to/star_env/bin/STAR "$CONSOLIDATED/STAR"
ln -sf /path/to/trim_galore_env/bin/trim_galore "$CONSOLIDATED/trim_galore"
# ... link all tools ...

# 2. Run snakemake directly without --use-conda
export PATH="$CONSOLIDATED:$PATH"
cd /path/to/output/workflow_dir
snakemake -s /path/to/subworkflow.smk \
    --configfile /path/to/raw.json \
    --cores 20 \
    --rerun-triggers input
```

**Key differences from normal run:**
- No `--use-conda`, `--conda-prefix`, `--conda-frontend` flags
- `PATH` must include all tool binaries
- Conda yaml files in rules are ignored (no env activation)
- JAVA_HOME may need to be set for tools like fastqc

**When to use:** As a last resort after exhausting conda fixes. The `conda:` directives in .smk files become no-ops without `--use-conda`.

## 55. Subworkflow preamble MUST define ROOT_DIR

Every subworkflow .smk needs `ROOT_DIR` in its preamble, not just in module config dicts. Without it, `decoy_database_config = {"ROOT_DIR": ROOT_DIR, ...}` raises `NameError`.

```python
# REQUIRED in every subworkflow preamble:
shell.prefix("set -x; set -e;")
from snakemake.logging import logger
import os

ROOT_DIR = config.get("ROOT_DIR", ".")   # ← MUST have this
indir = config.get("indir", "data/fastq")
outdir = config.get("outdir", "output")
# ...
```

**Why it's easy to miss:** Modules define ROOT_DIR via `common.smk`, so subworkflow authors assume it's inherited. But subworkflow .smk files are NOT modules — they don't include common.smk. Each subworkflow must define ROOT_DIR from config.

**Detection:** Grep for `\"ROOT_DIR\": ROOT_DIR` in config dicts, then verify `ROOT_DIR = config.get` appears earlier in the file.

## 56. Test meta files must use local paths, not server-specific paths

Test meta files (`assests/test/meta_*.tsv`) with hardcoded paths from other servers (e.g. `/rna_seq_1/luoshg/...`) fail on any other machine. The MetadataUtils checks `os.path.exists()` on fastq paths — non-existent paths cause all samples to be skipped silently.

**Fix:** Update all test meta files to use paths under `assests/test/data/fastq/`:
```python
# In test meta files, use relative paths that the test framework generates:
# fastq_1 → assests/test/data/fastq/{sample_id}_1.fq.gz
# fastq_2 → assests/test/data/fastq/{sample_id}_2.fq.gz
```

Create touch files at those paths (empty files, just need to exist for `os.path.exists()` check).

**Detection:** After `--test all`, if a workflow reports 0 samples or "have no fastqs, skip it", check the meta file paths.

## 53. `run<Workflow>()` must populate outfiles — empty list = no-op

Every `run<Workflow>()` function in `run.py` MUST build the `outfiles` list. An empty `outfiles = []` means `rule all: input: outfiles` has zero targets, and Snakemake does nothing (silently succeeds with 0 jobs).

**Pattern:** Iterate `samples_info_dict` to build per-sample outputs, then append aggregate outputs:
```python
outfiles = []
for sid in paired_samples:
    outfiles.append(f"{outdir}/QC/1_raw_fastqc/{sid}/fastqc.raw.txt")
    outfiles.append(f"{outdir}/common/2_trimmed_fastq/{sid}/{sid}_1.fq.gz")
    outfiles.append(f"{outdir}/common/3_raw_bam/{sid}/{sid}.bam")
if paired_samples:
    outfiles.append(f"{outdir}/counts/all_paired_featureCounts.tsv")
datajson["outfiles"] = outfiles
```

**Verification:** After running, check that snakemake reports N > 0 jobs in the DAG. If it reports "Nothing to be done", outfiles is empty.

## 43. Batch conversion completeness — verify ALL files, not just the first batch

When doing batch refactoring (e.g. shell: → run:, adding conda:), **verify the entire codebase after each batch**, not just the files you modified. The user will catch missed files: "你确定你转换完了吗" (are you sure you finished converting?).

**Common miss patterns:**
- Files with `conda:` already present get skipped (but they still need shell: → run:)
- Subdirectory modules (`hisat2/polygenomes/`, `hisat2/ncRNAseq/`) have different paths
- Files modified by subagents may not be checked if the subagent timed out

**Verification command after batch conversion:**
```bash
# Count remaining violations
find . -name "*.smk" -exec grep -l "    shell:" {} \; | wc -l
# List them
find . -name "*.smk" -exec grep -l "    shell:" {} \; | sort
# Check missing include
find . -name "*.smk" -exec sh -c 'grep -q "run:" "$1" && ! grep -q "include.*common" "$1" && echo "$1"' _ {} \;
```

**Rule:** After any batch operation, run the verification grep. If count > 0, fix ALL remaining files before reporting completion.

## 47. Per-workflow path injection — recursive _inject() for ALL fields

**Key insight (user-corrected):** Inject ALL path-like fields recursively, not just genome.*. This handles Params.arriba.blacklist, Procedure.gatk, etc.

**In `execute_workflows`, per-workflow:**

```python
def _is_path(val):
    if val is None: return True
    if not isinstance(val, str): return False
    if "/" in val: return True
    return False

def _inject(cfg, prefix, wf_extra):
    for field, val in cfg.items():
        dotted = f"{prefix}.{field}" if prefix else field
        if isinstance(val, dict):
            _inject(val, dotted, wf_extra)
        elif _is_path(val):
            wf_extra[dotted] = base_paths.get(dotted, _make_test_path(field, test_data, genome))

wf_extra = {}
_inject(workflow_config, "", wf_extra)
```

**Why recursive `_inject()`:**
- Handles ALL nesting: top-level, genome.*, genome.GRCm39.*, Params.*, Procedure.*
- No manual flat-vs-nested branching needed
- New workflows with unknown fields are handled by `_is_path` fallback

**Why `_is_path` fallback:**
- New workflows may have genome fields not in any schema
- Heuristic: null or contains "/" → treat as path
- Empty string, numbers, booleans → not paths

## 47b. Preserve `design` syntax; add iterable comparison groups for many-to-many workflows

When workflows evolve from one-to-one comparisons to many-to-many comparisons, do not overload or rewrite `design`.

**Keep `design` syntax unchanged:**
- `design`: keep the existing role+contrast encoding (`ctr_X` / `exp_X` or `ctrl_X` / `exp_X`)

**Add a separate grouping layer:**
- store the user-facing comparison-side grouping label separately (`comparison_group`, or map the metadata `group` column onto that field)
- expose iterable comparison blocks such as `ComparisonGroup` from `src/common/type.py`

**Implementation pattern:**
- Parse `design` into `(DesignRole, contrast)`
- Group all samples by `contrast`
- For each contrast, build one iterable comparison block containing:
  - `ctr_sample_ids`
  - `exp_sample_ids`
  - optional `ctr_group` / `exp_group`
- Return those comparison groups from `MetadataUtils.run()` so callers can iterate all comparison blocks directly
- Keep derived `DesignPair` objects only as a compatibility layer for legacy one-control workflows

**Workflow adaptation rule:**
- New code should iterate `comparison_groups`
- Old code that still requires a single control may choose the first control temporarily, but MUST log that fallback explicitly
- Define shared metadata/runtime types in `src/common/type.py`, not ad hoc inside `MetaUtil.py`

Keep helper scripts CLI-driven; if a script is executed from a `run:` block, pass group/sample lists via args instead of importing `snakemake.config`.

## 57. STAR index sjdbOverhang=0 when no GTF

When building a STAR index WITHOUT a GTF (e.g. smallRNA FASTA index for star_3pass pass2), STAR requires `--sjdbOverhang 0`. The default `sjdbOverhang=100` causes:

```
EXITING because of FATAL INPUT PARAMETER ERROR: when generating genome without annotations
do not specify >0 --sjdbOverhang
```

**Fix in `star.smk` `star_index` rule params:**
```python
sjdbOverhang = config.get('Params',{}).get('STAR', {}).get('sjdbOverhang') or (100 if gtf else 0),
```

This reads: use configured value if set, otherwise 100 when GTF exists, 0 when no GTF.

## 58. star_3pass path chain: star.smk output vs star_3pass.smk input

The `star_align` rule in `star.smk` renames output to `.bam`:
```python
# star.smk star_align output
bam = outdir + "/{sample_id}/{sample_id}.bam"
```

But `star_3pass.smk` rules originally expected `.Aligned.sortedByCoord.out.bam`. ALL input paths in `star_3pass.smk` must use `.bam`:

```python
# star_3pass.smk — CORRECT
input:
    bam = outdir + "/pass1/{sample_id}/{sample_id}.bam",          # NOT .Aligned.sortedByCoord.out.bam
    bai = outdir + "/pass1/{sample_id}/{sample_id}.bam.bai",
```

Apply this fix to: `star_3p_extract_smallrna`, `star_3p_pass3a_extract`, `star_3p_merge` (noncanonical input).

## 59. star_3pass: BAM→FASTQ conversion rules needed for pass3a/pass3b

The star_3pass pipeline requires converting pass2 BAM to FASTQ for pass3a (mapped reads) and pass3b (unmapped reads). The STAR module doesn't handle this — add two rules to `star_3pass.smk`:

```python
rule star_3p_pass2_mapped_to_fq:
    input:  bam = outdir + "/pass2/{sample_id}/{sample_id}.bam"
    output: fq  = outdir + "/pass2_fq/{sample_id}/{sample_id}.single.fq.gz"
    # samtools view -F 4 (mapped) | sort -n | fastq | gzip

rule star_3p_pass2_unmapped_to_fq:
    input:  bam = outdir + "/pass2/{sample_id}/{sample_id}.bam"
    output: fq  = outdir + "/pass2_unmapped_fq/{sample_id}/{sample_id}.single.fq.gz"
    # samtools view -f 4 (unmapped) | sort -n | fastq | gzip
```

Then in ncRNAseq.smk:
- pass3a indir = `{outdir}/common/3_raw_bam/pass2_fq`
- pass3b indir = `{outdir}/common/3_raw_bam/pass2_unmapped_fq`
- All pass2/3a/3b samples must be in `single_samples` (reads are SE after extraction)

## 60. star_3pass merged BAM is single-end → featureCounts SE mode

After the 3-pass pipeline, the merged BAM contains single-end reads (extracted and re-aligned as SE). featureCounts MUST use SE mode:

```python
# In subworkflow (ncRNAseq.smk):
fc_paired = [] if aligner == "star_3pass" else paired_samples
fc_single = paired_samples + single_samples if aligner == "star_3pass" else single_samples

featureCounts_config = {
    "paired_samples": fc_paired,
    "single_samples": fc_single,
    ...
}

# In run.py run<Workflow>():
aligner = datajson.get("Procedure", {}).get("aligner", "star")
if aligner == "star_3pass":
    outfiles.append(f"{outdir}/counts/all_single_featureCounts.tsv")
else:
    if paired_samples:
        outfiles.append(f"{outdir}/counts/all_paired_featureCounts.tsv")
```

## 61. Python dict value capture timing in subworkflow config dicts

When a subworkflow creates module config dicts, Python captures variable values at dict creation time, NOT at module import time. If derived paths are set AFTER the config dict is created, the dict will have the original (often `None`) values.

**Wrong (derived paths defined after config dict):**
```python
elif aligner == "star_3pass":
    star_pass2_config = {"genome": {"fasta": smallrna_fasta}}  # smallrna_fasta is still None!
    # ... 100 lines later ...
    smallrna_fasta = f"{outdir}/genome/smallrna/smallrna_genes_flank.fa"  # TOO LATE
```

**Correct (define derived paths FIRST):**
```python
elif aligner == "star_3pass":
    smallrna_fasta = f"{outdir}/genome/smallrna/smallrna_genes_flank.fa"
    smallrna_bed = f"{outdir}/genome/smallrna/smallrna_genes.bed"
    smallrna_star_index = f"{outdir}/genome/smallrna/star_index"
    # THEN create config dicts that reference these variables
    star_pass2_config = {"genome": {"fasta": smallrna_fasta}}
```

Also remove any duplicate definitions later in the code that would shadow the correct values.

## 62. star_3pass.smk include path is TWO levels up

`star_3pass.smk` lives at `modules/star/star_3pass/star_3pass.smk`. The include must go up TWO levels to reach `modules/common/`:

```python
include: "../../common/common.smk"   # star_3pass/ → star/ → modules/ → common/
```

NOT `"../common/common.smk"` (which resolves to `modules/star/common/common.smk` — doesn't exist).

## 63. featureCounts_result missing `/` separator

The `featureCounts_result` rule concatenates `outdir + "filename"` without `/`:

```python
# BUG: produces ".../countsall_paired_featureCounts.tsv"
input:
    paired = outdir + "all_paired_featureCounts.tsv",

# FIX:
input:
    paired = outdir + "/all_paired_featureCounts.tsv",
```

Also add `output: touch(outdir + "/featureCounts.done")` so Snakemake has a sentinel for up-to-date checking.

## 64. Copy-paste rule prefix contamination

When copying subworkflow code from another workflow, rule alias prefixes must be updated:

```python
# BUG: copied from PeakCalling.smk
use rule fastqc from fastqc_raw as PeakCalling_fastqc_raw
use rule trimming_Paired from trim_galore as PeakCalling_trimming_Paired

# FIX:
use rule fastqc from fastqc_raw as ncRNAseq_fastqc_raw
use rule trimming_Paired from trim_galore as ncRNAseq_trimming_Paired
```

**Detection:** `grep "as [A-Z]" subworkflow/<wf>.smk | grep -v "as <WfName>_"`

## 65. Conda `TypeError` workaround — --no-conda fallback

When conda 26.x fails with `TypeError('expected str, bytes or os.PathLike object, not NoneType')` during `conda create` (especially for Python-dependent packages like cutadapt/trim-galore), bypass conda entirely:

```bash
# Pre-create consolidated bin directory with all tools
CONSOLIDATED=/path/to/output/.conda/bin
mkdir -p "$CONSOLIDATED"
ln -sf /path/to/star_env/bin/STAR "$CONSOLIDATED/STAR"
ln -sf /path/to/trim_galore_env/bin/trim_galore "$CONSOLIDATED/trim_galore"
# ... link all tools ...

# Run snakemake directly without --use-conda
export PATH="$CONSOLIDATED:$PATH"
export JAVA_HOME="/path/to/jvm"
snakemake -s /path/to/subworkflow.smk --configfile raw.json --cores 20 --rerun-triggers input
```

Non-Python envs (STAR, samtools, bedtools) succeed. Pre-create those via `conda create --no-deps`. For Python tools, use pip into existing envs + wrapper scripts.

## 32. Examine existing outputs before creating new reports

## 66. DESeq2 output file variants: .tsv (Ensembl ID) vs .name.tsv (gene_name) - downstream modules must pick the right one

DESeq2's `DESeq2.r` writes results as `TEcount_Gene.tsv` with Ensembl gene_id as rownames (via `write.table(..., col.names=NA)`). Then `gene_id2name.py` (called as `cmd3` in `DESeq2.smk`) converts this to `TEcount_Gene.name.tsv` with a `gene_name` first column and no rownames.

**Different downstream analyses need different variants:**
- **GO/KEGG enrichment** (`clusterProfiler::bitr`): needs `gene_name` column -> use `.name.tsv`. `bitr(fromType="SYMBOL")` requires gene symbols, not Ensembl IDs.
- **GSEA** (`fgsea`): needs Ensembl `gene_id` as rownames -> use raw `.tsv`. The `GSEA_prepare()` function does `rownames_to_column("gene_id") %>% left_join(anno, by="gene_id")` where `anno` has `gene_id` (Ensembl). Using `.name.tsv` here silently produces zero rows because gene_name != gene_id in the join.

**Verification:** Trace the R script's column expectations:
```r
# gsea.r reads: rownames(df) <- df[[1]]  -> first column becomes rownames
# If first column is "gene_name" (from .name.tsv), rownames are gene symbols
# Then left_join(anno, by="gene_id") fails because anno$gene_id is Ensembl
```

**When wiring a new module after DESeq2:** Always check whether the R script expects Ensembl IDs (use `.tsv`) or gene symbols (use `.name.tsv`). This is a path-chain correctness issue, not a style preference.

## 67. Conditionally enabling an optional module in a subworkflow

When a module is optional (e.g., function analysis after DESeq2), gate it behind an `enabled` flag in the subworkflow:

```python
if config.get("Params", {}).get("function", {}).get("enabled", False):
    logger.info("Function analysis enabled (GO/KEGG + GSEA)")
    function_config = {
        "ROOT_DIR": ROOT_DIR,
        "indir": DESeq2_config["outdir"],      # chain from upstream
        "outdir": f"{outdir}/function",
        "logdir": logdir,
        "group_pairs": config.get("Params", {}).get("DESeq2", {}).get("group_pairs"),
        "genome": {"geneIDAnno": config.get("genome", {}).get("geneIDAnno")},
        "Params": {"function": config.get("Params", {}).get("function", {})}
    }
    module function:
        snakefile: "../modules/function/function.smk"
        config: function_config
    use rule function_go_kegg from function as RNAseq_function_go_kegg
    use rule function_gsea from function as RNAseq_function_gsea
```

Key points:
- Default `enabled: false` in config JSON so existing runs are unaffected
- `group_pairs` is passed through from `Params.DESeq2.group_pairs` so the module knows which comparison pairs exist
- In `run.py`, conditionally append function outputs to `outfiles` only when enabled
- The module's `indir` chains from `DESeq2_config["outdir"]` (same pattern as all path chains)

For the full function module integration pattern (go-kegg.r CLI, gsea.r CLI, wildcard matching, config/schema/run.py changes), see `references/deseq2-to-function-module-chain.md`.
