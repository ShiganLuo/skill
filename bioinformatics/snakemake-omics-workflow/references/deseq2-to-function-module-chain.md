# DESeq2 -> Function Module Integration Pattern

Session: integrating `modules/function/` (GO/KEGG + GSEA) into `subworkflow/RNAseq.smk` after DESeq2.

## DESeq2 output structure

DESeq2 produces per-comparison-pair output directories:

```
{outdir}/diff_expression/{ctrl}_vs_{exp}/
  DESeq2.done                        # sentinel (rule output)
  TEcount_Gene.tsv                   # raw DESeq2 result, Ensembl gene_id as rownames
  TEcount_Gene.name.tsv              # gene_id2name.py output, gene_name as first column
  TEcount_TE.tsv / .name.tsv
  TEcount_Gene_TE.tsv / .name.tsv
  group.tsv                          # sample group metadata
```

Wildcards: `{control_group_name}` and `{experimental_group_name}` (NOT `{control_group}` / `{experiment}`).

### gene_id2name.py output naming

`gene_id2name.py` with no `-o` flag (as called in DESeq2.smk cmd3) uses:
```python
outfile = f"{infile.split('.')[0]}.name.tsv"
```
So `TEcount_Gene.tsv` -> `TEcount_Gene.name.tsv`. This works correctly when the directory path has no dots before the filename extension.

## Which file variant each analysis needs

| Analysis | Input file | Why |
|----------|-----------|-----|
| GO/KEGG (`go-kegg.r`) | `TEcount_Gene.name.tsv` | `bitr(fromType="SYMBOL")` needs gene symbols |
| GSEA (`gsea.r`) | `TEcount_Gene.tsv` (raw) | `GSEA_prepare()` does `left_join(anno, by="gene_id")` where anno has Ensembl IDs |

**Critical bug if reversed:** GSEA with `.name.tsv` silently produces 0 protein-coding genes because gene_name != gene_id in the annotation join. No error, just empty results.

## go-kegg.r CLI

```
Rscript go-kegg.r \
  -i <input_tsv> \
  -o <output_dir> \
  -s <species: human|mouse> \
  --gene-col gene_name \
  --value-col log2FoldChange \
  --p-col padj \
  --lfc-cut 1 \
  --p-cut 0.05 \
  --top 10
```

Outputs: `go_back_to_back.png`, `kegg_back_to_back.png`, `go_up.csv`, `go_down.csv`, `kegg_up.csv`, `kegg_down.csv`, `up_genes.txt`, `down_genes.txt`.

Key fixes from original `go-kegg_back.r`:
- Added argparse CLI (original had hardcoded paths at bottom)
- Fixed down-gene filter: `value <= -lfc_cut` (was `value <= 1/up_cutoff` which is wrong for log2FC)
- Changed `bitr` fromType from `ENSEMBL` to `SYMBOL` (because input is `.name.tsv` with gene symbols)

## gsea.r CLI

```
Rscript gsea.r \
  -m Gene \
  -g <gmt_file> \
  -i <input_tsv> \
  -o <output_dir> \
  -a <geneIDAnnotation.csv> \
  -t <graph_title>
```

Output: `{output_dir}/GSEA/TEcount_Gene_GSEA.jpeg` (plus `TEcount_Gene_GSEA.rnk`, `TEcount_Gene_GSEA.csv`, and `enrichment_plots/` directory).

The annotation file (`geneIDAnnotation.csv`) must have columns: `gene_id, gene_type, gene_name`. Only `protein_coding` genes are used for the ranked list.

## function.smk rule structure

Two rules, both with `{control_group_name}_vs_{experimental_group_name}` wildcards matching DESeq2:

```python
rule function_go_kegg:
    input:
        deseq2_done = indir + "/{ctrl}_vs_{exp}/DESeq2.done",
    output:
        go_png = outdir + "/{ctrl}_vs_{exp}/go_back_to_back.png",
        kegg_png = outdir + "/{ctrl}_vs_{exp}/kegg_back_to_back.png",
    params:
        deseq2_result = indir + "/{ctrl}_vs_{exp}/TEcount_Gene.name.tsv",
        ...

rule function_gsea:
    input:
        deseq2_done = indir + "/{ctrl}_vs_{exp}/DESeq2.done",
    output:
        gsea_png = outdir + "/{ctrl}_vs_{exp}/GSEA/TEcount_Gene_GSEA.jpeg",
    params:
        deseq2_result = indir + "/{ctrl}_vs_{exp}/TEcount_Gene.tsv",  # RAW, not .name.tsv
        ...
```

**Input is `DESeq2.done` sentinel** (not the TSV directly) because the TSV is consumed as a `params:` path, not an `input:` - this avoids Snakemake trying to produce it from an unknown rule. The `run:` block checks `os.path.exists(params.deseq2_result)` and raises `FileNotFoundError` with a clear message if missing.

## Config integration (4 files to touch)

### 1. RNAseq.json - add Params.function
```json
"function": {
    "enabled": false,
    "species": "mouse",
    "gmt": null,
    "lfc_cut": 1,
    "p_cut": 0.05,
    "top": 10
}
```

### 2. RNAseq.schema.json - add function section under Params
Mirror the JSON structure with type/required/path fields.

### 3. RNAseq.smk - conditional module after DESeq2
Gate behind `if config.get("Params", {}).get("function", {}).get("enabled", False):`.
Chain `indir` from `DESeq2_config["outdir"]`.

### 4. run.py runRNAseq() - conditional outfiles
```python
if datajson.get("Params", {}).get("function", {}).get("enabled", False):
    pair_dir = f"{outdir}/function/{group_pair.ctr_group_name}_vs_{group_pair.exp_group_name}"
    outfiles.append(f"{pair_dir}/go_back_to_back.png")
    outfiles.append(f"{pair_dir}/kegg_back_to_back.png")
    outfiles.append(f"{pair_dir}/GSEA/TEcount_Gene_GSEA.jpeg")
```

## Verification recipe

1. `python -c "import py_compile; py_compile.compile('run.py', doraise=True)"`
2. JSON validity check on all 3 JSON files
3. Config key consistency: grep `config.get("` in function.smk, verify each key in function.json and function_config dict
4. Path chain: function indir = DESeq2 outdir; function output paths match run.py outfiles
5. Wildcard consistency: `{control_group_name}` / `{experimental_group_name}` match DESeq2.smk
6. CLI arg consistency: grep `parser$add_argument` in R scripts, verify function.smk passes matching args
7. `snakemake --dry-run --summary` with a test config that has `enabled: true` and fake prerequisite files - verify both rules appear in DAG
8. `python scripts/verify-smk-structure.py modules/function/function.smk function_go_kegg,function_gsea`
