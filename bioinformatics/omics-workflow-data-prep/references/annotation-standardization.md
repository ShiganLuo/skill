# Annotation Standardization

Standardize gene GTF and TE BED files for consistent downstream analysis.

## Problem

Different reference genomes use inconsistent naming:
- Chromosomes: `chr1` (UCSC) vs `1` (Ensembl), `chrM`/`chrMT`/`MT`/`M`
- Mitochondrial genes: `MT-ND1` (human) vs `ND1` (macaque RefSeq)

Downstream tools (Scanpy, Seurat) expect `MT-` prefix for QC metrics:
```python
# Scanpy
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None)
# Matches: adata.var_names.str.startswith('MT-')

# Seurat
PercentageFeatureSet(pattern = '^MT-')
```

## Solution

Script: `workflow/Omics/src/annotation/standardize_annotations.py`

Features:
1. Strip `chr` prefix from chromosomes (UCSC → Ensembl)
2. Normalize mitochondrial chromosome: `chrM`/`chrMT`/`M` → `MT`
3. Add `MT-` prefix to mitochondrial gene names (idempotent)
4. Support gzipped files (.gtf.gz)
5. `--dry-run` mode for preview
6. `--scan` mode to find all annotation files

Usage:
```bash
# Preview changes
python3 workflow/Omics/src/annotation/standardize_annotations.py \
  --gtf <gene.gtf> --te <te.bed> --species mulatta --dry-run

# Apply changes
python3 workflow/Omics/src/annotation/standardize_annotations.py \
  --gtf <gene.gtf> --te <te.bed> --species mulatta

# Scan database
python3 workflow/Omics/src/annotation/standardize_annotations.py \
  --scan /home/luosg/Database/Reference
```

## Mitochondrial Gene Names

Standard Ensembl/RefSeq names that get `MT-` prefix:
```
ATP6, ATP8, COX1, COX2, COX3, CYTB,
ND1, ND2, ND3, ND4, ND4L, ND5, ND6
```

Human/mouse GTFs typically already have `MT-` prefix.
Macaque (Mmul_10) RefSeq GTF does NOT have the prefix.

## QC Gene Categories

Standard scRNA-seq QC checks:
1. **Mitochondrial (MT-)**: High % → cell death/damage
2. **Ribosomal (RPS/RPL)**: High % → cell stress/activation
3. **Hemoglobin (HB-)**: RBC contamination
4. **Platelet (PPBP, PF4)**: Platelet contamination

Check naming conventions before running QC.
