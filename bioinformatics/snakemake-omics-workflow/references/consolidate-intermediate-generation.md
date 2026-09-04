# Consolidate intermediate generation into analysis scripts

## Principle

When an intermediate file (BED, TSV, etc.) is pure Python and consumed by exactly one downstream rule, integrate the generation logic into the downstream script instead of creating separate Snakemake rules. This eliminates intermediate rules, intermediate files, and simplifies the DAG.

User feedback: "生成tss bed以及gene region完全没必要写到sanekfile中,集成到脚本中不是更优雅吗，还都是python代码" — generating TSS BED and gene regions has no reason to be in the Snakefile; integrating into the script is more elegant since it's all Python anyway.

## Bad pattern (3 rules for what is really 1 step)

```python
# Rule 1: generate intermediate BED
rule generate_tss_bed:
    input: gtf = gtf
    output: bed = outdir + "/_tss_regions.bed"
    shell: "python3 generate_tss_bed.py --gtf {input.gtf} --output {output.bed}"

# Rule 2: another intermediate BED
rule extract_gene_regions:
    input: gtf = gtf
    output: bed = outdir + "/_gene_regions.bed"
    shell: "python3 extract_genes_bed.py --gtf {input.gtf} --output {output.bed}"

# Rule 3: the actual analysis, depends on intermediates
rule heatmap:
    input: bigwig = ..., regions = outdir + "/_tss_regions.bed"
    shell: "python3 run_heatmap.py --bigwig {input.bigwig} --regions {input.regions}"
```

## Good pattern (1 rule, script handles region generation internally)

```python
# run_heatmap.py accepts --gtf + --region-mode and generates BED on the fly
# using tempfile, cleaned up after computeMatrix runs

rule heatmap:
    input:
        bigwig = get_bigwig,
        gtf = _get_gtf_for_heatmap,  # returns "" when not needed
    output: heatmap = outdir + "/{sample_id}/{sample_id}_heatmap.png"
    run:
        cmd = ["python3", HEATMAP_SCRIPT, "--ip-bigwig", input.bigwig,
               "--output", output.heatmap]
        if input.gtf:
            cmd += ["--gtf", input.gtf, "--region-mode", "tss",
                    "--tss-flank", str(flank)]
        shell(" ".join(shlex.quote(str(c)) for c in cmd))
```

## When to apply

Intermediate file is:
- (a) Python-generated
- (b) Consumed by one rule only
- (c) Not needed as a standalone output

Keep separate rules when the intermediate is reused by multiple downstream rules or is itself a deliverable.

## Script design for on-the-fly generation

1. Add `--gtf` + `--region-mode` args to the analysis script
2. Use `tempfile.mkstemp()` for intermediate files, clean up after use
3. Add `--keep-regions-bed` flag for debugging (saves the generated BED)
4. Existing pre-made BED files still work via `--regions` (backward compatible)
5. In Snakefile, use conditional input functions that return `""` or `[]` when input not needed (avoids Snakemake treating `None` as a file path)

## Conditional input functions pattern

```python
def _get_gtf_for_heatmap(wildcards):
    """Return GTF path when mode needs it, empty list otherwise."""
    if regions_cfg == "tss":
        return [] if (tss_bed and os.path.isfile(tss_bed)) else (gtf or [])
    if _is_gene_regions():
        return _get_gene_gtf() or []
    return []

def _get_regions_for_heatmap(wildcards):
    """Return pre-made BED only for peaks mode."""
    if regions_cfg == "peaks":
        return os.path.join(indir, wildcards.sample_id, ...)
    if regions_cfg == "tss" and tss_bed and os.path.isfile(tss_bed):
        return tss_bed  # use existing BED directly
    return []  # tss/genes modes generate BED inside run_heatmap.py
```

**PITFALL:** Return `[]` NOT `""` for "no file". Snakemake treats `""` as a file path and raises "Empty file path encountered". Using `""` also causes silent DAG cascade in dry-runs.

## argparse: --gene-names as repeatable flag

When passing gene names from Snakefile via `cmd += ["--gene-names", name]` in a loop, use `action="append"` in argparse (not `nargs="*"` which overwrites on repeated flags):

```python
# Script
p.add_argument("--gene-names", action="append", default=[],
               help="Gene/TE names to extract (repeatable)")

# Snakefile
for name in gene_names:
    cmd += ["--gene-names", name]  # produces --gene-names A --gene-names B
```

## Real-world example: deeptools_heatmap module

- Before: 6 rules (generate_tss_bed, extract_gene_regions, extract_gene_region_per_name, heatmap, heatmap_gene, result)
- After: 3 rules (heatmap, heatmap_gene, result)
- `generate_tss_bed.py` and `extract_genes_bed.py` kept as standalone tools but no longer called from Snakemake rules
- BED generation logic merged into `run_heatmap.py` with `generate_tss_bed()` and `generate_genes_bed()` functions
