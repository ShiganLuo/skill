# Cell Ranger scRNAseq Module Pattern

## Module structure

```
modules/cellranger/
  cellranger.smk               # rules: cellranger_ref, cellranger_count, cellranger_to_h5ad
  cellranger.yaml              # conda env (anndata, scanpy, h5py, samtools)
  bin/cellranger_ref.py        # ALL ref-building logic (download, modify, filter, mkref)
  bin/cellranger_to_h5ad.py    # reads 10x matrix → writes .h5ad
```

**CRITICAL CONVENTION**: Rules ONLY validate inputs and call scripts. All logic lives in `bin/*.py`. The rule's `run:` block assembles a `cmd` list with `params.python, params.script, --args`, writes it to a timestamped `.sh` file, and calls `shell(f"bash {script} >> {log} 2>&1")`. NO inline sed/awk/grep/python logic in the rule. (User corrected: "规则只负责校验和调用,相关代码包装成脚本".)

This applies to ALL modules, not just cellranger. The scanpy module follows the same pattern: `bin/scRNAseq.py` has all mode logic (qc/cluster/batch/annotate/advanced/de), rules just pass `--mode` + args.

## Three rules

1. **cellranger_ref**: Calls `bin/cellranger_ref.py` which handles: download, strip Ensembl ID version suffixes from GTF, filter GTF by biotype, remove PAR_Y, run `cellranger mkref`. **FASTA and GTF keep original Ensembl chromosome names (1, 2, ..., X, Y, MT) — no chr prefix is added.** (User corrected: for non-human genomes, adding chr prefix is unnecessary and causes GTF/FASTA chromosome name mismatch errors.)
2. **cellranger_count**: Assembles `cellranger count` command with params (chemistry, expect_cells, no_bam) and writes to shell script.
3. **cellranger_to_h5ad**: Calls `bin/cellranger_to_h5ad.py` which reads 10x filtered_feature_bc_matrix → writes `.h5ad`.

## cellranger_ref.py pipeline

Steps:
1. Download or copy source FASTA/GTF
2. Strip Ensembl ID version suffixes from GTF (gene_id, transcript_id, exon_id)
3. Filter GTF by biotype allowlist (protein_coding, lncRNA, IG/TR genes)
4. Remove PAR_Y genes from Y (using Ensembl coordinates, not chrY)
5. Clean up stale `mkref_<genome>/` dir if present (cellranger refuses overwrite on param mismatch)
6. Run `cellranger mkref` with `cwd=args.output` — FASTA and GTF use matching Ensembl chromosome names

**CRITICAL**: `cellranger mkref` has NO `--output` flag. It creates `mkref_<genome>/` in the **current working directory**. Always pass `cwd=args.output` to `subprocess.check_call`. Without this, output goes to snakemake's CWD instead of the intended output dir.

```python
# Clean up stale mkref directory before running
mkref_dir = os.path.join(args.output, f"mkref_{args.genome}")
if os.path.exists(mkref_dir):
    logger.warning(f"Removing stale mkref directory: {mkref_dir}")
    shutil.rmtree(mkref_dir)
# Run with correct cwd
subprocess.check_call(cmd, cwd=args.output)
```

**Logging**: Use `setup_logger` from `src.common.util.LogUtil` instead of `print()`. Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`. Import via:
```python
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from src.common.util.LogUtil import setup_logger
logger = setup_logger(__name__, logging.INFO)
```

## Subworkflow wiring

In `subworkflow/scRNAseq.smk`:
- If `samples` list provided and no `input_h5ad`/`sample_h5ad` → Cell Ranger mode (upstream + scanpy downstream)
- If `input_h5ad` or `sample_h5ad` provided → skip Cell Ranger, scanpy only (backward-compatible)
- `cellranger_ref` is conditional: only runs if `Params.cellranger_ref.fasta` + `Params.cellranger_ref.gtf` are provided AND `genome.references.<default>.cellranger_transcriptome` is NOT already set

## Config structure

```yaml
samples: ["sample1", "sample2"]
Procedure:
  cellranger: "/opt/cellranger-8.0.0/bin/cellranger"
