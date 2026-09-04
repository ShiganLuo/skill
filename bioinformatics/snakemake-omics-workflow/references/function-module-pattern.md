# Function module: GO/KEGG + GSEA downstream of DESeq2

## Module structure

```
modules/function/
  function.smk          # Two rules: function_go_kegg, function_gsea
  function.json         # Config template
  function.yaml         # Conda env (clusterProfiler, fgsea, enrichplot, etc.)
  bin/
    go-kegg.r           # CLI with argparse, reads DESeq2 .name.tsv
    gsea.r              # CLI with argparse, reads raw DESeq2 .tsv
```

## Subworkflow integration (RNAseq.smk)

Function module is conditionally enabled via `Params.function.enabled`:
```python
if config.get("Params", {}).get("function", {}).get("enabled", False):
    function_config = {
        "ROOT_DIR": ROOT_DIR,
        "indir": DESeq2_config["outdir"],      # chains from DESeq2 output
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

## Critical input file distinction

The two rules consume DIFFERENT DESeq2 output files:

| Rule | Input file | Why |
|------|-----------|-----|
| function_go_kegg | `TEcount_Gene.name.tsv` | Has `gene_name` column; `bitr()` uses `fromType="SYMBOL"` |
| function_gsea | `TEcount_Gene.tsv` (raw) | Has Ensembl `gene_id` as rownames; `GSEA_prepare()` joins with annotation on `gene_id` |

If GSEA receives `.name.tsv`, the `left_join(anno, by="gene_id")` fails silently — gene_name values don't match Ensembl IDs in the annotation, so `filter(gene_type == "protein_coding")` returns 0 rows.

## DESeq2 output file naming

`gene_id2name.py` is called without `-o` (outprefix), so it defaults to:
```python
outfile = f"{infile.split('.')[0]}.name.tsv"
```
For input `{sample_outdir}/TEcount_Gene.tsv`, output is `{sample_outdir}/TEcount_Gene.name.tsv`.

**Caveat:** `split('.')[0]` splits on the FIRST dot. If the output path contains dots (e.g. `v2.0`), the filename is truncated incorrectly. This is a pre-existing bug in gene_id2name.py, not introduced by the function module.

## Wildcard consistency

Function rules use `{control_group_name}` and `{experimental_group_name}` — identical to DESeq2.smk wildcards. The `group_pairs` config dict is keyed by `f"{ctrl}_vs_{exp}"`.

## Config keys

`Params.function` section in RNAseq.json:
```json
{
    "function": {
        "enabled": false,
        "species": "mouse",
        "gmt": null,
        "lfc_cut": 1,
        "p_cut": 0.05,
        "top": 10
    }
}
```

## go-kegg.r CLI

```
Rscript go-kegg.r -i <input.tsv> -o <outdir> -s <species> \
  --gene-col gene_name --value-col log2FoldChange --p-col padj \
  --lfc-cut 1 --p-cut 0.05 --top 10
```

Outputs: `go_back_to_back.png`, `kegg_back_to_back.png`, `go_up.csv`, `go_down.csv`, `kegg_up.csv`, `kegg_down.csv`, `up_genes.txt`, `down_genes.txt`

## gsea.r CLI

```
Rscript gsea.r -m Gene -g <gmt_file> -i <input.tsv> -o <outdir> \
  -a <annotation.csv> -t <graph_title>
```

Outputs: `GSEA/TEcount_Gene_GSEA.jpeg`, `GSEA/TEcount_Gene_GSEA.csv`, `GSEA/TEcount_Gene_GSEA.rnk`, `GSEA/enrichment_plots/*.jpeg`

## run.py outfiles

In `runRNAseq()`, function outputs are added per group_pair:
```python
if datajson.get("Params", {}).get("function", {}).get("enabled", False):
    pair_dir = f"{outdir}/function/{group_pair.ctr_group_name}_vs_{group_pair.exp_group_name}"
    outfiles.append(f"{pair_dir}/go_back_to_back.png")
    outfiles.append(f"{pair_dir}/kegg_back_to_back.png")
    outfiles.append(f"{pair_dir}/GSEA/TEcount_Gene_GSEA.jpeg")
```
