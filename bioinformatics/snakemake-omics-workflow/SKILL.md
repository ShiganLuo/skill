---
name: snakemake-omics-workflow
description: Add new modules, subworkflows, and pipelines to the Omics Snakemake project — including porting from Nextflow
---

# When to use

- User asks to implement a new workflow/pipeline in the Omics Snakemake project
- User asks to port a Nextflow (nf-core) pipeline to Snakemake
- User asks to add a new tool module to `workflow/Omics/modules/`
- User asks to create a new subworkflow in `workflow/Omics/subworkflow/`
- User asks to tune per-rule threads/memory for a workflow via a `resources` config field (Fiberseq-style `rule_res` pattern) — see `references/per-rule-resources-pattern.md` for the full 4-layer procedure and measured-tuning workflow
- User asks to visualize/present a module's results inside the workflow (build rules + bin/ scripts in the owning module, wire into subworkflow + node.py outfiles + config JSON + READMEs) — e.g. the decoil ecDNA plots/IGV integration pattern (topology 分类解读与图例图形语言 → `references/decoil-topology-taxonomy.md`)
- User asks whether/how an ecDNA is transcribed from RNA-seq data (junction-read evidence ladder, circRNA disambiguation → `references/eccdna-expression-evidence.md`)
- User asks to run a single module directly (standalone with its own config JSON, or one module inside a workflow run) → `references/run-module-invocation.md` — includes the wrapper-Snakefile rule for modules without `rule all`

# Git push procedure for this repo (github.com over SSH)

The repo remote is SSH; direct `git push` hangs until the SOCKS proxy is
configured. Sequence: check `git config core.sshCommand`; if unset, set
`git config core.sshCommand "ssh -o ProxyCommand='nc -X 5 -x 127.0.0.1:1080 %h %p'"`
(SOCKS proxy on 127.0.0.1:1080 — GFW blocks github SSH; campus portal must
be authenticated first, see memory). Verify reachability once with
`timeout 15 ssh -o ProxyCommand=... -T git@github.com` before pushing.

