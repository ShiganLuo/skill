---
name: fiberseq-workflow
description: "Fiber-seq pipelines with fibertools-rs and Snakemake."
tags: [bioinformatics, fiberseq, pacbio, chromatin, snakemake]
triggers:
  - user mentions fiber-seq, fibertools, FIRE, nucleosome calling, m6A prediction
  - user works with PacBio HiFi data for chromatin accessibility
  - user asks about ft predict-m6a, ft fire, ft extract, ft call-peaks
---

# Fiber-seq Workflow

Fiber-seq single-molecule chromatin accessibility analysis using fibertools-rs (ft).

## Tool

Always use the **container version** for CLI help, not system PATH (which may be outdated):
```bash
apptainer exec /home/<USER>/Database/env/fibertools/fibertools.sif ft --help
# v0.13.1 in container vs v0.8.0 on system PATH
```

All subcommands support `-t/--threads` (default: 8). Always pass `-t {threads}` in the cmd list.

## Workflow Architecture

Three-stage pipeline:

```
Stage 1: Prepare (per-read ops, no alignment needed)
  CCS BAM (kinetics) → ft predict-m6a (m6A + nuc + MSP) → ft fire (FIRE calls)
  Output: {sample_id}.fiberseq.fire.bam

Stage 2: Align
  fiberseq.fire.bam → pbmm2 align → {sample_id}.sorted.bam
  pbmm2 preserves MM/ML/aq tags through alignment.

Stage 3: Analysis (needs aligned BAM)
  sorted.bam → ft extract (separate bed12 per feature type)
             → ft call-peaks (FIRE peaks, needs pileup)
             → ft qc
```

### Why align after fire, not before

- `predict-m6a`: needs raw kinetics (IPD/PL tags), must be before alignment
- `fire`: per-read operation, doesn't need alignment
- `extract -r`: needs reference coordinates → requires aligned BAM
- `call-peaks`: needs pileup across reads → requires aligned BAM

### predict-m6a already adds nucleosomes

`ft predict-m6a` outputs m6A + nucleosome + MSP calls by default.
Only run `ft add-nucleosomes` separately when custom params are needed.
Control via `Params.fibertools.add_nucleosomes` in JSON config (default: false).

Nucleosome calling params are species-independent — nucleosome wrap length
(~147bp) is conserved across eukaryotes. Only adjust for edge cases:
very short fibers (reduce `--distance-from-end`), or unusually short
linkers in specific genomic contexts.

### SPRQ Chemistry Auto-Detection

Revio SPRQ chemistry (BINDINGKIT=103-496-900) produces m6A calls on-instrument.
Running `ft predict-m6a` on SPRQ data fails: "Model for BINDINGKIT=103-496-900 not available."

Detection strategy (priority order):
1. Check BAM @RG header for `103-496-900` (instant, deterministic)
2. Fallback: sample first 100 reads for MM:Z: tags via `samtools view | head -100`

```python
def _detect_m6a(bam_path: str) -> bool:
    """Check header for SPRQ kit, fallback to MM tag sampling."""
    import subprocess
    try:
        r = subprocess.run(["samtools", "view", "-H", bam_path],
                          capture_output=True, text=True, timeout=10)
        if "103-496-900" in r.stdout:
            return True
        r = subprocess.run(f"samtools view {bam_path} | head -100",
                          shell=True, capture_output=True, text=True, timeout=30)
        lines = r.stdout.strip().split("\n")
        return sum(1 for l in lines if "MM:Z:" in l) > len(lines) // 2
    except Exception:
        return False
```

When m6A detected: skip predict-m6a, symlink input → output, proceed to add-nucleosomes + fire.

### Conditional add-nucleosomes via input function

Priority: manual config > auto-detect. User explicitly demanded this.

```python
def get_input_for_ft_fire(wildcards):
    add_nuc = config.get("Params", {}).get("fibertools", {}).get("add_nucleosomes_manual", None)
    if add_nuc is True:        # manual: force add-nucleosomes
        return outdir + "/{sample_id}/{sample_id}.fiberseq.nuc.bam"
    elif add_nuc is False:     # manual: force skip
        return outdir + "/{sample_id}/{sample_id}.fiberseq.bam"
    else:                      # auto-detect m6A
        if _has_m6a(wildcards.sample_id):
            return outdir + "/{sample_id}/{sample_id}.fiberseq.nuc.bam"
        else:
            return outdir + "/{sample_id}/{sample_id}.fiberseq.bam"

rule ft_fire:
    input:
        bam = get_input_for_ft_fire
```

