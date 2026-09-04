# Comparison-Pair-Driven Workflow Pattern

When a workflow compares pairs of conditions (e.g., treatment vs control SV analysis),
use a `comparisons` config structure instead of hardcoding pairs.

## Config structure

```json
{
    "comparisons": [
        {"name": "PlaB06_vs_DMSO06", "control_vcf": "...", "experiment_vcf": "..."},
        {"name": "PlaB20_vs_DMSO20", "control_vcf": "...", "experiment_vcf": "..."}
    ]
}
```

## Module .smk pattern

```python
comparisons = config.get("comparisons", [])
comparison_names = [c["name"] for c in comparisons]

# Per-comparison rule — lambda input resolves VCFs by comparison name
rule sv_exp_specific:
    input:
        control_vcf = lambda wc: next(c["control_vcf"] for c in comparisons if c["name"] == wc.comparison),
        experiment_vcf = lambda wc: next(c["experiment_vcf"] for c in comparisons if c["name"] == wc.comparison),
    output:
        annotated_tab = outdir + "/{comparison}/{comparison}_annotated.tab",
    ...

# Aggregation rule — expand over all comparison names
rule sv_diff_analysis:
    input:
        specific_vcfs = expand(outdir + "/{comp}/{comp}_only.vcf", comp=comparison_names),
    ...

# Result rule — collect all per-comparison + aggregation outputs
rule sv_result:
    input:
        annotated_tabs = expand(outdir + "/{comp}/{comp}_annotated.tab", comp=comparison_names),
        diff_dir = outdir + "/sv_diff_analysis",
```

## Key points

- `comparison_names` extracted at top level for `expand()` usage
- Lambda input functions look up per-comparison config from the list
- Aggregation rules iterate `comparisons` to build `-g NAME:PATH` style args
- Result rule collects both per-comparison and aggregation outputs
- Each comparison gets its own subdirectory: `{outdir}/{comparison_name}/`

## Example: SV analysis module (modules/sv/sv.smk)

The SV module uses this pattern for:
- `sv_exp_specific` — per-comparison: merge, extract, annotate
- `sv_exp_enrichment` — per-comparison: GO/KEGG enrichment
- `sv_exp_circos` — per-comparison: Circos plot
- `sv_gene_model` — per-comparison: gene model plots
- `sv_diff_analysis` — aggregation: cross-comparison SV type/length plots
- `sv_oncoprint` — aggregation: OncoPrint + DESeq2 fold change
- `sv_result` — endpoint: all outputs collected
