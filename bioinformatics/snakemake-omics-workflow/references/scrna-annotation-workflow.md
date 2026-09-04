# scRNA-seq Annotation Workflow (scanpy scRNAseq.py)

## Pipeline Modes

The `scanpy.py` script supports: `qc -> merge -> cluster -> batch -> annotate -> advanced -> de`

### Critical Pitfall: annotate mode without --marker-file

The `annotate` mode does NOTHING if none of these are provided:
- `--marker-file` (TSV with `cell_type` and `markers` columns)
- `--celltypist-model`
- `--llm-method`

Without one of these, it just plots `rank_genes_groups` and writes the h5ad unchanged. **Always provide a marker file for tissue-specific annotation.**

### Marker File Format

```
cell_type	markers
Oocyte	DDX4,DAZL,GDF9,ZP3,FIGLA,NOBOX,SYCP3
Granulosa	FSHR,CYP19A1,AMH,FOXL2,BMPR1B,LHCGR
```

- Tab-separated, columns: `cell_type`, `markers` (comma-separated gene names)
- Genes not in the h5ad `var_names` are silently skipped
- Score-based assignment: `sc.tl.score_genes()` per cell type, then `idxmax` to assign

## Resolution Tuning

| Tissue | Resolution | Expected Clusters | Notes |
|--------|-----------|-------------------|-------|
| Ovary | 0.5 | ~25 | 0.8 gives31 (over-clustered) |
| General | 0.8 | ~30-40 | Default, may over-cluster |

Rule of thumb: expect 8-15 major cell types for most tissues. Resolution 0.3-0.5 is often better than default 0.8.

## Merge Step: No HVG Selection

The `mode_merge` does NOT set `highly_variable` in `adata.var`. The `mode_cluster` checks:
```python
if "highly_variable" in adata.var:
    adata = adata[:, adata.var.highly_variable].copy()
```

Without HVG, **all genes** are scaled and used for PCA. For large datasets (60k+ cells, 25k+ genes), this causes:
- Very slow `sc.pp.scale()` (sparse -> dense conversion)
- High memory usage (~50GB for62k x 26k)
- Long h5ad write times

Workaround: either set HVG before cluster, or accept the longer runtime.

## Macaque Ovary Cell Type Markers

Verified markers for Macaca mulatta ovaries (all found in both cellranger and scTE):

| Cell Type | Markers | Notes |
|-----------|---------|-------|
| Oocyte | DDX4, DAZL, GDF9, ZP3, FIGLA, NOBOX, SYCP3 | Germline-specific |
| Granulosa | FSHR, CYP19A1, AMH, FOXL2, BMPR1B, LHCGR | Follicle support |
| Theca | CYP17A1, IGF1, STAR, CYP11A1 | Androgen production |
| Stromal | COL1A1, COL3A1, DCN, LUM, VIM, PDGFRA | ECM/connective tissue |
| Smooth_muscle | ACTA2, MYH11, TAGLN, CNN1, DES | Vascular/theca externa |
| Endothelial | PECAM1, VWF, CDH5, KDR, EMCN | Blood vessels |
| Macrophage | CD68, CD163, CD74, CSF1R, C1QA | Tissue-resident immune |
| T_NK_cell | CD3E, CD3D, CD8A, NKG7, GZMB | Adaptive immunity |
| B_cell | CD79A, CD79B, MS4A1, PAX5 | Humoral immunity |
| OSE | KRT18, EPCAM, WT1, LGR5, UPK3B | Ovarian surface epithelium |
| Pericyte | RGS5, PDGFRB, NOTCH3, ABCC9 | Vascular support |
| Luteal | HSD3B1, PRLR, LHCGR, STAR | Corpus luteum |
| Proliferating | MKI67, TOP2A, PCNA, CENPF | Cell cycle active |

Note: KRT8 is NOT in the macaque reference; use KRT18 instead.

## Typical Cell Type Proportions (Ovary)

From a 62k cell dataset:
- Endothelial/Stromal/Smooth_muscle: most abundant (~15-20% each)
- Pericyte/OSE: moderate (~10-15%)
- Granulosa/Theca: moderate (~5-10%)
- Immune (T/B/Mac): ~5-10% combined
- Oocyte: rare (~1-2%)
- Luteal/Proliferating: ~3-5%

## Command Examples

```bash
# Cluster
python scRNAseq.py --mode cluster --input merged.h5ad --output clustered.h5ad \
  --markers markers.tsv --n-pcs 50 --n-neighbors 15 --resolution 0.5 \
  --plot-dir plots/cluster

# Annotate (MUST provide --marker-file)
python scRNAseq.py --mode annotate --input clustered.h5ad --output annotated.h5ad \
  --marker-file macaque_ovary_markers.tsv --tissue ovaries --annotate-group leiden \
  --plot-dir plots/annotate

# Advanced (trajectory)
python scRNAseq.py --mode advanced --input annotated.h5ad --output advanced.h5ad \
  --n-pcs 50 --n-neighbors 15 --trajectory --plot-dir plots/advanced
```
