# scRNAseq Pipeline Pattern (Cell Ranger → scTE → Scanpy)

## Architecture

Dual-track pipeline: SC (gene expression) + TE (transposable elements) processed in parallel through independent Scanpy instances.

```
cellranger_ref (optional, from Ensembl FASTA + GENCODE GTF)
     ↓
cellranger_count (BAM + filtered matrix)
     ↓                    ↓
cellranger_to_h5ad    scTE_quantify
     ↓                    ↓
SC scanpy pipeline    TE scanpy pipeline
(qc→cluster→batch     (qc→cluster→batch
 →annotate→advanced     →annotate→advanced
 →de)                   →de)
```

## Module structure (rule bodies must delegate to scripts)

```
modules/cellranger/
  cellranger.smk          # rules: cellranger_ref, cellranger_count, cellranger_to_h5ad
  cellranger.yaml         # conda env
  bin/cellranger_ref.py   # download FASTA/GTF, modify headers, filter biotypes, mkref
  bin/cellranger_to_h5ad.py  # 10x matrix → h5ad

modules/scTE/
  scTE.smk                # rules: scTE_build_index, scTE_quantify
  scTE.yaml               # conda env
  bin/scTE_quantify.py    # wrapper: call scTE CLI, convert CSV → h5ad

modules/scanpy/
  scRNAseq_scanpy.smk     # rules: qc, cluster, batch, annotate, advanced, de
  bin/scRNAseq.py          # argparse modes: qc/cluster/batch/annotate/advanced/de
```

## Rule body pattern (MANDATORY)

Rules ONLY validate inputs and call scripts. Logic goes in `bin/*.py`.

```python
rule scanpy_qc:
    input: h5ad=inputs
    output: h5ad=qc_h5ad, metrics=outdir + "/scanpy/qc/qc_metrics.tsv"
    params: python=python, script=script, min_genes=200, ...
    run:
        log_path = str(log)
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            command_script = os.path.join(...)
            cmd = [params.python, params.script, "--mode", "qc", "--input"] + list(input.h5ad) + [...]
            with open(command_script, "w") as handle:
                handle.write("#!/usr/bin/env bash\nset -euo pipefail\n")
                handle.write(" ".join(shlex.quote(str(item)) for item in cmd) + "\n")
            shell(f"bash {shlex.quote(command_script)} >> {shlex.quote(log_path)} 2>&1")
        except Exception as exc:
            with open(log_path, "a") as handle: handle.write(f"failed: {exc}\n")
            raise
```

## Cell Ranger constraints

- Cell Ranger `count` requires `--fastqs DIR --sample PREFIX` — auto-discovers files by Illumina naming convention `{sample}_S{samp}_L{lane}_{read}_{pair}.fastq.gz`
- Cannot specify custom R1/R2 paths directly — no `--read1`/`--read2` flags
- Multi-lane files in same dir with same prefix are auto-merged
- For custom-named files, use symlinks or rename
- Cell Ranger needs `--create-bam=true` (or `--no-bam=false`) for scTE downstream

## scTE usage

```bash
# Build index — download mode (one-time per genome)
scTE_build -g hg38 -o /path/to/hg38 -m exclusive

# Build index — resource mode (local gene GTF + TE BED)
scTE_build -gene gencode.v30.annotation.gtf.gz -te rmsk.bed \
    -o /path/to/hg38 -m exclusive -g other

# Quantify from Cell Ranger BAM
scTE -i sample.bam -o output_prefix -x /path/to/hg38.exclusive.idx \
     --hdf5 True -CB CB -UMI UB -p 20
```

- `scTE_build_index` rule is dual-mode: branches on `Params.scTE.gene_gtf` + `Params.scTE.te_bed`
- See `references/scrna-scTE-module.md` for TE BED format and conversion
- See `references/dual-mode-rules.md` for the dual-mode pattern
- `-CB CB -UMI UB` for Cell Ranger BAM tags
- `-CB CR -UMI UR` for STARsolo BAM tags
- Output: CSV or h5ad (--hdf5 True)

## MetaUtil prepare_scRNAseq_meta

Meta format (one row per sample, multi-lane merged):
```
sample_id  design    group   fastq_dir   sample_prefix  organism
S1         ctr_age   youth   /path/fq    S1             mulatta
```

The function:
1. Scans fastq_dir for files matching sample_prefix + fq_pattern
2. Single-lane: symlink → `raw_fq_dir/{sample_id}/{sample_id}_{1,2}.fq.gz`
3. Multi-lane: cat-merge all R1, all R2
4. Returns `Dict[str, cellranger_input]` (fastq_dir + sample_prefix) for Cell Ranger

## Scanpy batch correction + annotation modes

Added to `bin/scRNAseq.py`:
- `mode_batch()`: BBKNN or Harmony batch correction after clustering
- `mode_annotate()`: marker-based (TSV file) or celltypist annotation

Config example:
```json
{
  "Params": {
    "scanpy": {
      "batch": {"enabled": true, "method": "bbknn", "batch_key": "sample"},
      "annotate": {"enabled": true, "marker_file": "config/markers.tsv", "celltypist_model": "Immune_All_High.pkl"},
      "advanced": {"trajectory": true, "cnv": true, "gtf": "/path/genes.gtf.gz", "cnv_reference": "Macrophages,Mast Cell"}
    },
    "scTE": {"enabled": true, "genome": "hg38", "cb_tag": "CB", "umi_tag": "UB"}
  }
}
```
