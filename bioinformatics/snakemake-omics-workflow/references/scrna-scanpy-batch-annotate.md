# Scanpy Pipeline Expansion: batch + annotate modes

## Overview

The scanpy module (`modules/scanpy/`) was expanded from 4 modes (qc/cluster/advanced/de) to 6 modes, adding batch correction and cell annotation.

## Pipeline order

```
qc → cluster → batch → annotate → advanced → de
```

Each mode is a function in `bin/scRNAseq.py` and a rule in `scRNAseq_scanpy.smk`.

## New modes

### batch mode (BBKNN / Harmony)

Config: `Params.scanpy.batch.enabled = true`

```yaml
Params:
  scanpy:
    batch:
      enabled: true
      method: "bbknn"       # or "harmony"
      batch_key: "sample"   # column in .obs for batch info
```

Logic: PCA → neighbors → bbknn/harmony → UMAP → leiden. Requires `sample` or `batch` column in .obs.

### annotate mode (marker-based / celltypist)

Config: `Params.scanpy.annotate.enabled = true`

```yaml
Params:
  scanpy:
    annotate:
      enabled: true
      marker_file: "config/markers.tsv"        # TSV: cell_type<TAB>gene1,gene2,...
      celltypist_model: "Immune_All_High.pkl"   # celltypist model name
```

Marker file format (TSV):
```
cell_type	markers
Oligodendrocytes	MBP,MOG,MAG,KLK6
Astrocytes	AGT,AQP4,APOE
Macrophages	CDK68,TYROBP,CD163
```

Logic: scores each cell type via `sc.tl.score_genes()`, assigns by highest score. celltypist runs as alternative.

## Conditional rules

Both `scanpy_batch` and `scanpy_annotate` are conditional in the smk file:
```python
if batch_enabled:
    rule scanpy_batch: ...
if annotate_enabled:
    rule scanpy_annotate: ...
```

The `advanced_input` chain adapts:
- annotate enabled → advanced reads from annotate_h5ad
- batch enabled → advanced reads from batch_h5ad
- neither → advanced reads from cluster_h5ad

## CNV enhancement

The advanced mode gained `--gtf` and `--cnv-reference` params for infercnvpy:
```yaml
advanced:
  cnv: true
  gtf: "/path/to/genes.gtf.gz"
  cnv_reference: "Macrophages,Mast Cell"  # comma-separated reference cell types
```
