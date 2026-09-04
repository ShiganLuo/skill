# Wrapping Commercial Tools as Omics Modules

When a bioinformatics tool is NOT available via conda (commercial, licensed,
or binary-only — e.g. Cell Ranger, STARsolo, Space Ranger), use this pattern:

## Module structure

```
modules/<tool>/
    <tool>.smk          # snakemake rules
    <tool>.yaml          # conda env for CONVERSION SCRIPT deps only (not the tool itself)
    bin/<tool>_to_<fmt>.py  # bridge script: tool output → project-standard format
```

## Key design decisions

1. **Tool binary path**: `config["Procedure"]["<tool>"]` — defaults to the bare
   command name (e.g. `"cellranger"`), user overrides to absolute path if needed.
   The tool is NOT declared in the conda YAML.

2. **Conda YAML**: only lists dependencies for the conversion/bridge script
   (e.g. anndata, scanpy, h5py). The `container: sif(...)` points to this YAML,
   so the SIF only needs the conversion deps.

3. **Bridge rule**: converts tool-specific output to the project's standard
   format. For scRNA-seq: Cell Ranger `filtered_feature_bc_matrix/` → `.h5ad`.
   This rule uses the conda env; the tool-execution rule does NOT (it runs
   the bare binary via shell).

4. **Dual-mode subworkflow**: the subworkflow checks whether to run the
   upstream tool or accept pre-processed input:
   ```python
   use_upstream = bool(samples) and not input_h5ad and not sample_h5ad
   if use_upstream:
       # wire module rules, build sample_h5ad from tool output
   # pass sample_h5ad/input_h5ad to downstream module
   ```
   This preserves backward compatibility — users with pre-existing h5ad files
   skip the upstream tool entirely.

## Cell Ranger example (scRNAseq)

**Config**:
```yaml
samples: ["sample1", "sample2"]
indir: "data/fastq"           # FASTQs: {indir}/{sample_id}/{sample_id}_S1_L001_R1_001.fastq.gz
Procedure:
  cellranger: "/opt/cellranger-8.0/cellranger"
Params:
  cellranger:
    chemistry: "auto"
    expect_cells: 5000
    no_bam: true              # saves disk
genome:
  default: "hg38"
  references:
    hg38:
      cellranger_transcriptome: "/path/to/refdata-gex-GRCh38-2024-A"
```

**DAG**: `cellranger_count → cellranger_to_h5ad → scanpy_qc → cluster → de`

**Rule pattern** (cellranger_count):
```python
rule cellranger_count:
    input:
        fastq_dir = indir + "/{sample_id}"
    output:
        outs_dir = directory(outdir + "/{sample_id}/outs")
    params:
        cellranger = cellranger_bin,  # from Procedure config
        ...
    run:
        # 1. Write timestamped shell script
        # 2. cd to sample dir, run cellranger count
        # 3. Copy cellranger's {id}/outs/* to output.outs_dir
```

## Pitfalls

- Cell Ranger creates output at `{cwd}/{id}/outs/` — must cd to the right
  directory first, then copy outs to the declared output path.
- `--no-bam` by default to save disk space (~10x reduction). User can disable.
- The `--sample` flag must match the FASTQ filename prefix, not the directory name.
- For the bridge script, use `sc.read_10x_mtx()` (scanpy) which reads the
  `filtered_feature_bc_matrix/` directory directly — no need to parse MTX manually.
