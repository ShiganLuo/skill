# TE Filtering and Gene Annotation

## Problem

scTE pipeline outputs h5ad with both gene counts and TE counts as features. When HVG selection includes TE genes, clusters form by TE composition (ERVK_high, Alu_high) rather than cell type identity.

## Solution: annotate_gene_type + _filter_te + --skip-te

### Gene Annotation (BED + CSV Format)

Current implementation uses two reference files:
- **TE BED** (e.g., `rheMac10_rmsk_TE.bed`): tab-separated, no header, columns: `chrom	start	end	TE_name`
- **Gene annotation CSV** (e.g., `geneIDAnnotation.csv`): tab-separated, with header, columns: `gene_id	gene_name	gene_type`

Parsing functions (in `scRNAseq.py`):
```python
def _parse_te_bed(bed_path: str) -> set:
    """Parse TE BED file, return set of TE names from column 4."""

def _parse_gene_tsv(tsv_path: str) -> Dict[str, str]:
    """Parse gene annotation TSV, return {gene_name: gene_type}."""
```

`annotate_gene_type(adata, te_bed, gene_tsv)` — populates `adata.var['gene_type']`

Matching priority:
1. Gene in TE BED → `"TE"` (overrides gene annotation)
2. Gene in gene annotation CSV → `gene_type` value (e.g., `"protein_coding"`, `"lncRNA"`)
3. Neither → `"unknown"`

**Example (macaque ovary, 19141 genes):**
- TE BED: 1274 unique TE names
- Gene CSV: 28113 entries
- Result: TE=1272, gene=17867, unknown=2

### Reference File Locations (Mulatta/Mmul_10)

```
/home/luosg/Database/Reference/mulatta/ENSEMBL/Mmul_10/geneIDAnnotation.csv
/home/luosg/Database/Reference/mulatta/ENSEMBL/Mmul_10/rheMac10_rmsk_TE.bed
```

### TE Gene Categories in scTE Output

Based on macaque ovary analysis (3000 HVGs, 19141 raw features):
- **ERVK (macaque)**: MacERVK2-int, MacERVK2_LTR1a, MacERVK2_LTR1c, MacNERVK2-int, MacNERVK2a-int, HERVK14-int, HERVK9-int, MacNERVK1-int
- **Alu/SINE**: AluYRd4 (only 1 in HVG set)
- **L1/LINE**: L1PA15
- **MIR/SINE**: 24 genes in HVG set
- **L2**: 52 genes
- **Other ERV**: ERVL47-int, HERVL74-int, HERV15/17/3/HERVE_a/HERVFH19/HERVH48/HERVS71
- **Other LTR**: LTR106_Mam, LTR108b, LTR10G, LTR12B/F, LTR14B, LTR17, LTR18B, LTR25, LTR26B, LTR44, LTR47A2, LTR80B, LTR81, LTR82B
- **MacERV family**: MacERV1-6 (LTR and internal regions)

Total: 46 TE genes in 3000 HVG set, 133 TE genes in raw features.

### ERVK_high vs Alu_high Comparison

| Feature | ERVK_high | Alu_high |
|---------|-----------|----------|
| Leiden clusters | 3, 6, 21, 24 | 17 |
| Cell count | 3373 | 481 |
| Dominant TE | ERVK2 (MacERV2) | Alu/SINE, L1/LINE, L2, MIR |
| Protein-coding markers | 125 (AMH, AREG, GJA1, RPS/RPL) | 0 (all top100 are TEs) |
| Biological status | Real cell state (TE derepression in granulosa-like cells) | TE-dominant profile, fewer genes detected |
| QC quality | Good (2574 genes, 0.16% MT) | Acceptable (1361 genes, 0.44% MT) — NOT low quality |

### Key Biological Insight

ERVK_high has real protein-coding gene expression (ovarian markers, ribosomal proteins, transcription factors) alongside high ERVK expression. This represents genuine TE derepression in a specific cell population.

Alu_high has NO protein-coding markers — its identity is entirely defined by repeat element composition. These cells have fewer detected genes because reads map to repeats, but MT% is low (0.44%) so they're not dying cells.

Both are biological phenomena (TE derepression), not QC artifacts. The distinction is that ERVK_high retains normal gene expression programs while Alu_high is dominated by repeat element mapping.

## Implementation in scRNAseq.py

### Functions Added

1. `_parse_te_bed(bed_path) -> set` — parses BED, returns set of TE names
2. `_parse_gene_tsv(tsv_path) -> Dict[str, str]` — parses CSV/TSV, returns {gene_name: gene_type}
3. `annotate_gene_type(adata, te_bed, gene_tsv)` — populates `adata.var['gene_type']`
4. `_filter_te(adata) -> adata` — subsets to non-TE genes, warns if gene_type missing

### CLI Usage

```bash
# cluster mode with TE filtering
scRNAseq.py --mode cluster --input input.h5ad --output output.h5ad --skip-te

# auto mode with TE filtering (requires gene_type pre-annotation)
scRNAseq.py --mode auto --input input.h5ad --output output.h5ad --skip-te
```

### Python Usage

```python
from scRNAseq import annotate_gene_type, _filter_te

# Step 1: Annotate gene types (must run BEFORE skip_te)
annotate_gene_type(adata,
    te_bed="/path/to/rheMac10_rmsk_TE.bed",
    gene_tsv="/path/to/geneIDAnnotation.csv")

# Step 2: Filter TE genes
adata_coding = _filter_te(adata)  # removes all genes where gene_type == 'TE'
```

### Critical Workflow Note

**`annotate_gene_type()` is NOT exposed as a CLI argument** for auto/cluster modes. The `--skip-te` flag calls `_filter_te()` which requires `gene_type` in `adata.var`. If the h5ad doesn't have `gene_type`, you must run `annotate_gene_type()` as a separate step first (see Auto Mode workflow in `references/auto_mode_llm_annotation.md`).

### Workflow

1. Run `annotate_gene_type()` on merged h5ad (before clustering) — separate Python script or inline
2. Save intermediate h5ad with `gene_type` column
3. Use `--skip-te` flag in cluster/auto modes
4. TE expression can be analyzed post-clustering as overlay on cell-type clusters
5. Rank_genes_groups with `use_raw=True` still includes TE genes for DEG analysis
