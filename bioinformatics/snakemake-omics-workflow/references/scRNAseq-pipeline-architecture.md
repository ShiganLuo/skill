# scRNAseq Pipeline Architecture (Omics)

## Dual-track design

The scRNAseq subworkflow supports parallel SC (gene) + TE (transposable element) analysis:

```
cellranger_ref (optional)
     ↓
cellranger_count (BAM + matrix)
     ↓                    ↓
cellranger_to_h5ad    scTE_quantify
     ↓                    ↓
SC scanpy pipeline    TE scanpy pipeline
(qc→cluster→batch     (qc→cluster→batch
 →annotate→advanced    →annotate→advanced
 →de)                  →de)
```

## Key modules

| Module | Purpose | Rules |
|--------|---------|-------|
| `modules/cellranger/` | Cell Ranger ref + count + h5ad conversion | `cellranger_ref`, `cellranger_count`, `cellranger_to_h5ad` |
| `modules/scTE/` | TE quantification from BAM | `scTE_build_index`, `scTE_quantify` |
| `modules/scanpy/` | Downstream analysis | `scanpy_qc`, `scanpy_cluster`, `scanpy_batch`, `scanpy_annotate`, `scanpy_advanced`, `scanpy_differential_expression` |

## Config pattern

```yaml
samples: ["sample1", "sample2"]
Procedure:
  cellranger: /path/to/cellranger
  scTE: /path/to/scTE
  scTE_build: /path/to/scTE_build
Params:
  scTE:
    enabled: true
    genome: hg38
    cb_tag: CB
    umi_tag: UB
  scanpy:
    batch:
      enabled: true
      method: bbknn  # or harmony
      batch_key: sample
    annotate:
      enabled: true
      marker_file: config/markers.tsv
      celltypist_model: Immune_All_High.pkl
    advanced:
      trajectory: true
      cnv: true
      gtf: /path/to/genes.gtf.gz
      cnv_reference: Macrophages,Mast Cell
genome:
  references:
    hg38:
      cellranger_transcriptome: /path/to/refdata-gex-GRCh38-2024-A
      scTE_index: /path/to/hg38.exclusive.idx
```

## Cell Ranger naming requirement

Cell Ranger strictly requires Illumina naming: `{sample}_S{samp}_L{lane}_{read}_{pair}.fastq.gz`.
It does NOT support custom file paths via --read1/--read2. Use `--fastqs DIR --sample PREFIX`.

For STARsolo, use `--readFilesIn R1.fq.gz R2.fq.gz` with explicit merged paths.

## scTE usage

```bash
# Build index (once per genome)
scTE_build -g hg38 -o /path/to/index

# Quantify TE per sample
scTE -i input.bam -o output -x /path/to/hg38.exclusive.idx \
     --hdf5 True -CB CB -UMI UB
```

scTE output: CSV matrix (cells × TEs), converted to h5ad by `bin/scTE_quantify.py`.

## Multi-lane FASTQ merging

`MetaUtil.prepare_scRNAseq_meta()` scans `fastq_dir` for files matching `sample_prefix`,
then:
- Single-lane: symlink to `raw_fq_dir/{sample_id}/{sample_id}_{1,2}.fq.gz`
- Multi-lane: cat-merge all R1 into one file, all R2 into one file

Merged paths stored in `samples_dict.fastq_1/fastq_2` (STARsolo).
Original `fastq_dir` + `sample_prefix` preserved for Cell Ranger.

## Rule vs script separation (user-corrected pitfall)

Rules must ONLY validate inputs/outputs and call scripts. NO inline logic in `run:`.

Correct: `params.python` + `params.script` → cmd list → write .sh → shell call.
Wrong: inline sed/awk/Python processing in the run block.

All processing logic goes into `bin/*.py` scripts with argparse CLI.
See scanpy_qc, TEcount, cellranger_ref for canonical examples.
