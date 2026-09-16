# Pseudobulk DEG Analysis with PyDESeq2

## Overview

Per-cell-type differential expression using pseudobulk aggregation + PyDESeq2. Standard approach: aggregate raw counts by sample per cell type, run DESeq2-style analysis. Superior to single-cell DEG methods (Wilcoxon on individual cells) for multi-sample comparisons.

## Key Reference

DGE.ipynb workflow (edgeR): aggregate → DGEList → filterByExpr → calcNormFactors → design → estimateDisp → glmQLFit → contrasts.

## PyDESeq2 No-Replicate Workaround

**Problem**: PyDESeq2 raises `ValueError: The number of samples and the number of design variables are equal` when each condition has only 1 sample (1-vs-1 comparison).

**Solution**: Split each sample's cells into N pseudo-replicates (default N=2), then run PyDESeq2 normally.

```python
def pseudobulk_with_replicates(adata_ct, sample_key="sample_id", n_splits=2):
    """Aggregate raw counts by sample, split into pseudo-replicates."""
    counts = adata_ct.layers["counts"]
    if hasattr(counts, "toarray"):
        counts = counts.toarray()

    gene_names = adata_ct.var_names.tolist()
    sample_ids = adata_ct.obs[sample_key].values

    all_rows, meta_rows = [], []
    for sample in sorted(set(sample_ids)):
        mask = sample_ids == sample
        cell_indices = np.where(mask)[0]
        np.random.shuffle(cell_indices)
        splits = np.array_split(cell_indices, n_splits)

        for i, split_idx in enumerate(splits):
            sub_counts = counts[split_idx]
            row_sum = np.asarray(sub_counts.sum(axis=0)).flatten()
            rep_name = f"{sample}_rep{i}"
            all_rows.append(row_sum)
            meta_rows.append({"sample": rep_name, "condition": sample, "replicate": f"rep{i}"})

    counts_df = pd.DataFrame(all_rows, columns=gene_names)
    counts_df.index = [m["sample"] for m in meta_rows]
    meta_df = pd.DataFrame(meta_rows).set_index("sample")
    return counts_df, meta_df
```

## PyDESeq2 Usage

```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

dds = DeseqDataSet(counts=sub_counts.astype(int), metadata=sub_meta, design="~condition")
dds.deseq2()

contrast = ["condition", sample2, sample1]
stat_res = DeseqStats(dds, contrast=contrast)
stat_res.summary()

res = stat_res.results_df  # columns: baseMean, log2FoldChange, lfcSE, stat, pvalue, padj
```

## TE Gene Identification

**Critical**: Naive regex matching (e.g., `L1`, `L2`, `LTR`) produces massive false positives from normal genes (CYSLTR1, IL1R1, COL1A1, etc.).

**Correct approach**: Match by repeat element naming conventions only:

```python
def is_te(name: str) -> bool:
    te_prefixes = (
        "Alu", "HERV", "HERVE", "HERVI", "HERVL", "HERVFH", "HERVH",
        "HERVK", "HERVS", "LTR", "L1M", "L1P", "L1PA", "L1PB",
        "L2a", "L2c", "MER", "MLT", "ERVL", "MacERV", "MacERVK",
        "MacNERVK", "hAT", "Tigger", "Charlie", "EuthAT",
    )
    te_exact = {"MIR", "MIR1306", "MIR1307", "MIR142", "MIR15A", "MIR26B",
                "MIR32", "MIR335", "MIR4785", "MIR5004", "MIR5047", "MIR1-2", "MIRLET7A1"}
    if name in te_exact:
        return True
    return any(name.startswith(p) for p in te_prefixes) or "-int" in name
```

**Validated counts** (macaque, scTE 3000 HVG):
- Uterus scTE: 44 TE genes
- Ovaries scTE: 83 TE genes
- Cell Ranger: 0 TE genes (expected — not quantified)

## Environment Notes

- **scanpy sif** (`/home/luosg/Database/env/scanpy/scanpy.sif`): has pydeseq2 0.5.4, does NOT have rpy2/edgeR
- **Host venv**: does NOT have pydeseq2 or rpy2
- Run via: `apptainer exec scanpy.sif python3 script.py`

## Output Structure

```
diff_expression/
  {dataset}/
    {cell_type}_{s1_short}_vs_{s2_short}_deg.tsv   # full DEG table with is_TE column
    {cell_type}_{s1_short}_vs_{s2_short}_volcano.png # volcano with TE highlighted (blue diamonds)
```

TSV columns: baseMean, log2FoldChange, lfcSE, stat, pvalue, padj, gene, cell_type, sample1, sample2, is_TE

## Cell Type Composition Analysis

For sample proportions per cell type (row-normalized crosstab):

```python
obs = adata.obs[["cell_type", "sample_id"]]
counts_df = pd.crosstab(obs["cell_type"], obs["sample_id"])
pct_df = counts_df.div(counts_df.sum(axis=1), axis=0) * 100
```

Stacked bar chart: one bar per cell_type, stacked by sample_id, x-axis = proportion %.

## Pitfalls

### PyDESeq2 design formula must use condition column
The `condition` column in metadata must have exactly 2 unique values for a pairwise comparison. Don't use `~replicate + condition` when there are only pseudo-replicates — `~condition` is sufficient.

### Min cells per sample threshold
Default `min_cells=30`. Cell types with <30 cells in any sample are skipped for that comparison. This prevents unreliable DEG results from tiny populations.

### scanpy backed mode for obs-only reads
Use `ad.read_h5ad(path, backed='r')` + `adata.obs[cols]` + `adata.file.close()` for quick metadata access without loading full X matrix. But note: `adata.file.close()` is required to release the HDF5 handle.
