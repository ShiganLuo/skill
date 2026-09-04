---
name: omics-workflow-data-prep
description: Prepare data and config for Omics Snakemake workflows (PeakCalling, RNAseq, CLIP, etc.) — JSON config, meta.tsv, directory setup.
tags: [bioinformatics, snakemake, chipseq, peak-calling, omics, ngs]
triggers:
  - user asks to prepare data for Omics workflow
  - user mentions PeakCalling, ChIP-seq, CLIP, or other Omics subworkflows
  - user has fastq files and needs to configure a Snakemake pipeline
---

# Omics Workflow Data Preparation

Prepare input data and configuration for the Omics Snakemake workflow system.

## Workflow Structure

The Omics repo lives under `workflow/Omics/` and contains:
- `config/<WorkflowName>.json` — per-workflow config
- `subworkflow/<WorkflowName>.smk` — Snakemake subworkflow
- `modules/<tool>/<tool>.smk` — reusable tool modules

## Step 1: Identify Samples from Raw Data

Scan the raw data directory for sample folders. Each folder typically contains:
- `<Sample>_1.fq.gz` (read 1)
- `<Sample>_2.fq.gz` (read 2, for paired-end)
- `MD5.txt`

Group samples into IP/Input pairs by naming convention (e.g., `Rpp21IP` / `Rpp21Input`).

## Step 2: Confirm Organism

**PITFALL: NEVER assume organism from directory names.** The working directory may say `GRCh38` while the data is actually mouse. Always ask the user to confirm:
- Mouse: genomes=`["mm"]`, genome_size=`"mm"`, fasta under `mouse/GRCm39/`
- Human: genomes=`["hg38"]`, genome_size=`"hs"`, fasta under `human/GRCh38/`

Reference genome paths on this system:
- Mouse: `/disk5/luosg/Reference/GENCODE/mouse/GRCm39/GRCm39.primary_assembly.genome.fa`
- Human: `/disk5/luosg/Reference/GENCODE/human/GRCh38/GRCh38.primary_assembly.genome.fa`

## Step 3: Write config/<WorkflowName>.json

Required fields for PeakCalling:

```json
{
    "ROOT_DIR": "<workflow/Omics_dir>",
    "indir": "<raw_data_dir>",
    "outdir": "<project_root>/output",
    "logdir": "<project_root>/logs",
    "samples": ["<all_sample_names>"],
    "paired_samples": ["<paired_end_samples>"],
    "single_samples": [],
    "ip_samples": ["<IP_samples>"],
    "input_samples": ["<Input_controls>"],
    "sample_ip_input_map": {
        "<IP_sample>": "<corresponding_Input>"
    },
    "genomes": ["mm"],
    "outfiles": [],
    "Procedure": {
        "trim_galore": null,
        "bowtie2-build": null,
        "bowtie2": null,
        "samtools": null,
        "macs3": null
    },
    "Params": {
        "trim_galore": {"quality": 30},
        "bowtie2": {},
        "macs3": {
            "bw": 200,
            "pvalue": "1e-5",
            "genome_size": "mm"
        }
    },
    "genome": {
        "fasta": "<primary_fasta_path>",
        "mm": {"fasta": "<mouse_fasta>"},
        "hg38": {"fasta": "<human_fasta>"}
    }
}
```

Key mapping rules:
- `sample_ip_input_map`: each IP sample maps to its matching Input control
- `genomes` array must match the keys under `genome`
- `macs3.genome_size`: `"mm"` for mouse, `"hs"` for human

## Heterogeneous metadata / scattered-data consolidation

When raw files are scattered across many directories and metadata tables use different column names, do NOT answer with schema theory alone. Deliver a concrete normalization artifact the user can run immediately.

Recommended pattern:
1. Keep raw data in place; do not copy everything into one directory first.
2. Build a centralized registry with at least two outputs:
   - `sample_registry.tsv`: one row per logical sample
   - `file_registry.tsv`: one row per physical file
3. For each metadata source, define a per-source column mapping into a small standard field set, e.g.:
   - `sample_id`
   - `data_id`
   - `project_id`
   - `assay_type`
   - `organism`
   - `condition`
   - `group`
   - `replicate`
4. Match metadata rows to scattered files by a stable join key (`data_id`, run accession, lane key, etc.), not by hand-maintained ad hoc notes.
5. Emit QA tables in addition to the registry:
   - `conflicts.tsv` for contradictory metadata on the same `sample_id`
   - `issues.tsv` for metadata rows with no matched files
   - `unmatched_files.tsv` for scanned files that were not registered
