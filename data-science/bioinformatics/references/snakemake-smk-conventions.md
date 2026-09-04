# Snakemake smk Rule Command Construction Conventions

## Always use cmd list + shlex.quote()

All smk rules should construct commands as lists and write to scripts with `shlex.quote()`:

```python
import shlex

# CORRECT
cmd = ["tool", "--arg", value, "--flag"]
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")

# WRONG — values with spaces/semicolons break bash
f.write(" ".join(cmd) + "\n")
```

## argparse nargs="+" with multiple args

When passing multiple values for the same flag, pass each separately:

```python
# CORRECT — each sample is a separate --samples arg
for s in samples:
    cmd += ["--samples", s]

# WRONG — joins into one string, argparse receives as single element
cmd += ["--samples", " ".join(samples)]
```

## Full config parameter chain

```
config/PeakCalling.json          →  Params.module.param
subworkflow/PeakCalling.smk      →  module_config["Params"] = config.get("Params", {}).get("module", {})
modules/module/module.smk        →  config.get("Params", {}).get("module", {}).get("param", default)
rule params:                     →  param = config.get("Params", {}).get("module", {}).get("param", default)
cmd list:                        →  "--param", str(params.param)
shlex.quote:                     →  handles spaces in values
```

Every layer must pass Params through — forgetting the subworkflow config step means the module reads empty dict.

## TE GTF hierarchy (RepeatMasker)

| Level | GTF attribute | Example |
|-------|--------------|---------|
| class | class_id | LINE, SINE, LTR, DNA, Satellite |
| family | family_id | L1, B2, ERV1, Alu, MIR |
| subfamily | gene_id | L1MdA_I, B1_Mur1, B2_Mm1a, GSAT_MM |

For subfamily-level analysis, use `gene_id` (most specific), not `family_id`.

## ChIP-seq enrichment at TE regions

Correct approach: count reads from IP and Input BAMs in peak-TE overlap regions.

```
1. bedtools intersect peaks + TE GTF → overlap BED
2. Extract overlap regions as BED
3. samtools view -b -F 1024 → filter duplicates → tmp.bam
4. bedtools coverage -a regions -b tmp.bam -counts → read counts
5. Per subfamily: log2(sum_IP_reads / sum_Input_reads)
```

Input samples should NOT have peaks called on them (they are background).
The enrichment TSV has both `ip_reads` and `input_reads` columns in the same row.