## ft extract: separate outputs, not --all

```bash
# ✅ Correct: separate bed12 files per feature type
ft extract -r input.bam --m6a m6a.bed.gz --nuc nuc.bed.gz --msp msp.bed.gz -c cpg.bed.gz

# ❌ Wrong: --all outputs tabular format, not standard bed12
ft extract -r input.bam --all all.bed.gz
```

Separate bed12 files → each is a standalone UCSC browser track (drag-and-drop).
`--all` is a tabular summary, not directly browser-compatible.

bed12 vs bedgraph: different purposes.
- bed12: single-molecule resolution (one fiber per line, block structure)
- bedgraph: aggregate signal/coverage (continuous values)
Convert bed12 → bedgraph with bedtools when aggregate views needed.

## Snakemake Module Pattern

Use a single `_bam_suffix` config for input flexibility. Subworkflow controls routing:

```python
# Module (fibertools_prepare.smk)
rule ft_fire:
    input:
        bam = outdir + "/{sample_id}/{sample_id}.fiberseq.bam"

# Module (fibertools_analysis.smk)
_bam_suffix = config.get("bam_suffix", ".fiberseq.fire.aligned.bam")
rule ft_extract:
    input:
        bam = indir + "/{sample_id}/{sample_id}" + _bam_suffix

# Subworkflow (Fiberseq.smk)
module fibertools_analysis:
    config: {"bam_suffix": ".sorted.bam", ...}
```

Do NOT create multiple suffix parameters (`_fire_input_suffix`, `_input_suffix`).
The subworkflow layer handles routing, not the module layer.

## Module Files

- `modules/fibertools/fibertools_prepare.smk` — predict-m6a, add-nucleosomes, fire
- `modules/fibertools/fibertools_analysis.smk` — extract, call-peaks, qc
- `modules/pbmm2/pbmm2.smk` — alignment (shared with other workflows)
- `subworkflow/Fiberseq.smk` — orchestrates the three stages

## BAM Naming Convention

Use descriptive suffixes so files are identifiable without checking path:
```
{id}.fiberseq.bam              — after predict-m6a
{id}.fiberseq.nuc.bam          — after add-nucleosomes (optional)
{id}.fiberseq.fire.bam         — after fire
{id}.fiberseq.fire.sorted.bam  — after pbmm2 alignment
```

pbmm2 supports `output_bam_suffix` config to control output naming:
```python
# In subworkflow pbmm2_config:
"bam_suffix": ".fiberseq.fire.bam",          # input
"output_bam_suffix": ".fiberseq.fire.sorted", # output (without .bam)
```
Default is `.sorted` (backward compatible). PacVar.smk and other workflows
that don't pass `output_bam_suffix` continue to get `.sorted.bam`.

## node.py ↔ Subworkflow Alignment

When refactoring Fiberseq.smk (renaming directories, splitting modules),
ALSO update `node.py::runFiberseq()`. See `references/node-py-subworkflow-alignment.md`.

## Pitfalls

- **System PATH outdated**: ft v0.8.0 (system) lacks `call-peaks`; always use container v0.13.1
- **Over-engineering suffixes**: One `_bam_suffix` per module, not per-rule suffix params
- **extract --all**: Tabular format, not bed12. Use `--m6a`/`--nuc`/`--msp`/`-c` for bed12
- **Alignment timing**: Don't align before predict-m6a (kinetics tags may be modified)
- **add-nucleosomes**: Usually unnecessary (predict-m6a includes it), only for custom params
- **call-peaks needs sorted BAM**: The rule sorts internally, but input must be aligned
- **Missing -t in cmd**: All ft subcommands default to 8 threads, but must be passed explicitly via `-t {threads}` in cmd list
- **add-nucleosomes species-independence**: Nucleosome structure is conserved; default params work for all eukaryotes. Only adjust for edge cases (very short fibers, unusual linker lengths)
- **SPRQ detection**: Don't use `samtools view` alone (reads entire BAM, timeout on large files). Check header first with `samtools view -H`
- **Snakemake source cache**: Module imports may cache stale `.smk` code. If code changes aren't taking effect, clear `~/.cache/snakemake/snakemake/source-cache/runtime-cache/`