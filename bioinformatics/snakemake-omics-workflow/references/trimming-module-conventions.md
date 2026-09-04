# Trimming Module Conventions

Two trimming modules exist: `cutadapt` (direct cutadapt) and `trim-galore` (wrapper).
Both follow identical rule naming and input/output conventions.

## Rule names (required by subworkflows)

- `trimming_Paired` — paired-end trimming
- `trimming_Single` — single-end trimming

Subworkflows import via:
```python
use rule trimming_Paired from cutadapt as <Workflow>_trimming_Paired
use rule trimming_Single from cutadapt as <Workflow>_trimming_Single
```

## Input file naming conventions

```
# Paired-end (default)
{indir}/{sample_id}/{sample_id}_1.fq.gz
{indir}/{sample_id}/{sample_id}_2.fq.gz

# Paired-end (UMI mode: config.mode == "UMI")
{indir}/{sample_id}/{sample_id}_1.umi.fq.gz
{indir}/{sample_id}/{sample_id}_2.umi.fq.gz

# Single-end (default)
{indir}/{sample_id}/{sample_id}.single.fq.gz

# Single-end (UMI mode)
{indir}/{sample_id}/{sample_id}.umi.single.fq.gz
```

## Output file naming conventions

```
# Paired-end
{outdir}/{sample_id}/{sample_id}_1.fq.gz
{outdir}/{sample_id}/{sample_id}_2.fq.gz
{outdir}/{sample_id}/{sample_id}.cutadapt_report.txt   # or trim_galore_report.txt

# Single-end
{outdir}/{sample_id}/{sample_id}.single.fq.gz
{outdir}/{sample_id}/{sample_id}.single.cutadapt_report.txt
```

## UMI mode detection

Both modules check `config.get("mode")` for UMI suffix dispatch:
```python
mode = config.get("mode") or None
```

## Downstream consumer patterns

- `bwa-mem2` expects: `{indir}/cutadapt/{sample_id}/{sample_id}_1.fq.gz`
  (subworkflow passes `indir` already pointing at cutadapt output dir)
- `hisat2/ncRNAseq` expects: `{outdir}/ncRNAseq/cutadapt/{sample_id}_cutadapt2_trimmed.fq.gz`
  (different naming convention — ncRNAseq-specific)

## Config key naming pitfall

See pitfall #46 in SKILL.md — the module directory name and the config key
(Procedure/Params) must match, OR the subworkflow must remap keys explicitly.

## Parameters file convention

Projects include a `parametes.txt` (note: original typo preserved) in the data
directory describing the trimming pipeline parameters:
```
fumitools (v0.19.0) with default commands and parameters to extract UMIs.
cutadapt: --match-read-wildcards -u 16 -a 'AAAAAAAACAAAAAAAAAA' --trimmedonly, followed by -a 'AAAA$' -a 'AAA$' -a 'AA$' -a 'A$' -m 50 -M 110
```

## Conda environment

trim-galore.yaml includes both cutadapt and trim-galore:
```yaml
dependencies:
  - cutadapt=5.2
  - trim-galore=0.6.11
```

cutadapt.yaml only needs cutadapt:
```yaml
dependencies:
  - cutadapt>=4.0
```