6. If the user wants a centralized view for pipelines, generate a symlink tree from the registry instead of duplicating large FASTQ/BAM files.

See `references/heterogeneous-metadata-registry.md` for a compact registry schema, per-source mapping pattern, QA outputs, and join-key strategy.

User-preference pitfall:
- If the user asks how to centrally manage scattered datasets/metadata, avoid staying at the conceptual level. Provide a runnable script, mapping template, registry format, or a direct transformation path from their current metadata to unified tables.

## Step 4: Write meta.tsv

Tab-separated with columns:
```
sample_id	data_id	design	fastq_1	fastq_2	workflow
```

- `design`: controls how samples are paired for comparison. Two modes:

### Design mode A - Grouping (MERIP / RNAseq)
Plain group name derived from sample_id by stripping replicate suffixes (`-1`, `_Rep2`, etc.).
Example: `GV`, `mESC-10ng`, `mA_A_0_4`.

**Automated generation**: Use `generate_meta_input.py design` to auto-build the design column from `gsm_metadata.csv` + `sra_metadata.csv`. The user specifies which metadata columns (e.g., `treatment`, `phenotype`) to use for grouping via `-c`. See `ngs-data-download` skill's `references/generate-design.md` for details.

### Design mode B — Comparison pairs (PeakCalling / CLIP)
Format: `ctrl_TAG1_TAG2_...` for controls, `exp_TAG` for experiments.
TAGs are underscore-delimited tokens. Matching rule: **token-set intersection** — a control matches an experiment when their TAG token sets share at least one element.

```
# One control serves multiple experiments:
Input_WT     ctrl_WT_KO_IP    # tokens={WT,KO,IP}
H3K4me3_WT   exp_WT           # tokens={WT} ∩ {WT,KO,IP}={WT} → match
H3K4me3_KO   exp_KO           # tokens={KO} ∩ {WT,KO,IP}={KO} → match

# Multiple controls, each matched to its experiments:
Input_WT     ctrl_WT
Input_KO     ctrl_KO
H3K4me3_WT   exp_WT           # matches Input_WT
H3K4me3_KO   exp_KO           # matches Input_KO
```

Key rules:
- Token isolation: `ctrl_KOWT` does NOT match `exp_KO` (token `KOWT` ≠ `KO`)
- `ctr_` prefix also accepted (backward compat), recommend `ctrl_`
- Multiple ctrl samples with same tag → only first is used (warning logged)
- If no ctrl matches an exp tag → warning logged, that exp is skipped

See `references/design-pairing.md` for full examples and edge cases.

- `fastq_1` / `fastq_2`: absolute paths to paired-end fastq files
- `workflow`: e.g., `PeakCalling`

## Step 5: Create Output Directories

```bash
mkdir -p <outdir> <logdir>
```

## Step 6: Run the Workflow

**ALWAYS read the README at `workflow/Omics/README.md` first.** The correct entry point is `run.py`, not raw snakemake commands.

```bash
export CONDA_PREFIX=/home/luosg/miniconda3  # fix conda plugin bug
python workflow/Omics/run.py \
  -m <meta.tsv> \
  -w PeakCalling \
  -o <output_dir> \
  -t <threads> \
  --conda-prefix <conda_env_prefix_dir>
```

- `-m`: meta.tsv file OR fastq directory
- `-w`: workflow name (`PeakCalling`, `RNAseq`, `CLIP`, etc.)
- `-o`: output directory (run.py creates `output/<workflow>/` substructure)
- `--conda-prefix`: directory for snakemake conda envs (must exist)

## Step 7: Verify

Validate config before running:
1. JSON parses correctly
2. All fastq files exist at referenced paths
3. Reference genome fasta exists
4. IP-Input mapping is consistent (every IP has a corresponding Input)

## Pitfalls

See also:
- `references/troubleshooting.md` — conda, snakemake module import, symlink issues
- `references/annotation-standardization.md` — MT gene prefix, chromosome naming
- `references/apptainer-container-building.md` — EnvUtil, post hooks, build verification
See `references/task-status-monitoring.md` for systematic pipeline status checking, forensic crash diagnosis (boot gap analysis, STAR Log.out null-byte detection, OOM/kernel-upgrade checks), and crash recovery procedures.

