# Snakemake Module Conventions & Pitfalls

## Command construction: always use cmd list + shlex.quote()

Never write commands with f-strings. Always:
1. Build a `cmd = [...]` list
2. Write to script with `" ".join(shlex.quote(str(c)) for c in cmd)`

```python
# WRONG — values with spaces break
f.write(f'--title "{params.title}" \\\n')

# RIGHT
cmd = ["python3", script, "--title", params.title, ...]
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")
```

Requires `import shlex` at top of .smk file.

## Module result rule convention

Every module must have a `*_result` rule for subworkflow import:

```python
rule <module>_result:
    """Result aggregation rule for subworkflow use rule import."""
    input:
        main_output = outdir + "/{sample_id}/{sample_id}_main_output.txt",
```

## Params passing chain (3 steps)

When a module reads `config.get("Params", {}).get("module_name", {})`, ALL THREE steps must exist:

1. **Config JSON** (`config/Workflow.json`):
   ```json
   "Params": { "my_module": { "option": "value" } }
   ```

2. **Subworkflow config dict** (`subworkflow/Workflow.smk`):
   ```python
   my_module_config = {
       ...
       "Params": {
           "my_module": config.get("Params", {}).get("my_module", {}),
       },
   }
   ```
   **PITFALL**: Forgetting step 2 means the module reads empty dict and uses all defaults silently.

3. **Module reads** (`modules/my_module/my_module.smk`):
   ```python
   option = config.get("Params", {}).get("my_module", {}).get("option", "default")
   ```

## Subworkflow import path alignment

When importing a module rule via `use rule ... from module as Workflow_...`, the module's `outdir` from config must match where upstream rules actually write files.

**PITFALL**: If upstream writes to `outdir/results/peaks/` but module expects `outdir/peaks/`, MissingInputException occurs.

Fix: pass explicit subdirectory paths in the module config:
```python
report_config = {
    "outdir": outdir,
    "peaks_dir": f"{outdir}/results/peaks",
    "annotation_dir": f"{outdir}/results/annotation",
    "log_sample_dir": f"{logdir}/sample",
}
```

Then module reads: `peaks_dir = config.get("peaks_dir", outdir + "/peaks")`

## Wildcard greedy matching with repeated wildcards

When a pattern has `{sample_id}` twice:
```
outdir + "/{sample_id}/{sample_id}.fastqc.txt"
```

Snakemake's regex is greedy — the first `{sample_id}` may match `Pop5IP/Pop5IP` instead of just `Pop5IP`.

Fix: add `wildcard_constraints` at module level:
```python
wildcard_constraints:
    sample_id = "[^/]+"
```

## TE GTF hierarchy (for ChIP-seq / peak-TE overlap)

The repeatMasker TE GTF has three levels:
- `class_id`: LINE, SINE, LTR, DNA, Satellite (broadest)
- `family_id`: L1, B2, ERV1, Alu, MIR (middle)
- `gene_id`: Lx2B2, B1_Mur1, L1MdV_III (most specific = subfamily)

For subfamily-level analysis, use `gene_id` (not `family_id`).

## ChIP-seq TE enrichment visualization

For showing IP vs Input enrichment across TE subfamilies:
- Metric: log2(normalized_IP_count / normalized_Input_count)
- Normalize by total peaks per sample (CPM-like)
- Bar chart: orange=IP enriched (positive), blue=Input enriched (negative)
- Top panel: mean TE length line plot for reference
- Sort by mean TE length (ascending) by default

Do NOT use box plots for count-based metrics — they are for distributions (interval overlap fractions).

## shell: block does NOT see Python variables

In a `shell:` block, `{VAR}` is always resolved by Snakemake as a template variable (wildcard, input, output, params). Python variables in scope are invisible:

```python
MY_SCRIPT = os.path.join(MODULE_DIR, "bin", "tool.py")

rule my_rule:
    shell:
        "python3 {MY_SCRIPT} ..."  # WRONG: Snakemake looks for wildcard/input/params.MY_SCRIPT
```

**Fix:** Either use `params:` to pass the path, or use `run:` block where Python variables are accessible:

```python
# Option A: params
rule my_rule:
    params: script = os.path.join(MODULE_DIR, "bin", "tool.py")
    shell: "python3 {params.script} ..."

# Option B: run block
rule my_rule:
    run:
        cmd = ["python3", MY_SCRIPT, ...]
```

## Optional inputs: return `[]` not `""`

When a rule has optional inputs (e.g., GTF only needed for some modes), the input function MUST return `[]` (empty list) for "no file", NOT `""` (empty string). Snakemake treats `""` as a file path and raises:

```
Empty file path encountered. Snakemake cannot understand this.
If you want to indicate 'no file', please use an empty list ([]) instead of an empty string ('').
```

```python
# WRONG
def get_gtf(wildcards):
    if mode == "tss":
        return gtf
    return ""  # ERROR

# RIGHT
def get_gtf(wildcards):
    if mode == "tss":
        return gtf
    return []  # OK
```

This also causes silent cascade in dry-runs — Snakemake may re-evaluate the entire DAG.

## use rule and module-level variables

When importing a rule via `use rule X from module as Y`, module-level variables defined in the imported Snakefile are NOT accessible inside the rule. Only `config` values (passed via the module config dict) and `params:` are available.

```python
# In modules/my_module/my_module.smk:
MY_SCRIPT = os.path.join(MODULE_DIR, "bin", "tool.py")  # module-level

rule my_rule:
    run:
        cmd = ["python3", MY_SCRIPT]  # FAILS when imported via use rule
```

**Fix:** Compute the path in `params:`:

```python
rule my_rule:
    params:
        script = os.path.join(MODULE_DIR, "bin", "tool.py"),  # MODULE_DIR comes from config
    run:
        cmd = ["python3", params.script]  # OK — params are resolved per-rule
```

`MODULE_DIR` itself is safe because it's computed from `config.get("ROOT_DIR")` which is passed through the module config dict.

## Report module input completeness

Report Snakefiles must list ALL module outputs as explicit `input:` dependencies. Missing inputs cause Snakemake to skip dependency tracking and can lead to stale reports.

Checklist for ChIP-seq report inputs:
- narrowPeak, broadPeak, xls (narrow + broad), summits, cutoff_analysis (narrow + broad)
- FRiP score files
- HOMER annotation files
- Bowtie2 logs AND metrics (both needed)
- MarkDuplicates metrics
- TrimGalore stats (R1 + R2)
- TE subfamily overlap (with `te_class` column — class info merged into subfamily TSV)
- TE enrichment PNGs (one per IP-input pair)
- Peak-centric TE summary (`{sample}_peak_centric_te.tsv`)

Each module's output files must be enumerated — use `expand()` with the sample list.
