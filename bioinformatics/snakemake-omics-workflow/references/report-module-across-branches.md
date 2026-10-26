# Report module across multiple subworkflow branches

When a subworkflow has multiple aligner/mode branches (e.g. hisat2, star, star_3pass, star_3pass_gene), each producing different output structures, the report module must adapt to the active branch.

## Problem

A report module was originally placed inside one specific branch (star_3pass_gene). Other branches had no report. The module hardcoded paths to that branch's outputs (4_per_gene_bam, genes.tsv, tail CSV).

## Solution: 3-layer adaptation

### Layer 1: Subworkflow — move report to public area

Move the report config/module/use-rule from inside a specific branch to the shared area AFTER the if/elif/else block:

```python
# BRANCHES (each sets up its own alignment modules)
if aligner == "hisat2":
    ...
elif aligner == "star":
    ...
elif aligner == "star_3pass":
    ...
elif aligner == "star_3pass_gene":
    ...
else:
    raise ValueError(...)

# SHARED REPORT — runs for ALL branches
ncRNAseq_report_config = {
    "ROOT_DIR": ROOT_DIR,
    "outdir": outdir,
    "samples": all_samples,
    "aligner": aligner,          # ← pass the branch type
    "sample_groups": config.get("sample_groups", {}),
    ...
}
module ncRNAseq_report:
    snakefile: "../modules/ncRNAseq_report/ncRNAseq_report.smk"
    config: ncRNAseq_report_config
use rule generate_report from ncRNAseq_report as ncRNAseq_generate_report
```

### Layer 2: Module .smk — conditional inputs with unpack()

Use `unpack(_report_inputs)` to dynamically assemble inputs based on the aligner:

```python
aligner = config.get("aligner", "star_3pass_gene")
has_per_gene = (aligner == "star_3pass_gene")
has_tailer = aligner in ("star_3pass", "star_3pass_gene")

def _report_inputs(wildcards):
    inp = {
        "trimming_stats": expand(...),  # always present
    }
    if has_per_gene:
        inp["per_gene_bams"] = expand(...)
        inp["per_gene_manifests"] = expand(...)
    if has_tailer and not has_per_gene:
        inp["tailer_csvs"] = expand(...)  # different path for star_3pass
    return inp

rule generate_report:
    input:
        unpack(_report_inputs)
    ...
    params:
        aligner = aligner,
    run:
        cmd = [..., "--aligner", params.aligner, ...]
```

### Layer 3: Python script — branch-aware data collection

The report script accepts `--aligner` and adapts paths + skips missing sections:

```python
def collect_sample_data(analysis_dir, samples, aligner="star_3pass_gene"):
    has_per_gene = aligner == "star_3pass_gene"
    has_tailer = aligner in ("star_3pass", "star_3pass_gene")

    for s in samples:
        # BAM path varies by branch
        if has_per_gene:
            bam = f"4_per_gene_bam/{s}/{s}.bam"
        elif aligner == "hisat2":
            bam = f"4_markdup_bam/{s}/{s}.sorted_markdup.bam"
        else:
            bam = f"3_raw_bam/{s}/{s}.bam"

        # Tail CSV path varies
        if has_tailer:
            if has_per_gene:
                tail_csv = f"4_per_gene_bam/{s}/{s}_tail.csv"
            else:
                tail_csv = f"results/tailer/{s}/{s}_tail.csv"

    # ...

# In main(): skip slides when data is missing
has_gene_data = any(d.get("n_genes") is not None for d in samples_data)
has_tail_data = any(d.get("total_tail_reads") is not None for d in samples_data)
if has_gene_data:
    build_gene_slide(...)
if has_tail_data:
    build_tail_slide(...)
```

## Branch data structure reference

| Data | hisat2/star | star_3pass | star_3pass_gene |
|------|-------------|------------|-----------------|
| BAM dir | 4_markdup_bam | 3_raw_bam | 4_per_gene_bam |
| BAM suffix | .sorted_markdup.bam | .bam | .bam |
| STAR/hisat2 log | {sample}.Log.final.out / .hisat2_summary.txt | N/A (embedded in 3-pass log) | N/A (embedded in 3-pass log) |
| Tail CSV | none | results/tailer/ | 4_per_gene_bam/ |
| Gene manifest | none | none | 4_per_gene_bam/genes.tsv (side effect, NOT declared output) |

## Critical pitfalls discovered during implementation

### STAR log files don't exist as standalone inputs for 3-pass branches

STAR's `--outFileNamePrefix` produces `{prefix}Log.final.out`. For plain `star` aligner, the prefix is `{sample_id}.`, so the file is `{sample_id}.Log.final.out` (NOT `star.Log.final.out`). For `star_3pass` and `star_3pass_gene`, STAR is called inside `three_pass_align.py` with per-pass prefixes — the logs are embedded in the script's own log file, not available as standalone files.

**Action**: Do NOT include STAR log files in `_report_inputs()`. The report Python script's `parse_star_log()` handles missing files gracefully (returns None for all stats). STAR alignment stats will simply be absent from the report for 3-pass branches.

### Only declared outputs can be Snakemake inputs

`genes.tsv` and `read_gene_overlaps.tsv` are produced as side effects by `gene_specific_align.py` / `prepare_gene_inputs.py` but are NOT declared in the rule's `output:` section. Including them in `_report_inputs()` causes `MissingInputException` because Snakemake can't trace them to any rule.

**Action**: Only use declared outputs (`{sample}.bam`, `{sample}_tail.csv`) in `_report_inputs()`. The Python script reads `genes.tsv` at runtime; if it doesn't exist, it returns empty data.

### node.py outfiles must exactly match rule output filenames

The rule declares `file_inventory = outdir + "/ncRNAseq_report_files.xlsx"`. If node.py appends `outdir + "/ncRNAseq_report.xlsx"` (without `_files`), Snakemake's `rule all` can never satisfy the target. Always verify the exact filename matches.

**Action**: After modifying rule outputs, grep node.py for the old output name and update it.

### Duplicate outfiles when moving report from branch to shared area

When moving `outfiles.append(f"{outdir}/ncRNAseq_report.pptx")` from inside a branch to the shared area, remove the branch-level append. Otherwise the file appears twice in `outfiles`, which while not breaking anything, is messy and confusing.

**Action**: Delete the old branch-specific `outfiles.append()` when adding the shared one.
