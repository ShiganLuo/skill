# Smk `run:` Block Conventions

## Command construction (MANDATORY)

All smk `run:` blocks MUST use `cmd` list + `shlex.quote()`, NOT f-string command construction.

```python
# CORRECT
import shlex  # at top of .smk file

cmd = [
    "python", SCRIPT,
    "--input", input.file,
    "--output", output.result,
    "--title", params.title,  # spaces OK — shlex.quote handles it
]
script = os.path.join(sample_outdir, f"my_rule_{current_time}.sh")
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")
shell(f"bash {script} >> {log_path} 2>&1")

# WRONG — f-string construction breaks on spaces in values
f.write(f"python {script} --title {params.title}\n")
```

Every `.smk` file that has a `run:` block with command construction needs `import shlex` at the top.

## Module `*_result` rule convention

Every module MUST have a `*_result` rule that declares the main outputs for subworkflow import:

```python
rule macs3_result:
    """Result aggregation rule for subworkflow use rule import."""
    input:
        peak = outdir + "/{sample_id}/{sample_id}_peaks.narrowPeak",
        xls = outdir + "/{sample_id}/{sample_id}_peaks.xls",
```

The subworkflow imports via `use rule macs3_result from macs3 as PeakCalling_macs3_result`. Without this rule, downstream dependencies cannot reference the module's outputs by name.

The result rule is a no-run rule (only `input:` section, no `run:` or `shell:`). It just declares the canonical outputs.

## Wildcard constraints for repeated wildcards

When an output pattern has the same wildcard twice (e.g., `{sample_id}/{sample_id}.fastqc.txt`), Snakemake's greedy regex can overmatch. Add `wildcard_constraints`:

```python
wildcard_constraints:
    sample_id = "[^/]+"

rule fastqc:
    output:
        flag = outdir + "/{sample_id}/{sample_id}.fastqc." + log_suffix
```

Without the constraint, Snakemake may match `Pop5IP/Pop5IP.fastqc.txt` as a single `sample_id` value instead of correctly splitting into two `Pop5IP` matches.

## deeptools plotHeatmap `--whatToShow` valid values

Valid choices (exact strings, case-sensitive):
- `"plot, heatmap and colorbar"`
- `"plot and heatmap"`
- `"heatmap only"`
- `"heatmap and colorbar"`

Do NOT use comma-separated custom values like `"heatmap, colorbar, metagene"` — they will fail silently.

## TE GTF hierarchy (rmsk_TE.gtf)

The TE annotation GTF has three levels of specificity:

| Level | Attribute | Examples |
|-------|-----------|----------|
| class | `class_id` | LINE, SINE, LTR, DNA, Satellite |
| family | `family_id` | L1, B2, ERV1, ERVL, Alu, MIR |
| subfamily | `gene_id` | Lx2B2, B1_Mur1, B2_Mm1a, L1MdV_III |

For subfamily-level analysis, use `gene_id` (most specific), not `family_id`.

## argparse repeated flags: use `action="append"` not `nargs="+"`

When Snakefile builds a command with repeated flags in a loop:

```python
for s in ip_samples:
    cmd += ["--samples", s]
# Produces: --samples Pop5IP --samples Rpp14IP --samples Rpp21IP
```

The Python script MUST use `action="append"`:

```python
# CORRECT — accumulates: ['Pop5IP', 'Rpp14IP', 'Rpp21IP']
ap.add_argument("--samples", action="append", default=[])

# WRONG — keeps only LAST value: ['Rpp21IP']
ap.add_argument("--samples", nargs="+")
```

With `nargs="+"`, repeated flags overwrite: `--samples A --samples B` gives `['B']`, not `['A', 'B']`.

**Verification:** `python3 -c "import argparse; ap=argparse.ArgumentParser(); ap.add_argument('--s', nargs='+'); print(ap.parse_args(['--s','A','--s','B']))"` → `Namespace(s=['B'])`

## `use rule` and `params:` for script paths (NOT module-level variables)

When a module rule references a script path via a module-level variable like `PEAK_CENTRIC_SCRIPT = os.path.join(MODULE_DIR, "bin", "script.py")`, this variable is NOT accessible when the rule is imported via `use rule` in a subworkflow. Module-level variables don't transfer with `use rule`.

**Fix:** Compute the script path in `params:` using `MODULE_DIR` (which IS available from config):

```python
MODULE_DIR = os.path.join(config.get("ROOT_DIR", "."), "modules", "peak_te_overlap")
# DO NOT: PEAK_CENTRIC_SCRIPT = os.path.join(MODULE_DIR, "bin", "script.py")  # not accessible via use rule

rule peak_centric_overlap:
    params:
        script = os.path.join(MODULE_DIR, "bin", "peak_centric_overlap.py"),  # OK — computed in params
        bedtools = config.get("Procedure", {}).get("bedtools") or "bedtools",
    run:
        cmd = ["python3", params.script, ...]  # use params.script, not module-level var
```

## Optional inputs: return `[]` NOT `""`

When an input function returns nothing (no file needed), return an empty list `[]`, NOT an empty string `""`. Snakemake treats `""` as a file path and raises "Empty file path encountered":

```python
# CORRECT
def _get_gtf_for_heatmap(wildcards):
    if not needs_gtf:
        return []  # empty list = no input
    return gtf_path

# WRONG — causes "Empty file path encountered" error
def _get_gtf_for_heatmap(wildcards):
    if not needs_gtf:
        return ""  # Snakemake tries to use "" as a file path
    return gtf_path
```

This error cascades and causes all downstream jobs to re-run in dry-run.
