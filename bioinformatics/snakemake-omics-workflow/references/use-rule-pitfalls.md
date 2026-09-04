# `use rule` Pitfalls

## Module-level variables not inherited

When importing a rule with `use rule X from module as Y`, module-level Python variables defined in the module's `.smk` are NOT accessible inside the imported rule's `shell:` block. `{VARIABLE}` in shell is treated as a Snakemake wildcard, not a Python variable.

**Symptom**: `KeyError` or empty expansion of script path variables.

**Fix**: Use `params:` to pass the value (params are evaluated at rule-definition time and travel with the imported rule):
```python
# WRONG — shell block can't see Python vars
PEAK_CENTRIC_SCRIPT = os.path.join(MODULE_DIR, "bin", "peak_centric_overlap.py")
rule peak_centric_overlap:
    shell: "python3 {PEAK_CENTRIC_SCRIPT} ..."  # ← wildcard, not Python!

# CORRECT — use params
rule peak_centric_overlap:
    params:
        script = os.path.join(MODULE_DIR, "bin", "peak_centric_overlap.py"),
    run:
        cmd = ["python3", params.script, ...]
```

Alternatively, use `run:` block instead of `shell:` — `run:` executes Python where module-level variables ARE accessible.

## Empty string in input functions

Returning `""` (empty string) from an input function causes Snakemake to treat it as a file path:
```
Empty file path encountered. Snakemake cannot understand this.
```

**Fix**: Return `[]` (empty list) instead of `""` when no input file is needed:
```python
def _get_gtf_for_heatmap(wildcards):
    if no_gtf_needed:
        return []   # NOT ""
    return gtf_path
```

## argparse `nargs="+"` with repeated flags

When Snakemake builds commands with repeated flags in a loop:
```python
for s in ip_samples:
    cmd += ["--samples", s]  # produces --samples A --samples B --samples C
```

And the Python script uses `nargs="+"`:
```python
parser.add_argument("--samples", nargs="+", required=True)
```

**Result**: `args.samples = ['C']` — only the LAST value is kept! Each `--samples` overwrites the previous.

**Fix**: Use `action="append"` instead:
```python
parser.add_argument("--samples", action="append", default=[], required=True)
# Now: args.samples = ['A', 'B', 'C']
```
