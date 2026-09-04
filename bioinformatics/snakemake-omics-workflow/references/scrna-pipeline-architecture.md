# scRNA-seq Pipeline Architecture (Omics Snakemake)

## Module Rule Convention (user-corrected)

**Rules MUST ONLY validate + assemble cmd + call shell. ALL logic goes in `bin/` Python scripts.**

The user explicitly corrected: "规则只负责校验和调用,相关代码包装成脚本"
(rules only handle validation and calling, code should be wrapped in scripts).

### Correct pattern (scanpy_qc-style)

```python
# In .smk rule:
params:
    python=python,
    script=script,
    # all args as params
run:
    log_path = str(log)
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        command_script = os.path.join(..., f"step_{current_time}.sh")
        cmd = [params.python, params.script, "--mode", "qc", "--input", input.h5ad, ...]
        with open(command_script, "w") as handle:
            handle.write("#!/usr/bin/env bash\nset -euo pipefail\n")
            handle.write(" ".join(shlex.quote(str(item)) for item in cmd) + "\n")
        shell(f"bash {shlex.quote(command_script)} >> {shlex.quote(log_path)} 2>&1")
    except Exception as exc:
        with open(log_path, "a") as handle:
            handle.write(f"step failed: {exc}\n")
        raise
```

### WRONG pattern (inline logic in rule)

```python
# DON'T: sed/awk/grep inline in .smk run blocks
# DON'T: biotype filtering logic in .smk
# DON'T: download/modify/filter steps as inline shell in .smk
```

## Bash Script Generation Pitfall

When generating bash scripts with sed/awk regex from Python:

**WRONG**: List-based approach with `\\\\` escaping — fragile, hard to debug:
```python
lines = [
    "    | sed -E 's/^(\\\\S+).*/>\\\\1 \\\\'1/' \\\\",
    # quadruple backslashes → easy to get wrong
]
```

**CORRECT**: Triple-quoted f-string — clean, escaping works naturally:
```python
script_content = f"""#!/usr/bin/env bash
set -euo pipefail
cat {q(input)} \\
    | sed -E 's/^>(\\S+).*/>\\1 \\1/' \\
    | sed -E 's/^>([0-9]+|[XY]) />chr\\1 /' \\
    > {q(output)}
"""
with open(script_path, "w") as f:
    f.write(script_content)
```

In Python triple-quoted f-strings: `\\S` → `\S` in string → `\S` in bash single quotes → sed sees `\S` (non-whitespace). Correct.

## scTE Module (TE Quantification)

For single-cell transposable element analysis, use scTE:

### Pipeline flow
```
cellranger_count (with --create-bam=true)
    ↓                    ↓
cellranger_to_h5ad    scTE_quantify
    ↓                    ↓
SC scanpy pipeline    TE scanpy pipeline
```

### scTE module structure
```
modules/scTE/
├── scTE.smk           # rules: scTE_build_index, scTE_quantify
├── scTE.yaml          # conda env (pip install scTE)
└── bin/
    └── scTE_quantify.py  # wrapper: BAM → scTE → CSV → h5ad
```

### scTE CLI usage
```bash
# Build index (one-time per genome)
scTE_build -g hg38 -o /path/to/index/hg38

# Quantify TE from Cell Ranger BAM
scTE -i sample.bam -o output_dir -x /path/to/hg38.exclusive.idx \
     -p 20 -CB CB -UMI UB
```

### Key config fields
```yaml
Params:
  scTE:
    enabled: true
    genome: "hg38"
    cb_tag: "CB"      # Cell Ranger uses CB, STARsolo uses CR
    umi_tag: "UB"     # Cell Ranger uses UB, STARsolo uses UR
genome:
  references:
    hg38:
      scTE_index: "/path/to/hg38.exclusive.idx"
```

### Cell Ranger BAM requirement
Cell Ranger must be run with `--create-bam=true` (or `--no-bam=false`) to produce the BAM file that scTE needs. The default cellranger_count rule uses `--no-bam=true` — override this when scTE is enabled.

## Dual-Track SC + TE Analysis

The scRNAseq subworkflow supports parallel gene expression (SC) and transposable element (TE) tracks:

```python
# In scRNAseq.smk:
if scte_enabled:
    # TE track uses separate scanpy module instance
    te_scanpy_config = dict(config)
    te_scanpy_config.update({"outdir": f"{outdir}/TE", "sample_h5ad": te_sample_h5ad})
    module te_scanpy:
        snakefile: "../modules/scanpy/scRNAseq_scanpy.smk"
        config: te_scanpy_config
    use rule scanpy_qc from te_scanpy as scRNAseq_te_scanpy_qc
    # ... etc
```

Each track runs independently through the full scanpy pipeline (qc → cluster → batch → annotate → advanced → de).

## Scanpy Pipeline Modes

The `modules/scanpy/bin/scRNAseq.py` script supports 6 modes:

| Mode | Input | Output | Key params |
|------|-------|--------|------------|
| qc | raw h5ad | filtered h5ad | min_genes, max_genes, max_pct_mt, n_top_genes |
| cluster | filtered h5ad | clustered h5ad | n_pcs, n_neighbors, resolution |
| batch | clustered h5ad | batch-corrected h5ad | batch_method (bbknn/harmony), batch_key |
| annotate | batched h5ad | annotated h5ad | marker_file (TSV), celltypist_model |
| advanced | annotated h5ad | advanced h5ad | trajectory, velocity, communication, cnv, gtf, cnv_reference |
| de | advanced h5ad | de h5ad + markers.tsv | (uses leiden or condition) |

Pipeline order: qc → cluster → batch → annotate → advanced → de

### Batch correction methods
- **BBKNN**: `sc.external.pp.bbknn(adata, batch_key='sample')` — fast, good for similar batches
- **Harmony**: `sc.external.pp.harmony_integrate(adata, key='sample')` — better for diverse batches

### Annotation methods
- **Marker file**: TSV with columns `cell_type` and `markers` (comma-separated genes). Uses `sc.tl.score_genes()`.
- **Celltypist**: `celltypist.annotate()` with pre-trained models (e.g. `Immune_All_High.pkl`)

### CNV analysis
Uses `infercnvpy`. Requires GTF for genomic position and reference cell types:
```python
cnv.io.genomic_position_from_gtf(gtf, adata)
cnv.tl.infercnv(adata, reference_key="cell_type", reference_cat=["Macrophages", "Mast Cell"])
```

## Cell Ranger Reference Building

The `cellranger_ref` rule builds a Cell Ranger reference from Ensembl FASTA + GENCODE GTF:

1. Download FASTA/GTF (URL or local)
2. Modify FASTA headers (add chr prefix, handle chrM)
3. Strip Ensembl ID version suffixes from GTF
4. Filter GTF by biotype allowlist (protein_coding, lncRNA, IG/TR genes)
5. Remove PAR_Y genes from chrY
6. Run `cellranger mkref`

All logic is in `modules/cellranger/bin/cellranger_ref.py`. The rule only calls it.

Config: `Params.cellranger_ref.fasta` (URL/path), `Params.cellranger_ref.gtf` (URL/path)