If push is rejected (fetch first): `git fetch` and inspect BOTH directions
(`main..origin/main` and `origin/main..main`) — this repo is shared across
sessions and remote is often dozens of commits ahead. Rebase, resolve
conflicts conservatively (in `run.sh` example-command blocks, prefer the
remote's commented-out form and fold local edits into it as comments),
`git add <file> && git -c core.editor=true rebase --continue`, then push.
Do not merge or force-push unless the user asks.

Commit style: follow existing history — `feat(scope):`/`fix(scope):` prefix,
English or Chinese body both appear; match the most recent commits.

# User preference: proactive error fixing

When reviewing logs or identifying errors, **fix them immediately** — do not just report them. The user expects the agent to take initiative: find the error, understand the root cause, apply the fix, and verify. "I found an error but didn't fix it" is unacceptable. Always trace the error back to the source code and patch it.

**However, "proactive" does NOT mean "rash":**
1. **Understand the full pipeline first** — read the subworkflow, trace the DAG, know what each step does. "你完全不懂这个流程是什么" = unacceptable.
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
For deeptools enrichment heatmap module (multi-mode regions, computeMatrix, TSS BED generation): see `references/deeptools-heatmap-module.md`.
For peak-TE overlap analysis (bedtools intersect, TE class counting, grouped bar chart): see `references/chipseq-te-overlap-module.md`.
For ChIP-seq QC report PPT generation (data collection, 9-slide structure, pptxgenjs): see `references/chipseq-report-pptx.md`.
For Python-based report module (python-pptx + matplotlib, modular bin/ scripts): see `references/chipseq-report-python.md`.
For serving IGV track HTML via nginx (internal IP access, URL mapping): see `references/nginx-igv-serving.md`.
For IGV track module modes (single vs iCLIP, auto-grouping): see `references/igv-track-modes.md`.

For ncRNAseq small RNA three-pass STAR alignment (canonical gene extraction, multi-pass re-alignment, Tailer 3' end analysis): see `references/ncrna-three-pass-star.md`.
For SRA data download scripts (methods, meta file format, run.sh integration, prefetch `--max-size` and TLS pitfalls): see `references/sra-download-scripts.md`.

For converting legacy `shell:` rules to `run:` blocks (batch migration checklist, pitfalls, verification): see `references/shell-to-run-conversion.md`.
For config schema validation and test path generation via SchemaValidator: see `references/schema-validator.md`.

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

# Genome reference resolution — RNAseq pattern
genome = config.get("genome", {}).get("default")
genome_ref = config.get("genome", {}).get("references", {}).get(genome, {})

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
        "fasta": genome_ref.get("fasta")
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

**Pitfall — string values:** The value is always a string unless the arg has no value (→ `True`). Numeric config values like `binSize` will be set as string `"50"` not int `50`. If the workflow needs an int/float, the module's `config.get()` or `params:` must cast it.

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

## Pitfalls

1. **Matplotlib CJK fonts** — DejaVu Sans renders Chinese/Japanese as boxes. Use English labels for all matplotlib plot titles/axis labels. PPT text (python-pptx) renders correctly with CJK because it uses system fonts at display time.

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
    "genome": {"fasta": genome_ref.get("fasta")}
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

**Pipeline position:** AFTER Trim Galore, BEFORE STAR alignment:
```
1_raw_fastq → demultiplex (dedup_fastq) → Trim Galore (2_trimmed_fastq) → subsample (trimmed_subsampled_fastq) → STAR → ...
```

**Correction (2026-07-23):** User clarified subsample must be AFTER Trim Galore, not before. The subsample step operates on trimmed FASTQ, not raw FASTQ. Update `subsample_config.indir` to `trim_galore_config["outdir"]` and downstream STAR configs to `subsample_config["outdir"]`.

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
- Logging: `main()` initializes a module-global logger via `setup_logger` from `src/common/util/LogUtil.py`; functions never take a `logger` parameter — they use the module-global logger. Log the full URL and full command line of every external call, and never swallow child-process error lines (pipe stderr into the log stream). CLI `--log` must be optional: when omitted, log to stdout instead of erroring — `setup_logger(name, log_file=str(args.log) if args.log else None, stream=None if args.log else sys.stdout)`. Never `str(args.log)` on an optional arg unguarded: `str(None)` opens a log file literally named `None`.

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

## 55. `__file__` in module .smk is WRONG in Snakemake 9 — use `workflow.current_basedir`

Inside a `module X: snakefile: ...` loaded .smk, `__file__` resolves to
`.../site-packages/snakemake/workflow.py`, NOT the module's own path (verified
by debug print in dry-run, 2026-09-30). `os.path.dirname(__file__)` silently
gives the snakemake install dir. Correct API:

```python
MODULE_DIR = str(workflow.current_basedir)   # dir of the currently-parsed .smk
```

`workflow.basedir` = main snakefile dir (NOT the module dir). Always verify
module-dir resolution with a temporary `print(..., file=sys.stderr)` + dry-run
before relying on it.

## 56. decoil module (PacVar eccDNA) — CLI gotchas, all verified in decoil.sif 2.0.2

- `decoil reconstruct` has NO `--threads` flag (argparse rejects it, exit 2).
- VCF must be plain text — decoil uses `open()`, .vcf.gz → UnicodeDecodeError 0x8b.
- pbsv VCF needs conversion to sniffles1 style: INFO STRANDS/CHR2/END(BND) +
  FORMAT DR/DV (pbsv has GT:AD:DP only). Converter ships as
  `modules/decoil/bin/pbsv2decoil.py <in.vcf[.gz]> <out.vcf>` located via
  `os.path.join(ROOT_DIR, "modules", "decoil", "bin", "pbsv2decoil.py")`
  (project convention: bin/ + ROOT_DIR, NOT __file__ / current_basedir);
  the generated .sh runs it before `decoil reconstruct`.
- BND strand from ALT: `t[p[`→`+-`, `t]p]`→`++`, `]p]t`→`-+`, `[p[t`→`--`.
- decoil's own `pass_filter` skips ALL records with MATEID (BND pairs never
  enter the graph) — decoil-internal behavior, not a converter bug.
- Workflow: test the exact command in the SIF first (`singularity exec ...
  decoil reconstruct ...` to a tmp outdir), THEN patch the .smk. The image
  test surfaced both the gzip and pbsv-field issues that dry-run cannot.

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

## 48. get_star_index os.path.exists breaks dry-run

`get_star_index()` in `star.smk` checks `os.path.exists(index_dir + "/Genome")`. During `--dry-run`, no files exist → check always fails → falls back to `outdir + "/index"` → triggers unnecessary `star_index` rebuild or MissingInputException.

**Fix:** Remove the existence check. Always return `index_dir` if set. Snakemake handles DAG dependency resolution:

```python
def get_star_index(wildcards):
    star_index_dir = config.get('genome',{}).get('index_dir') or None
    if star_index_dir:
        return star_index_dir  # NO os.path.exists check
    return outdir + "/index"
```

**Impact:** Affects ALL workflows using STAR (RNAseq, ncRNAseq, PeakCalling, etc.). Any workflow with a pre-built STAR index will fail dry-run if the index directory doesn't exist yet on disk.

## 49. STAR unmapped reads not declared as outputs

`star_align` with `--outReadsUnmapped Fastx` produces `*.Unmapped.out.mate1/2` as side effects, but these aren't declared in `output:`. Downstream rules can't track them via the DAG.

**Fix:** Add unmapped files as additional outputs and touch if not produced:

```python
output:
    bam = outdir + "/{sample_id}/{sample_id}.bam",
    bai = outdir + "/{sample_id}/{sample_id}.bam.bai",
    unmapped_r1 = outdir + "/{sample_id}/{sample_id}.Unmapped.out.mate1",
    unmapped_r2 = outdir + "/{sample_id}/{sample_id}.Unmapped.out.mate2",
# In run block, after STAR execution:
f.write(f"test -f {output.unmapped_r1} || touch {output.unmapped_r1}\n")
f.write(f"test -f {output.unmapped_r2} || touch {output.unmapped_r2}\n")
```

