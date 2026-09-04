# Shlex quoting and wildcard constraints in Snakemake modules

## Rule: ALWAYS use `shlex.quote()` when writing cmd lists to bash scripts

The pattern `" ".join(cmd)` breaks when arguments contain shell metacharacters.

```python
# At top of .smk file:
import shlex

# When writing the script:
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")
```

This handles: values with spaces (`"heatmap and colorbar"`), semicolons (`"Pop5IP:Pop5Input;Rpp14IP:Pop5Input"`), empty strings.

**Every module `.smk` that writes bash scripts MUST use this pattern.**

## `wildcard_constraints` for repeated wildcard patterns

When a rule output has `{sample_id}` appearing TWICE in the path:
```python
output:
    flag = outdir + "/{sample_id}/{sample_id}.fastqc." + log_suffix
```

Snakemake's greedy regex can match `Pop5IP/Pop5IP.fastqc.txt` as a single `{sample_id}`. Fix:
```python
wildcard_constraints:
    sample_id = "[^/]+"
```

## DAG reverse-pulling: samples expand beyond config["samples"]

When rule A's `expand()` depends on outputs of rule B with `{sample_id}`, ALL samples matching rule A's wildcard get pulled into rule B — even if rule B's module config only lists a subset.

**Example**: `peak_te_overlap` uses `expand(..., sid=ip_samples + input_samples)`, which requires `{sample}_peaks.narrowPeak` for ALL samples. This forces `macs3_callpeak` to run on Input samples too, even though `macs3_config["samples"] = ip_samples`.

**Fix**: Ensure `expand()` in downstream rules only lists samples that should actually be produced by upstream rules.

## `_result` rule convention

Every module should have a `<module>_result` rule for subworkflow import:
```python
rule <module>_result:
    """Result aggregation rule for subworkflow use rule import."""
    input:
        main_output = outdir + "/{sample_id}/{sample_id}_main_output.txt",
```

The `_result` rule declares the MAIN outputs only. Use `shlex.quote()` in run blocks.
