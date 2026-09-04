# Splitting monolithic tools into sub-modules

When a tool does everything in one command (like mimseq), split into independent
Snakemake sub-modules with file-based state passing.

## Directory structure
```
modules/<tool>/
  <tool>.smk          # main orchestrator, includes sub-modules
  bin/
    serialize.py      # pickle/JSON state serialization
    <sub1>/run.py     # wrapper script for sub-module 1
    <sub2>/run.py     # wrapper script for sub-module 2
  <sub1>/<sub1>.smk   # Snakemake rule for sub-module 1
  <sub2>/<sub2>.smk   # Snakemake rule for sub-module 2
```

## State passing via pickle files

Each sub-module wrapper saves its output state to `outdir/state/` as pickle files.
Downstream sub-modules load these pickles as input.

```python
# bin/serialize.py
import pickle, os, json

def save_pickle(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pickle file not found: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)

def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, "r") as f:
        return json.load(f)
```

## Dependency chain via .done sentinel files

```python
rule sub1:
    output: touch(outdir + "/sub1.done")
    run: ...

rule sub2:
    input: outdir + "/sub1.done"
    output: touch(outdir + "/sub2.done")
    run: ...
```

## Main orchestrator pattern

```python
# <tool>.smk
include: "sub1/sub1.smk"
include: "sub2/sub2.smk"

rule <tool>_all:
    input:
        sub2_done = outdir + "/sub2.done",

rule <tool>_result:
    input:
        sub2_done = outdir + "/sub2.done",
    output:
        touch(outdir + "/<tool>.done"),
```

## Subworkflow import pattern

CRITICAL: Import ALL intermediate rules, not just the final one:

```python
# WRONG - only imports final rule, breaks dependency chain
use rule <tool>_result from <tool> as WF_<tool>_result

# CORRECT - imports ALL intermediate rules
use rule <tool>_sub1 from <tool> as WF_<tool>_sub1
use rule <tool>_sub2 from <tool> as WF_<tool>_sub2
use rule <tool>_result from <tool> as WF_<tool>_result
```

Without importing intermediate rules, Snakemake raises MissingInputException.

## outfiles must match final output

The `outfiles` in run.py and raw.json must exactly match the final rule's output:

```python
# If <tool>_result produces: touch(outdir + "/<tool>.done")
outfiles = [f"{outdir}/<tool>/<tool>.done"]
# NOT: outfiles = [f"{outdir}/<tool>"]  ← causes MissingInputException
```

## Pitfall: conda: + run: incompatibility

When using `run:` blocks, `conda:` directive is NOT allowed. Either:
1. Remove `conda:` and use full path to conda env Python in shell script:
   ```python
   cmd = ["/path/to/env/bin/python", params.script, ...]
   ```
2. Activate conda env in the generated shell script:
   ```python
   f.write("source /path/to/conda/bin/activate /path/to/env\n")
   ```

## Example: mimseq module splitting

mimseq was split from one monolithic rule into 6 sub-modules:
1. `tRNAtools` — parse tRNA, generate SNP index, GSNAP indices
2. `align` — GSNAP alignment
3. `clusters` — cluster splitting and deconvolution
4. `mods` — modification quantification
5. `coverage` — coverage calculation and plotting
6. `deseq` — DESeq2 differential expression

Each sub-module has:
- `bin/<sub>/run.py` — Python wrapper calling mimseq functions
- `<sub>/<sub>.smk` — Snakemake rule

State is passed via `outdir/state/*.pkl` pickle files.
