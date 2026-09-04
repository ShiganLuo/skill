# Cell Ranger output structure and integration

## Cell Ranger count output

```
<output-dir>/<sample_id>/
└── outs/
    ├── web_summary.html
    ├── metrics_summary.csv
    ├── possorted_genome_bam.bam
    ├── possorted_genome_bam.bam.bai
    ├── raw_feature_bc_matrix/
    │   ├── barcodes.tsv.gz
    │   ├── features.tsv.gz
    │   └── matrix.mtx.gz
    ├── filtered_feature_bc_matrix/
    │   ├── barcodes.tsv.gz
    │   ├── features.tsv.gz
    │   └── matrix.mtx.gz
    ├── filtered_feature_bc_matrix.h5
    ├── raw_feature_bc_matrix.h5
    ├── molecule_info.h5
    ├── cloupe.cloupe
    └── analysis/
```

## Key path: `<output-dir>/<sample_id>/outs/`

Cell Ranger `count --id <sample_id> --output-dir <dir>` creates:
`<dir>/<sample_id>/outs/...`

NOT `<dir>/outs/...` — the `--id` becomes a subdirectory inside `--output-dir`.

## smk rule output declaration

All output paths MUST include `/outs/`:
```python
output:
    bam = outdir + "/{sample_id}/outs/possorted_genome_bam.bam",
    filtered_h5 = outdir + "/{sample_id}/outs/filtered_feature_bc_matrix.h5",
    filtered_barcode = outdir + "/{sample_id}/outs/filtered_feature_bc_matrix/barcodes.tsv.gz",
    # ...
```

## --output-dir and --id interaction

```bash
# Creates: /results/sample1/outs/...
cellranger count --id sample1 --output-dir /results

# WRONG — creates: /results/sample1/sample1/outs/...
cellranger count --id sample1 --output-dir /results/sample1
```

Use `--output-dir outdir` (the parent), NOT `outdir/sample_id`.

## Downstream: cellranger_to_h5ad

Input should be the `outs/` directory:
```python
input:
    outs_dir = outdir + "/{sample_id}/outs"
```

## --create-bam format

Cell Ranger expects lowercase `"true"` or `"false"`:
```python
"--create-bam", str(params.create_bam).lower(),
```

## Bundled tools

Cell Ranger bundles its own STAR (2.7.2a) and samtools (1.16.1) in
`lib/bin/`. These are used internally — the conda env's samtools is
for custom scripts only.

## Pitfall: anndata pandas incompatibility in SIF

When building a Cell Ranger SIF with conda env for h5ad conversion,
pin `anndata>=0.10` to avoid `pandas.core.index` removal error.
See `apptainer-sif-build-pitfalls.md` section 7.
