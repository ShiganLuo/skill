# node.py ↔ Subworkflow Output Path Alignment

## Problem

`node.py`'s `run<Workflow>()` function constructs `outfiles` that define
the DAG boundary. These paths MUST exactly match the subworkflow's actual
output paths. When subworkflow directory structure changes, node.py must
be updated in lockstep.

## How to find the mismatch

```bash
# 1. Find the run function
grep -n "def run<Workflow>" node.py

# 2. Find the subworkflow's output directories
grep -n "outdir\|_outdir" subworkflow/<Workflow>.smk

# 3. Compare paths
```

## Example: Fiberseq workflow

Subworkflow defines:
```python
prepare_outdir = f"{outdir}/common/2_fiberseq_bam"
aligned_dir = f"{outdir}/common/3_align_bam"
analysis_outdir = f"{outdir}/results"
```

node.py must match:
```python
outfiles.append(f"{outdir}/common/2_fiberseq_bam/{sid}/{sid}.fiberseq.fire.bam")
outfiles.append(f"{outdir}/common/3_align_bam/{sid}/{sid}.fiberseq.fire.sorted.bam")
outfiles.append(f"{outdir}/results/{sid}/{sid}.m6a.bed.gz")
```

## Pitfall

When refactoring a subworkflow (renaming directories, splitting modules),
ALSO update node.py. The pipeline will run without error but `rule all`
will have wrong paths → snakemake reports "Nothing to be done" or
MissingRuleException.

## Verification

After any subworkflow refactoring:
1. `grep -A 20 "def run<Workflow>" node.py` — check outfiles paths
2. `grep "outdir\|_outdir" subworkflow/<Workflow>.smk` — check actual dirs
3. Ensure every outfile path maps to a real rule output in the subworkflow