Params:
  cellranger:
    chemistry: "auto"
    expect_cells: 5000
    no_bam: true
  cellranger_ref:
    fasta: "http://ftp.ensembl.org/pub/release-109/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz"
    gtf: "http://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_44/gencode.v44.primary_assembly.annotation.gtf.gz"
    genome_name: "GRCh38"
    version: "2024-A"
    ref_dir: "output/cellranger_ref"
```

## CRITICAL PITFALL: sed regex escaping in Python-generated bash scripts

When generating bash scripts with `sed -E` regex patterns from Python strings in Snakemake rules:

**WRONG** — list-based line building with manual escaping:
```python
lines = [
    "    | sed -E 's/^(\\\\\\\\S+).*/>\\\\\\\\1 \\\\\\\\1/' \\\\\\",
]
```
This produces `\\\\\\\\S` (4 backslashes) → Python string `\\\\S` → bash sees `\\\\S` → sed sees literal `\\S` text (wrong). The `>` also gets lost when editing. **Real bug caught by verification**: missing `>` in `^>(\\S+)` pattern.

**CORRECT** — triple-quoted f-string:
```python
script_content = f"""#!/usr/bin/env bash
set -euo pipefail
cat {q(fasta_in)} \\
    | sed -E 's/^(\\S+).*/>\\1 \\' \\
    | sed -E 's/^>([0-9]+|[XY]) />chr\\1 /' \\
    | sed -E 's/^>MT />chrM /' \\
    > {q(fasta_modified)}
"""
```
In a triple-quoted f-string: `\\S` → `\S` in the string → `\S` in bash single quotes → sed sees `\S` (non-whitespace). Correct.

**Key rule**: Use triple-quoted f-strings for any bash script containing sed regex. Never use list-based line building for sed patterns.

## GTF sed with variable interpolation

For sed patterns that need shell variable expansion (`$ID`), use `'"'"'` to break in/out of single quotes:
```python
| sed -E 's/gene_id '"'"'$ID'"'"';/gene_id "\\1"; gene_version "\\3";/' \\
```
In triple-quoted strings, `'"'"'` passes through Python literally and bash interprets it as: end single-quote → literal `'` → start single-quote.

## Biotype allowlist (10x Genomics standard)

```python
BIOTYPE_PATTERN = (
    "protein_coding|protein_coding_LoF|lncRNA|"
    "IG_C_gene|IG_D_gene|IG_J_gene|IG_LV_gene|IG_V_gene|"
    "IG_V_pseudogene|IG_J_pseudogene|IG_C_pseudogene|"
    "TR_C_gene|TR_D_gene|TR_J_gene|TR_V_gene|"
    "TR_V_pseudogene|TR_J_pseudogene"
)
```

## PAR_Y filter

The PAR_Y filter uses `fields[0] == "Y"` (not `"chrY"`) since chromosome names are kept in original Ensembl format. Coordinates are human GRCh38-specific (2752083–56887903). For non-human genomes, this filter effectively has no impact since the Ensembl IDs won't match human patterns anyway.

## Stdout buffering in containers

When running inside Apptainer/singularity with stdout redirected to a file (`>> log`), Python detects non-TTY and uses block buffering (~4-8KB). Log messages appear in bursts, not real-time. Fix: set `PYTHONUNBUFFERED=1` env var, pass `-u` to Python, or use `sys.stdout.reconfigure(line_buffering=True)`.

## FASTQ layout

Cell Ranger expects: `{fastqs_dir}/{sample_id}_S1_L001_R1_001.fastq.gz`
Subworkflow rule input: `indir + "/{sample_id}"` (directory containing FASTQ files)
