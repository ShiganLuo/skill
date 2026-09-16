# Input Function Pitfalls in Snakemake

## Trailing comma creates tuple, not string

Python trailing comma makes a 1-element tuple. Snakemake wraps tuples/lists as Namedlist.

```python
# WRONG — returns tuple ("path",), not string "path"
def get_input(wildcards):
    return f"{indir}/{wildcards.sample_id}/{wildcards.sample_id}.fq.gz",

# RIGHT — returns string
def get_input(wildcards):
    return f"{indir}/{wildcards.sample_id}/{wildcards.sample_id}.fq.gz"
```

Symptom: `" ".join(cmd)` fails with `TypeError: sequence item N: expected str instance, Namedlist found` at the element index where the input is used.

Root cause: Snakemake's `input.fastq` becomes a Namedlist wrapping the tuple. `Namedlist.__str__` may work for single-element lists, but `join()` sees the object type, not its string repr.

Fix: remove the trailing comma. Do NOT rely on `str(input.fastq)` as a workaround — it may produce `"['path']"` for multi-element Namedlists.

## Defensive str() cast for input objects

When using `input.X` in a `run:` block cmd list, cast to `str()` defensively:

```python
cmd = [params.tool, str(input.fastq), "-o", output.result]
```

This handles edge cases where Snakemake's input resolution produces a Namedlist instead of a plain string (e.g., single-element list from input function).

## Input function must return str or list, never tuple

```python
# WRONG — implicit tuple from trailing comma
def get_fq(wildcards):
    return f"sample.fq.gz",

# RIGHT — single string
def get_fq(wildcards):
    return f"sample.fq.gz"

# RIGHT — list for paired
def get_fq(wildcards):
    return [f"sample_1.fq.gz", f"sample_2.fq.gz"]
```

## Verify input function return types

Quick grep for trailing commas in return statements:
```bash
grep -n 'return.*\.fq\.gz",' modules/**/*.smk
grep -n 'return.*",' modules/**/*.smk | grep -v '#'
```