- **Read the docs first**: ALWAYS read `workflow/Omics/README.md` and `subworkflow/README.md` before running anything. Use `run.py` entry point, not raw snakemake.
- **Organism mismatch**: Directory names like `GRCh38` in the working path do NOT mean the data is human. Always confirm.
- **genome_size must match organism**: `"mm"` for mouse, `"hs"` for human. Wrong value causes MACS3 to miscalculate genome length.
- **Paired vs single**: Check if reads come as `_1.fq.gz`/`_2.fq.gz` (paired) or single files.
- **Absolute paths**: All paths in config and meta.tsv should be absolute.
- **ROOT_DIR must be `workflow/Omics`**: NOT the project root. The `common.smk` module imports `{ROOT_DIR}/src/common/LogUtil.py`. Set it to the directory containing `src/`, `modules/`, `subworkflow/`.
- **Module configs need ROOT_DIR**: When adding module configs in `.smk` files (e.g., `cutadapt_config`), include `"ROOT_DIR": config.get("ROOT_DIR", ".")` or `common.smk` import fails silently and `use rule` imports don't register.
- **conda `anaconda_anon_usage` plugin crash**: If `CONDA_DEFAULT_ENV=base` but `CONDA_PREFIX` is unset, conda crashes with `TypeError`. Fix: `export CONDA_PREFIX=/home/luosg/miniconda3` before running, or `pip uninstall anaconda-anon-usage`.
- **`conda:` directives in .smk modules**: Can cause snakemake startup failures even without `--use-conda`. If rules aren't registered, check for conda directives and either fix the environment or comment them out and use full binary paths.
- **repN token pollution in design column**: When design values contain `rep1`/`rep2` suffixes (e.g., `ctr_GSE123_condition_rep1`), the `rep1` token participates in set-intersection matching, causing false cross-study pairings (e.g., `exp_GSE456_other_rep1` matches `ctr_GSE123_condition_rep1` because they share `rep1`). The code now warns when shared tokens are **only** rep-like (`repN`), but does not skip the match. To avoid this: provide a `group` column in meta.tsv, or omit rep numbers from the design column.
- **group column auto-derivation**: If meta.tsv has no `group` column, group names are derived from the `design` column by stripping the `ctr`/`ctrl`/`exp` prefix and replacing `_` with spaces (e.g., `exp_GSE123_treated` → `GSE123 treated`). If a `group` column exists, it takes priority. This affects `CompareGroupPair.ctr_group_name` / `exp_group_name`, which become the keys in `raw.json`'s `Params.DESeq2.group_pairs` via `setdefault("{ctr}_vs_{exp}", ...)`.
- **`build_design_pairs` returns a 2-tuple**: `(sample_pairs: List[DesignPair], group_pairs: List[CompareGroupPair])`. Not 3 elements. Calling code that unpacks 3 values will fail.
- **Flat symlinks vs subdirectory structure**: MetaUtil creates `raw_fastq/{sample_id}_1.fq.gz` (flat) but cutadapt expects `raw_fastq/{sample_id}/{sample_id}_1.fq.gz`. This is NOT handled by run.py - after run.py generates `raw.json`, you must edit it to set `indir` to the original data directory (which has the correct subdirectory layout), OR manually create subdirectories with symlinks before running snakemake.
- **PeakCalling.smk cutadapt_config needs ROOT_DIR**: The `cutadapt_config` dict in `subworkflow/PeakCalling.smk` is missing `"ROOT_DIR"`. Add `"ROOT_DIR": config.get("ROOT_DIR", ".")` to it, or `common.smk` import fails and `use rule` imports don't register (only affects snakemake-based execution, not shell script fallback).
- **outfiles must be populated**: The `outfiles` array in config must list all expected output files. run.py generates this automatically. For manual config, populate it or snakemake's `rule all` has nothing to target.
- **Fallback: shell script**: If snakemake module imports fail (e.g., conda plugin issues breaking `use rule` silently), write a shell script running each step directly: cutadapt → bowtie2-build → bowtie2 align → samtools sort/index → macs3 callpeak. Use `scripts/generate_peakcalling_script.py` to generate this script automatically.
- **`"key" in input` does NOT check named keys**: In Snakemake's `run:` block, `input` is a `Namedlist`. The `in` operator checks if the string appears as a **value** (file path), not as a **named key** from `unpack()`. So `"bam_control" in input` always returns False. Fix: use `hasattr(input, "bam_control") and input.bam_control`.
- **Numeric params crash `" ".join(cmd)`**: Snakemake config values like `bw=200` or `seed=2346` are `int`. Building a command list and joining with `" ".join(cmd)` raises `TypeError: sequence item N: expected str instance, int found`. Always wrap: `str(params.bw)`, `str(params.seed)`, etc.
