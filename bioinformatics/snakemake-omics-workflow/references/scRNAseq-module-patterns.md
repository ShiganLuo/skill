# scRNAseq Module Patterns

## Module Rule Pattern (MUST follow)

Rules validate + call scripts only. All logic in bin/ Python scripts.

Template (from modules.md and samtools.smk):
```python
rule some_analysis:
    input: h5ad=qc_h5ad
    output: h5ad=out_h5ad
    log: logdir + "/{sample_id}/some_analysis.log"
    threads: 4
    conda: "env.yaml"
    container: sif("env.yaml")
    params:
        python=python,
        script=os.path.join(ROOT_DIR, "modules", "xxx", "bin", "xxx.py"),
        param1=params.get("param1", default),
    run:
        log_path = str(log)
        try:
            open(log_path, "w").close()                          # 1. clear old log
            rule_logger = setup_logger("some_analysis", log_file=log_path)  # 2. structured logger
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            rule_logger.info(f"Start some_analysis for sample {wildcards.sample_id} at {current_time}")
            sample_outdir = os.path.dirname(str(output.h5ad))
            os.makedirs(sample_outdir, exist_ok=True)
            script = os.path.join(sample_outdir, f"xxx_{wildcards.sample_id}_{current_time}.sh")
            cmd = [params.python, params.script, "--mode", "xxx",
                   "--input", input.h5ad, "--output", output.h5ad]
            with open(script, "w") as f:                         # 3. write .sh script
                f.write("#!/bin/bash\n")                          #    NOT #!/usr/bin/env bash
                f.write(" ".join(shlex.quote(str(item)) for item in cmd) + "\n")
                f.write(f'echo "some_analysis for {wildcards.sample_id} at {current_time} completed successfully"\n')
            shell(f"bash {script} >> {log_path} 2>&1")           # 4. no shlex.quote on script/log_path
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"Error occurred during some_analysis for sample {wildcards.sample_id}: {e}\n")
            logger.error(f"Error occurred during some_analysis for sample {wildcards.sample_id}: {e}")
            raise e
```

**Key differences from old pattern:**
- `open(log_path, "w").close()` — clears old log before run
- `setup_logger()` from common.smk — structured logging with timestamps
- `rule_logger.info(...)` — start/end markers in log
- `#!/bin/bash` — not `#!/usr/bin/env bash\nset -euo pipefail`
- `f.write(" ".join(...))` — not `f.write(shlex.join(cmd))`
- echo completion marker at end of script — success confirmation in log
- `shell(f"bash {script} >> {log_path} 2>&1")` — direct paths, no shlex.quote wrapper
- `logger.error(...)` + `raise e` — re-raise with snakemake logger
- bin/*.py scripts use `logging` module, NOT `print()` statements

**PITFALL**: Do NOT embed sed/awk/grep in .smk run blocks. Shell escaping across Python to bash to sed is fragile. Use Python in bin/ instead.

**PITFALL**: Do NOT wrap rule definitions in `if/else` in module .smk. ALL rules must be unconditionally defined. The subworkflow decides which rules to `use rule` based on config. Input functions should also be unconditional — each rule has a fixed input path. The subworkflow chains rules as needed.

## scRNAseq Pipeline Architecture

Dual-track (gene expression + transposable elements):

```
cellranger_ref (optional, from FASTA+GTF)
      |
cellranger_count (BAM + filtered matrix)
      |                    |
cellranger_to_h5ad    scTE_quantify
      |                    |
SC scanpy pipeline    TE scanpy pipeline
(qc->cluster->batch     (qc->cluster->batch
 ->annotate->advanced    ->annotate->advanced
 ->de)                  ->de)
```

## Cell Ranger Constraints

- `cellranger count --fastqs <dir> --sample <prefix>` -- auto-discovers by naming convention
- NO support for custom file paths (--read1, --read2 dont exist)
- Files must follow: `{sample}_S{samp}_L{lane}_{read}_{pair}.fastq.gz`
- For scTE: needs --create-bam=true
- Multi-lane: Cell Ranger merges automatically from directory

## scTE (Transposable Element Quantification)

```bash
scTE_build -g hg38 -o /path/to/hg38
scTE -i possorted_genome_bam.bam -o output -x hg38.exclusive.idx \
    --min_counts 1 --min_genes 1 -CB CB -UMI UB
```

- Input: Cell Ranger BAM with CB (cell barcode) and UB (UMI) tags
- Output: CSV matrix (cells x TEs)
- Convert to h5ad: pd.read_csv -> sparse csr_matrix -> AnnData
- Cell Ranger: -CB CB -UMI UB; STARsolo: -CB CR -UMI UR

## Multi-lane FASTQ Handling (MetaUtil.prepare_scRNAseq_meta)

For scRNAseq meta with fastq_dir + sample_prefix columns:
1. Scan fastq_dir for files matching sample_prefix + fq_pattern
2. Single-lane: symlink to raw_fq_dir/{sample_id}/{sample_id}_{1,2}.fq.gz
3. Multi-lane: cat-merge all R1, all R2
4. Store merged paths (STAR) + original dir/prefix (Cell Ranger)

## Config propagation: node.py → subworkflow → module

The scRNAseq config flows through 3 layers:

1. **node.py** builds runtime fields:
   - `tissue_samples = {tissue: [sid, ...]}` — groups samples by tissue
   - `datajson["Params"]["scanpy"]["tissue_samples"] = tissue_samples` — inside Params.scanpy
   - NO `sample_h5ad`, NO `tissue_map`, NO `enabled` flags

2. **scRNAseq.smk** assembles scanpy_config:
   ```python
   scanpy_params = config.get("Params", {}).get("scanpy", {})
   scanpy_config = {
       "ROOT_DIR": ROOT_DIR,
       "indir": h5ad_outdir,
       "outdir": ..., "outdir_combine": ...,
       "logdir": ..., "logdir_combine": ...,
       "Params": {"scanpy": scanpy_params},  # tissue_samples is inside here
       "Procedure": {"python": ...},
   }
   ```

3. **scanpy.smk** reads config:
   ```python
   params = config.get("Params", {}).get("scanpy", {})
   tissue_samples = params.get("tissue_samples", {})  # from Params.scanpy
   indir = config.get("indir", "input")
   ```

**Key**: `tissue_samples` is inside `Params.scanpy`, NOT top-level.
**Key**: `indir` must be explicitly defined in the module.
**Key**: No `enabled` flags — subworkflow decides what to run.

## Scanpy Pipeline Modes

modes: qc, cluster, batch, annotate, advanced, de

All rules unconditionally defined with fixed inputs (linear chain):
qc → merge → cluster → batch → annotate → advanced → de

Subworkflow decides which rules to `use rule` based on config.
- batch: BBKNN or Harmony (sc.external.pp.bbknn / sc.external.pp.harmony_integrate)
- annotate: marker-based (TSV with cell_type + markers) or celltypist
- advanced: trajectory (diffmap+dpt), velocity, communication, CNV (infercnvpy)
- CNV needs GTF for genomic positions + reference cell types

Data flow: `tissue_samples = {tissue: [sid,...]}` built in node.py, passed through subworkflow to module.