**When to use:** Only for modules that configure `outReadsUnmapped: Fastx` (e.g. ncRNAseq pass2). For standard alignment, the touch creates empty sentinel files harmlessly.

## 50. Module config dict variable capture timing

When a subworkflow defines module config dicts, Python captures variable values at dict DEFINITION time, not at USE time. If a variable is `None` when the dict is defined but reassigned later, the dict still holds `None`.

**Real example (ncRNAseq):**
```python
smallrna_fasta = config.get("genome", {}).get("smallrna_fasta")  # → None

star_pass2_config = {
    "genome": {"fasta": smallrna_fasta}  # Captures None!
}

smallrna_fasta = f"{outdir}/genome/smallrna/smallrna_genes_flank.fa"  # Too late!
```

**Fix:** Always assign derived paths BEFORE defining config dicts that reference them. See `references/ncrna-three-pass-star.md` pitfall #6 for the full ncRNAseq example.

## 52. No conditional rule definitions in module .smk

**模块 .smk 中禁止 `if`/`else` 包裹 `rule` 定义。** This is also stated in `modules/modules.md` but agents keep violating it.

**Wrong:**
```python
if regions_cfg == "tss":
    rule generate_tss_bed:
        input: gtf = gtf,
        output: bed = outdir + "/_tss_regions.bed",
        ...
```

**Correct:** Define ALL rules unconditionally. Let Snakemake's DAG decide which rules to execute based on dependency chains. If nothing depends on `generate_tss_bed`, it won't run.

```python
rule generate_tss_bed:
    input: gtf = gtf or "/dev/null",  # safe fallback when gtf is None
    output: bed = outdir + "/_tss_regions.bed",
    ...
```

