# Pseudobulk DEG Analysis Patterns

## PyDESeq2 Pseudobulk Workflow

For scRNA-seq differential expression: aggregate raw counts per sample per cell type, split into pseudo-replicates, run PyDESeq2.

### Core Pattern

```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# 1. Aggregate counts by sample, split into N pseudo-replicates
for sample in sorted(set(sample_ids)):
    mask = sample_ids == sample
    cell_indices = np.where(mask)[0]
    np.random.shuffle(cell_indices)
    splits = np.array_split(cell_indices, n_splits)  # typically 2

    for i, split_idx in enumerate(splits):
        sub_counts = counts[split_idx]
        row_sum = np.asarray(sub_counts.sum(axis=0)).flatten()
        # row_sum = pseudobulk counts for this replicate

# 2. Run PyDESeq2
dds = DeseqDataSet(
    counts=sub_counts.astype(int),
    metadata=sub_meta,
    design="~condition",
)
dds.deseq2()

contrast = ["condition", sample2, sample1]
stat_res = DeseqStats(dds, contrast=contrast)
stat_res.summary()
res = stat_res.results_df
```

### Key Points

- **Raw counts required**: Use `layers["counts"]`, not normalized X
- **Pseudo-replicates**: Split each sample's cells into 2 groups → enables DESeq2 dispersion estimation without true biological replicates
- **Min cells filter**: Skip cell type × sample combos with <30 cells (configurable)
- **Design formula**: `~condition` for pairwise comparison; add covariates as needed

### Pitfalls

- **Do NOT use shallow heuristics for gene classification** (e.g. TE detection by string prefix matching). For scTE data, TE classification comes from the tool's annotation — use that directly, not ad-hoc name parsing.
- PyDESeq2 requires integer counts — cast with `.astype(int)`
- Drop zero-count genes before DESeq2 to avoid convergence issues
- `sub_counts.shape[0] < 4` → return empty (need at least 2 conditions × 2 replicates)

### Output Columns

| Column | Description |
|--------|-------------|
| baseMean | Mean normalized count |
| log2FoldChange | log2(sample2 / sample1) |
| lfcSE | Standard error of LFC |
| stat | Wald statistic |
| pvalue | Raw p-value |
| padj | BH-adjusted p-value |

### Volcano Plot Thresholds (typical)

- padj < 0.05 AND |log2FC| > 1 → significant
- Label top N genes by -log10(padj) with adjustText for anti-overlap
