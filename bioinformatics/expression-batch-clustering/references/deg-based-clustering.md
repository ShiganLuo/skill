# DEG-Based Clustering for Stem Cell Discrimination

## Problem

Marker genes (100-200 genes) fail to discriminate between stem cell types because core pluripotency genes (NANOG, POU5F1, SOX2, KLF4) are expressed in all stem cells. In vitro culture conditions create shared expression patterns that dominate over stage-specific signals.

## Solution: DEG-based gene selection

Use DESeq2 results to find genes that are differentially expressed between stem cell types.

### Step 1: Run DESeq2 comparisons

For each stem cell type, run DESeq2 against hESC (or appropriate control):
- hTBLC vs hESC
- ci8CLC vs hESC
- prEpiSC vs hESC
- ciTotiSC vs mESC (mouse)
- TLSC vs mESC (mouse)

### Step 2: Select significant DEGs

```python
import pandas as pd

def load_deg_genes(deg_path, padj_cut=0.05, lfc_cut=1.0):
    df = pd.read_csv(deg_path, sep="\t")
    pcol = 'padj' if 'padj' in df.columns else 'pvalue'
    mask = (df[pcol] < padj_cut) & (abs(df['log2FoldChange']) > lfc_cut)
    gene_col = 'gene_name' if 'gene_name' in df.columns else df.columns[0]
    return df.loc[mask, gene_col].tolist()
```

### Step 3: Combine DEGs from all comparisons

```python
htblc_deg = load_deg_genes("hTBLC/DESeq2/TEcount_Gene_name.tsv")
ci8clc_deg = load_deg_genes("ci8CLC/DESeq2/TEcount_Gene_name.tsv")
all_deg = list(set(htblc_deg + ci8clc_deg))
```

### Step 4: Cluster with DEGs

```python
# Filter expression matrix to DEGs
available_deg = [g for g in all_deg if g in tpm_df.index]
subset_tpm = tpm_df.loc[available_deg]

# log2 transform and z-score
log2_tpm = np.log2(subset_tpm + 1)
z = log2_tpm.subtract(log2_tpm.mean(axis=1), axis=0).div(log2_tpm.std(axis=1), axis=0).fillna(0)

# Correlation distance (often better than cosine for developmental mapping)
samples = z.T.values
corr = np.corrcoef(samples)
dist = np.maximum(1 - corr, 0)

# Hierarchical clustering
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
Z = linkage(squareform(dist), method="average")
```

## Results

In the Totipotent20251031 project:
- hTBLC vs hESC: 5,824 DEGs
- ci8CLC vs hESC: 2,665 DEGs
- Total unique: 7,756 DEGs
- After filtering to available genes: 4,698 genes

Using DEGs + correlation distance:
- ci8CLC → clusters with 8-cell (expected!) ✓
- prEpiSC → clusters with Morula/Blastocyst (expected!) ✓
- hESC → clusters with 8-cell (expected: Blastocyst ICM) - partial match
- hTBLC → clusters with 8-cell/hESC (expected: 2-4 cell) - not ideal

## When to use

- Marker genes fail to discriminate stem cell types
- Stem cells always cluster together regardless of distance metric
- Need to find genes that distinguish between stem cell states
- Want to map stem cells to developmental stages

## Limitations

- DEGs are specific to the comparison (hTBLC vs hESC), not general
- May not capture all biologically relevant genes
- Still affected by batch effects if present
- Requires existing DESeq2 results