**Why:** Conditional rule definitions break:
- `use rule` imports in subworkflows (the rule doesn't exist when the condition is false)
- Static analysis and verification scripts
- The project's design principle: "模块应该定义所有可能的 rule，由 subworkflow 决定 use rule 哪些"

**When you need conditional logic:** Use input functions (e.g. `get_regions(wildcards)`) or runtime `if` inside `run:` blocks — both are fine. Only the `if` wrapping `rule` definitions is forbidden.

## 51. Module .json must include ALL config.get() keys — including genome.*

When a module .smk reads `config.get("genome", {}).get("gtf")` or similar nested keys, the module's .json config template MUST include the `genome` section with those keys. Omitting it breaks automated verification (`.json` key coverage check) and makes the module's config contract incomplete.

**Real example (deeptools_heatmap):** The .smk reads `config.get("ROOT_DIR")`, `config.get("indir")`, `config.get("outdir")`, `config.get("logdir")`, `config.get("samples")`, `config.get("bigwig_dir")`, `config.get("Procedure")`, `config.get("Params")`, AND `config.get("genome")` (for TSS mode GTF). The initial .json missed `genome`, which was caught by verification:
```python
config_keys = set(re.findall(r'config\.get\("(\w+)"', smk)) - {"ROOT_DIR"}
assert config_keys <= set(json.load(open("module.json")).keys())
# AssertionError: json missing: {'genome'}
```

**Fix:** After creating a module, run this check:
```bash
python3 -c "
import json, re
smk = open('module.smk').read()
mj = json.load(open('module.json'))
keys = set(re.findall(r'config\.get\(\"(\w+)\"', smk)) - {'ROOT_DIR'}
missing = keys - set(mj.keys())
if missing: print(f'ERROR: .json missing keys: {missing}')
"
```

**Rule:** Every top-level `config.get("X")` call in the .smk MUST have a corresponding `"X": ...` entry in the .json. This includes `genome`, `env`, `paired_samples`, `single_samples`, and any other config keys the module reads.

## 53. Empty schema.json breaks `generate_test_paths` in test mode

An empty `config/<Workflow>.schema.json` (0 bytes) causes `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` in `setup_test_args` → `SchemaValidator.generate_test_paths()`. The function iterates ALL `*.schema.json` files and calls `json.load()` on each — one empty file crashes the entire test run.

**Detection:**
```bash
for f in config/*.schema.json; do [ ! -s "$f" ] && echo "EMPTY: $f"; done
```

**Fix:** Write `{}` (minimal valid JSON) to any empty schema files:
```python
json.dump({}, open("config/<Workflow>.schema.json", "w"))
```

**Prevention:** When creating a new workflow, always write `{}` as the initial schema content, not an empty file.

## 54. Genome config must use nested `default` + `references` structure

**Wrong (flat):**
```json
"genome": {
    "fasta": "/path/to/genome.fa",
    "gtf": "/path/to/genes.gtf",
    "bowtie2_index_prefix": "/path/to/bowtie2/index"
}
```

**Correct (nested, RNAseq pattern):**
```json
"genome": {
    "default": "GRCm39",
    "references": {
        "GRCm39": {
            "fasta": "/path/to/mouse/genome.fa",
            "gtf": "/path/to/mouse/genes.gtf",
            "bowtie2_index_prefix": "/path/to/mouse/bowtie2/index"
        },
        "GRCh38": {
            "fasta": "/path/to/human/genome.fa",
            "gtf": "/path/to/human/genes.gtf",
            "bowtie2_index_prefix": "/path/to/human/bowtie2/index"
        }
    }
}
```

**Subworkflow pattern:**
```python
genome = config.get("genome", {}).get("default")
genome_ref = config.get("genome", {}).get("references", {}).get(genome, {})
# Use genome_ref.get("fasta"), genome_ref.get("gtf"), etc. in all module config dicts
```

**run.py pattern — auto-detect organism from metadata:**
```python
organisms = set()
for sample_id, sample_info in samples_info_dict.items():
    if sample_info.organism:
        organisms.add(sample_info.organism)
if len(organisms) == 1:
    organism = next(iter(organisms))
    if organism in ["Homo sapiens", "human"]:
        datajson["genome"]["default"] = "GRCh38"
    elif organism in ["Mus musculus", "mouse"]:
        datajson["genome"]["default"] = "GRCm39"
```

**Schema mirrors config:**
```json
"genome": {
    "default": { "type": "str", "required": true },
    "references": { "type": "dict", "required": true }
}
```

**Remove legacy `genomes` field:** Old configs may have `"genomes": ["mm"]` — remove it when migrating to nested structure.

## 57. gsva.py score semantics — KS ranks vs mean z-score

`modules/function/bin/gsva.py` produces TWO matrices (verified 2026-10-11, sign fixed):

- **`gsva_scores.tsv` (KS-based)**: within-sample rank walk (LOW→HIGH), `score = max|miss_frac - hit_frac|`; positive = gene set concentrated at the HIGH-expression end (GSVA/GSEA convention, fixed 2026-10-11; was inverted). Not classic GSVA — the old dead `kcdf` parameter was removed. Constitutive sets (e.g. DNA repair housekeeping) saturate at 0.5–0.86 in every sample with cross-sample span ≤0.19: the score is mostly a property of the SET, not the sample.
- **`gsva_mean_z.tsv` (mean per-gene z, the heatmap source)**: per-gene z on log2(TPM+1) across samples, averaged within the set; each row sums to 0 across samples. Reflects absolute expression changes — use this for sample comparisons ("pathway higher in A than B"). `--no-log2` if input already log-scale.
- **`gsva_heatmap.png` = mean-z heatmap** (declared rule output alongside gsva_scores.tsv). `plot_heatmap(values, path, title, value_label, row_scale)` is generic; row_scale=True gives row-z-scored view.
- **KS scores are rank-relative**: absolute 2–8 fold expression shifts move within-sample ranks only a few percent and get erased; mean-z preserves them. KS and mean-z can disagree in direction (relative rank vs absolute level are different questions) — say which metric a figure shows.
- **Gene-set means are hijacked by multi-copy families.** Reactome GMT sets contained 23–54% histone genes (H2bc*/H4c*) whose expression was 8–9.6 log2 in fibroblasts vs ~0–2.7 in ESCs (direction anomalous; suspected multi-mapping/pseudogene). They flipped the sign of stem-vs-fibro gaps in DSB/NHEJ/BER/Telomere/Chromosome sets (mean gap negative, median gap positive) and made all heatmap rows move together (same genes shared across sets). Always aggregate set scores by MEDIAN (or trimmed mean) and inspect gene-level distributions (mean vs median, histone/multi-copy fraction) before interpreting any set-level figure.
- **poly(A) vs total-RNA libraries are not comparable for non-polyA transcripts.** rRNA-depleted total-RNA libraries capture histone mRNAs (stem-loop, no polyA), sn/snoRNA, 7SL/RMRP; poly(A) libraries do not. Mixing them in one TPM panel makes multi-copy families explode in the total-RNA samples only and corrupts every set containing them. Fingerprint library type first: non-polyA ncRNA TPM (Rn7sk, Rpph1, RN7SL*, RMRP) near zero = polyA, percent-of-library = total-RNA. Same trap applies to relative-scale heatmaps: z-scored colors are panel-composition dependent — "same color" ≠ "same expression"; always cross-check absolute values before interpreting a figure.

## 58. New meta rows vs layout lists, and silent PE→SE degradation

`get_input_for_XenofilteR`/star.smk validate every sample against `paired_samples`/`single_samples` built when run.py parses the meta. Two failure modes when adding samples to an existing meta:

1. **`Sample X not defined in paired_samples or single_samples`** — the sample's fastq files did not exist when run.py built the layout lists (MetaUtil classifies SE/PE by actual files) or the lists are stale. Download the fastq first, then re-run run.py so raw.json/config are regenerated.
2. **PE data silently runs single-end** — if only mate-1 is on disk, the aligner accepts it unpaired (aligner log shows `100% unpaired`), losing half the data with no error. Before running on new samples, verify mate completeness: `ls *_2.fastq.gz | wc -l` must equal the number of PE samples; after alignment, grep the aligner summary for `unpaired`.

When appending rows to a project meta, copy the conventions of an existing row (data_id/design/contaminated_organism style) instead of deriving the schema from pipeline code — the user will redirect you to the existing row as the reference.

## 59. Don't re-implement IGV/UCSC rendering — feed files to modules/track/bin/track.py

`track.py` is the shared renderer: `--mode ucsc` takes a plain list of track
files (bigwig/bed/bedgraph) and writes UCSC track lines; `--mode igv` takes a
config JSON (reference fasta/index/cytobandURL, GTF tracks, publicPathMap,
js path) plus track files and renders the interactive HTML. To browse a new
result type, generate a config JSON and call track.py — never write a new
igv.js page. The `igv` config section lives in the workflow config (see
`config/PacVar.json` for the full key set: js/id/publicPathMap/fastaURL/
indexURL/cytobandURL/tracks).

Type detection pitfall (fixed in `_track_type`): non-bedgraph suffixes used
to be declared `type=bigWig` in ucsc track lines. `.bed`/`.bed.gz` now map
to `type=bed` — verify the emitted `track type=` line when feeding a new
file format to ucsc mode.

Also: ucsc track lines use RELATIVE `bigDataUrl` paths — the track file is
only meaningful relative to the directory layout it was generated in.

For the decoil ecDNA application (structure/plot/compare/igv/ucsc rules,
bin scripts, sif bind-mount quirks), see the decoil-visualization skill
(user-owned: needs `hermes curator adopt decoil-visualization` before
autonomous edits can land):

- `decoil_plot`(每样本):summary.txt + reconstruct.ecDNA.filtered.bed → 尺寸分布(log 直方图)+ topology 组成 + ecDNA 区域表。bin 脚本 `decoil_plot.py`,支持 `--mode single|compare`。
- `decoil_structure`(每样本):**先判断是否检测到 eccDNA 再画** —— filtered BED 无数据行(header-only 会抛 `pd.errors.EmptyDataError`,必须捕获)→ 输出 "No ecDNA detected" 占位图;检测到则按 circ_id 画环形结构。bin 脚本 `decoil_structure.py`,`Params.decoil.structure.{formats,max_per_fig}`,超过 max_per_fig(默认 12)自动分页 `.pN.<fmt>`。decoil 2.0.2 自身无 plotting 子命令(上游已注释掉),结构图必须自绘。**结构图必须带基因功能标注**(用户明确要求,纯坐标圈没有价值),4 层从外到内:基因名标签(癌基因紫色加粗,内置 panel 可 `--onco-genes` 换清单;被环化打断的基因名尾加 `*`)→ 基因条(红=intact 完整包含,橙=truncated 断点落在基因体内,判定:gene 区间未被单个 fragment 完整包含即 truncated)→ 片段主环(按染色体着色)→ 剂量环(内圈橙色,`--bw` 传 coverage bigwig,逐 bin 覆盖以全基因组均值(`load_bw_mean_coverage`)为 1x 基准 log 封顶 100x——**必须用固定 WGS 均值基准,按环内最大值归一化会使所有环看起来一样满**);中心 hub 显示 `N genes / N oncogene / N truncated`;配套输出 `decoil_structure_genes.tsv`(gene/status/onco/region/median_coverage/tpm,tpm 列预留表达耦合接口 `--tpm`)。rule 从 `config.genome.gtf` 传 `--gtf`、从 `bw_dir` 传 `--bw`;outfiles 需同时登记 png + genes.tsv。版式沿革:曾定稿为 decoil-viz 式三轨道线性,但用户后来重新起用并迭代**环形版 decoil_structure.py**(CGView 式:外 ruler 刻度 / 金色 coverage 环 / 基因轨道 / 中心 hub)——两套脚本并存,改哪套先确认用户在看哪张图;用户桌面上的 `a_circ9.png` 等散放 png 是拷贝件,验证渲染必须重跑产物后读 output/ 下的真身,不能用旧拷贝判断"没变"。环形版基因模型画法(多轮迭代收敛,改前先核对本条与 decoil_structure.py 现状):**对齐 `modules/sv/bin/utils/gene_model.py` 的画图惯例**——①内含子线只画在外显子间隔(exon[j].end→exon[j+1].start 逐段),不贯穿全基因,**虚线弧**(描边 Wedge width=0 + edgecolor + linestyle (0,(2.5,1.8));虚线是内含子的固有符号,与截断状态无关),线宽 INTRON_W=0.006 远细于 exon 块(EXON_W=0.075)——粗了会被误读成第二个块或独立圆圈;半径必须精确居中 r_lane-EXON_W/2(残留的历史 +0.007×2 偏移会让虚线贴内边缘,用户否定过);②链方向:**不画任何箭头/三角/taper**(用户明确抛弃)——固定尺寸箭头弧长约 7°,对 <400bp 的短基因是基因自身弧长的 7-20 倍,完全淹没外显子块;taper 方案(第一外显子收窄成尖)也试过被否,仍属变相箭头且引入跨 0kb 角度反转 bug;外显子全部为普通矩形块,方向信息不画。③外显子实心全高块,**每基因独立颜色**——基因名哈希基础色相 + 线性探测避开已用色相(固定调色板取模在基因数超过色数时必撞色),**按基因名缓存**:gene_color 对同一基因被调用两次(模型一次、标签一次),每次都注册色相会污染探测序列且两次可能返回不同色,缓存后同名恒同色;基因名标签同色;truncated 不再用橙色区分(橙金色系与 coverage 环同系不可辨),截断只由 `//` 表达。UTR = exon 带上**基因色 alpha=0.35 + 白描边 0.3** 的叠加(旧 white alpha=0.65 全覆盖视觉不可见,用户看不到等于没画);**不画 CDS 层**(DNA 图不是转录本模型,用户明确否定)。`//` 是基因级标记但必须做**真断点判定**:基因跨度端只有落在片段 clip 边界 ±2bp 内、或基因延伸越过片段末端(beyond fragment end,此时可见端就是片段边界)才画;落在环上完整序列的一端(如跨白缝长基因的另一端)不画——旧版"两端无条件各画一次"会把只被切一次的基因标成两处截断(用户否定)。所有 taper/角度分割运算先把弧段角度归一化到同一分支(e1n<e2n 则 +360)且 taper 长度不超过该 exon 自身弧宽,否则 Wedge theta1>theta2 被 matplotlib 逆时针补 360° 画成整环色带。图例:**基因结构元件(exon/intron/UTR/junction break)统一黑色 #1A1A1A**,coverage 保持金色;strand direction 条目已随箭头移除;junction break 只画两道斜杠不加底色方块。图例位置:画布右侧独立空白带(x≈1.38 起),canvas xlim 扩到 1.80 容纳;figsize 宽高比必须匹配数据范围比例(xlim 跨 3.35 / ylim 跨 2.85 → figsize 9.4×8.0),比例不符时 aspect equal 把环挤到画布一角、标签散布四角。基因名标签:**钉死在基因起点角度,永不沿角度移动**——短基因钉 5' 起点(名称对齐起点),长基因(弧 >90°)锚定弧中点(否则名称飘到长模型远端,名称-模型对不上);碰撞用**径向分层**解决——占位者记 (角度, ring),刻度 ring=0,新标签与同 ring 占位角度差 <20° 才升一环(每环 0.10R,起点 R+0.14,在刻度标签 R+0.055 之外);避让判定若不区分 ring(只看角度),ring 会空转到 max_iter,标签散布画布四角、环缩成一角;同 ring 角差 <20° 升环之外,相邻 ring 且角差 <5° 也算冲突(旋转文字宽度径向投影会压邻层标签)。**刻度自适应环长**:主刻度步长从 (5,10,20,25,50,100,...,5000) 列表选第一个使整环 ≤12 个主刻度的值,次刻度 5:1 细分无标签——固定 10/50kb 间隔在大环上标签挤成一团。极小外显子(<100bp)在 ~150kb 环上物理只有 1-3px,白色描边占满块体呈"白杠"——分辨率极限,不是 bug。**微型基因(全基因弧 <0.15°)强制分区渲染,不靠逐标签避让**(用户定稿):微基因整体移出基因 lane——圆点画在 hub 白圆(r=0.40)与最内基因 lane 之间的专用窄带(r≈0.46),名称画在刻度环外专属带(R+0.10+ring×0.09),微基因点/微基因名/大基因模型三者半径互斥,任何角度都不挤占对方空间。**zorder 覆盖陷阱**:hub 是后画的白底 Circle(zorder=6),同 zorder 的先画元素会被整体盖住——元素"代码画了、图上没有"先查 zorder 与后画白色 patch 的覆盖关系,用 matplotlib spy 取证(monkeypatch Axes.plot 记录 data 坐标 + transData 像素坐标),不要靠看图反复猜。**不给标签画引线(leader line)**(用户定性为设计失误):名称与模型对应不清时,修元素本身的可见性与归属,不加横跨 coverage 环的连线。改环形版代码先读懂现有绘制逻辑再动手,删除已失真的旧注释(描述旧行为的注释会误导后续修改),不要在失真注释下叠补丁。**fragment join 不画专门刻度**:覆盖环白色间隙 + 截断基因 // 已双重表达,第三种标记(珊瑚色刻度)是冗余,用户明确删过。改完必跑渲染验证+视觉放大检查——迭代期用合成 fixture(小 BED + 手写 GTF 片段,含完整基因、带内部 exon 的截断基因、贴边 UTR 各一,`apptainer exec` 秒级出图)先验证几何与语义,再上真实数据核对计数。环形版的标签布局教训(环绕感知贪心、径向堆叠、SAT 碰撞检测须在 set_xlim 之后跑、旋转文字 AABB 高估须反转投影求真实长、外显子/基因体先裁剪到片段范围防巨弧、长内含子画双斜杠断线、微型基因强制分区画圆点而非不画)详见 decoil-visualization skill;线性布局天然免疫这些几何坑。of max or min must be given`——一律用 `np.clip(arr, min, None)` 函数形式。**输出形态(用户定稿):一个 ecDNA 一张独立大图**——`--one-file-per-cycle` 生成 `<prefix>_circ<id>.<fmt>`(8×8 in 方图,适合 PPT 单页展示),`Params.decoil.structure.one_file_per_cycle` 默认 true;汇总网格图 rule 输出声明的 `decoil_structure.png` **仍必须生成**(Snakemake MissingOutputException 会挂掉 rule),单环图作为附加产物;per-cycle 输出目录不存在会 FileNotFoundError,先 makedirs。
GTF 功能层加载:主入口 `load_gtf_all_features(path)` **单遍扫描**同时返回 genes/exons/utrs 三个 DataFrame(大 GTF 上 4 遍扫描 5.8s → 单遍 3.1s;**不加载 CDS**,用户明确否定);通用接口 `load_gtf_features(path, feature_type)` 第二参接受 str 或 tuple 保留备用。gffutils 建库在这个场景是负优化:151 万行 GTF 建库 145s(1.45GB .db)+ 查询 9.8s,对比单遍解析 3.1s——只有"同库多次增量区间查询"才值得建库,每次全量加载不要用。decoil.sif 里没有 gffutils,脚本顶层 `import gffutils` 会直接 ModuleNotFoundError——必须 try/except 可选导入(create_db 在 decoil_structure 中从未被调用)。容器内跑法:`apptainer exec --bind /data/pub:/data/pub /data/pub/<USER>/Database/env/decoil/decoil.sif python <script>` + 完整 CLI 参数(sample/ecdna-bed/summary/gtf/bw/o/max-per-fig/one-file-per-cycle/-f png)。
- decoil 输出文件语义(源码核实):`summary.txt` 的 `label=ecDNA` **纯尺寸判定**——size > 0.1 Mb(`ECDNA_MINSIZE`),与复杂度无关;`reconstruct.ecDNA.filtered.bed` = label=ecDNA 且 score ≥ FILTER_SCORE(源码默认 0,项目 config 设 5,故 summary 有 ecDNA 行而 filtered BED 缺环时先查 filter_score);`graph.gpickle` = pickle 的 MultiGraph 片段组装图(中间产物,调试用);`reconstruct.json` = 最全结果(score/conf/topology 细节),summary 和 bed 均由它派生;`reconstruct.links*.txt` = 环内 fragment 首尾连接,给环形可视化工具用;`reconstruct*.fasta` = 环序列。score(estimated_proportions)≈ 环丰度;structure 图的数据源链 = summary.txt(ecDNA 行)⇔ reconstruct.ecDNA.filtered.bed,画前核对两者 circ_id 一致。
- `decoil_compare`(聚合):跨样本 counts/尺寸叠加/topology 堆叠 + shared/unique 区域表(键 = 完整坐标 `chr:start-end` 字符串,不缩写)。
- `decoil_igv`(每样本):生成 track.py igv 模式所需 config(`decoil_igv_config.py`)+ 调 track.py --mode igv → 交互 HTML,locus 默认 = 最大 ecDNA 区域。
- `decoil_ucsc`(每样本):track.py --mode ucsc 生成 UCSC track 线文件(coverage bigwig + ecDNA BED)→ `visualization/ucsc_track.txt`。
- decoil.sif 里有 matplotlib+pandas,但 apptainer exec 必须显式 `--bind /data/pub:/data/pub`,否则模块路径不可见。
- 出图后用视觉检查渲染质量(标签重叠/截断/乱码),并与 summary.txt 原始计数核对,再报告完成。
- 展示形态定稿:一个 ecDNA 一张独立大图(`--one-file-per-cycle`,8×8 in 方图,`<prefix>_circ<id>.<fmt>`,`Params.decoil.structure.one_file_per_cycle` 默认 true)——多环聚合网格对密集标签天然不利,per-cycle 大图优先,网格页只作 rule 输出的汇总图。注意:per-cycle 模式下汇总 png 仍必须生成(rule 声明的输出,缺了报 MissingOutputException);输出目录不存在先 makedirs。
- ecDNA 片段合并:BED 按 (sample_id, circ_id) groupby 取 min(start)/max(end);不同样本起点差 1bp 会使 shared 表把它们判为 unique——是坐标本身差异,不是 bug。
- decoil 数据源链:结构图数据源 = summary.txt(label=ecDNA 行)⇔ reconstruct.ecDNA.filtered.bed;label 判定纯尺寸(>0.1Mb 即 ecDNA),config filter_score=5(源码默认 0)——summary 有 ecDNA 行而 filtered BED 缺环时先查 filter_score。graph.gpickle=片段组装图(中间产物),reconstruct.json=最全结果,links*.txt=环内 fragment 连接(给可视化工具),fasta=环序列。

## 60. Adding a rule to an existing multi-rule module — 5-surface sync + wildcard verification

A new rule in `modules/<tool>/<tool>.smk` is not live until ALL of these are updated — the module import does not pick up new rules automatically:
1. module `.smk` — rule definition
2. module `.json` — `Params.<tool>.<rule>` subfields (per-rule param pattern, see config conventions)
3. subworkflow `<Workflow>.smk` — `use rule <rule> from <tool> as <Workflow>_<rule>`
4. `node.py` — outfiles entry for the new output
5. workflow config template `config/<Workflow>.json` — only when params deviate from module defaults

Verification, in order:
- Dry-run via `run.py -m ... -w <Workflow> --dry-run` (run.py needs snakemake+pandas — use the conda env that has both, e.g. `smk`) and grep the output for the new alias. Missing `use rule` shows up here as zero jobs for the new rule, not as an error.
- Real-run just the new rule: wildcarded rule names cannot be CLI targets (`Target rules may not contain wildcards`) — pass the concrete output file paths instead: `snakemake -s subworkflow/<W>.smk --configfile <outdir>/raw.json ... /abs/path/{sample}/visualization/new_output.png`.
- Re-running after editing a rule: mtime triggers may report "Nothing to be done" even when the rule code changed — `touch` an upstream input (e.g. the module's summary.txt) to force the rebuild, or verify the change landed by inspecting the freshly generated `.sh` script in the output dir (it contains the exact cmd the rule built — its content proves which code version ran).
- If `run.py --test <wf>` fails, check whether the failure is in the test fixture (meta columns, schema files) before blaming your change — fixture failures are independent of module edits.

- Per-cycle side-outputs alongside a declared summary output: if a rule gains a mode that emits extra files but stops writing the declared output (e.g. `--one-file-per-cycle` skipping the summary grid PNG), Snakemake fails with `MissingOutputException` — keep emitting the declared output AND the new side files, or add the side files to `output:`.
- Rule-code edits that don't change input/output mtimes are invisible to `--rerun-triggers mtime`: `touch` an upstream input (summary.txt) AND pass `--forcerun <Rule>` (or delete the declared outputs) to actually re-execute. Verify which code version ran by reading the freshly generated `.sh` script in the output dir.


Two structural rules for workflow/module config JSON, both user-enforced:

1. **Shared cross-module config goes ONE LEVEL UNDER Params, not at top level.**
   `igv` (browser reference/tracks, consumed by track/igv/decoil-igv rules)
   lives at `Params.igv` — matching PeakCalling/CLIP. Do NOT put it at the
   config top level. Subworkflows forward it as
   `"igv": config.get("Params", {}).get("igv", {})` inside the module config
   dict; modules read `config.get("Params", {}).get("igv", {})`.

2. **Multi-rule modules nest per-rule params under the module's parent key.**
   Do NOT invent a sibling flat key (e.g. `Params.visualization`) for one
   rule's params of a module whose params live under `Params.<module>`.
   Pattern: `Params.<module>.<rule>.*` for rule-specific params
   (`Params.decoil.{reconstruct, plot, compare, igv.locus}`), shared params
   (`formats`) at the parent `Params.<module>` level. Rules resolve via a
   fallback helper (rule subfield → parent field → default) so legacy flat
   keys keep working.

**Sync ALL THREE config surfaces when adding params:** module template
`modules/<tool>/<tool>.json`, workflow template `config/<Workflow>.json`, and
the subworkflow's forwarding dict. Adding to only the module template makes
`config.get(...)` silently fall back to code defaults in real runs — the
workflow template key check (pitfall #51 pattern) must cover the workflow
template too, not just the module template.

## 61. Debug the script copy that actually ran — workflow trees are forked

Per-project copies of `workflow/Omics` on this host diverge silently (two
copies once differed by 216 lines while believed identical). When an
application log carries a traceback: first resolve WHICH script the job
ran — read the generated runner `.sh` in the output dir (it embeds the
python script path) or the snakemake command line in the log — then
`md5sum`/`diff` that file against your working copy before reasoning about
line numbers or patching. Patch the copy that executed, then port the fix
to sibling copies (diff them; never assume they match). A fix landed only
in an unexecuted fork changes nothing for the failing run.

Related scRNAseq.py bug pattern (applies to any forked module script):
AnnData exposes NO `.loc` accessor — `adata.loc[...]` raises
AttributeError; write `adata.obs.loc[...]`. Such restore-block bugs hide in
iteration ≥ 2 paths: a run can annotate every cluster cleanly, then crash
when a discontinuous cluster triggers re-clustering — verify fixes with
data that exercises the second iteration, not just a clean first pass.
When restoring raw counts for re-clustering, also re-attach `obsm`
embeddings (UMAP…) from the saved copy so per-iteration plots stay
comparable.

## 32. Examine existing outputs before creating new reports
