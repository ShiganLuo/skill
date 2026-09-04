# Scanpy Module Pitfalls

## smk rule template compliance

When writing scanpy .smk rules, MUST follow the standard run: block template from modules.md.
The old `scRNAseq-module-patterns.md` reference had a WRONG template that was missing:
- `open(log_path, "w").close()` — log clearing
- `setup_logger()` — structured logging
- `rule_logger.info()` — start/end markers
- `logger.error()` + `raise e` — proper error handling

## echo completion marker (MANDATORY)

Every shell script written by a run: block MUST end with an echo line confirming success.
Since the script's stdout is redirected to the log (`>> {log_path} 2>&1`), the echo appears
in the log file as a clear completion marker:

```python
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(cmd) + "\n")
    f.write(f'echo "<tool> <action> for {wildcards.sample_id} at {current_time} completed successfully"\n')
```

## NO conditional branches in module .smk (MANDATORY)

Module .smk files MUST NOT wrap rule definitions in `if/else` blocks.
ALL rules must be unconditionally defined. The subworkflow decides which rules to `use rule`.

Input functions should ALSO be unconditional — each rule has a fixed input path.
The subworkflow chains rules as needed.

## NO `enabled` flags in module config

The module does NOT read `enabled` flags. The subworkflow decides what to run.
Do NOT add `batch.enabled`, `annotate.enabled`, etc. to the scanpy config.
The subworkflow decides which rules to `use rule` based on its own logic.

## bin/*.py scripts: use logging, NOT print

All bin/*.py scripts must use Python `logging` module, NOT `print()` statements.

```python
import logging

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

# In main():
setup_logging()

# Then use:
logging.info("message")
logging.warning("message")
logging.error("message")
```

## Common typos in scanpy.smk

- `{sample}` vs `{sample_id}` — always use `{sample_id}` consistently
- `{sample_Id}` (capital I) — typo, must be `{sample_id}`
- `indir + "/{sample_id}/{sample}.h5ad"` — wrong wildcard name

## tissue_samples data flow

`tissue_samples` is a scanpy parameter, lives inside `Params.scanpy`.

1. `node.py` builds `tissue_samples = {tissue: [sid, ...]}` and injects into `datajson["Params"]["scanpy"]["tissue_samples"]`
2. `scRNAseq.smk` passes `scanpy_params` (from `config["Params"]["scanpy"]`) into scanpy_config's `Params.scanpy`
3. `scanpy.smk` reads via `params.get("tissue_samples", {})`

**Wrong**: `tissue_samples = config.get("tissue_samples", {})` — reads from top-level
**Right**: `tissue_samples = params.get("tissue_samples", {})` — reads from Params.scanpy

Do NOT use `tissue_map = {sid: tissue}` and convert with defaultdict. Build `tissue_samples` directly.

## sample_h5ad anti-pattern (REMOVED)

`sample_h5ad = {sid: path}` was built in node.py but never read by the scanpy module.
The module derives paths from `indir + sample_id` pattern. Removed entirely.
Don't build unused intermediate dicts just to pass through as config fields.

## Config structure: nested params (NOT flat)

scanpy params MUST be nested by step, NOT flat at the top level:

```json
{
  "Params": {
    "scanpy": {
      "tissue_samples": {},
      "qc": { "min_genes": 200, "max_genes": 6000, ... },
      "cluster": { "n_pcs": 50, "n_neighbors": 15, "resolution": 0.8 },
      "batch": { "n_pcs": 50, "method": "bbknn", "batch_key": "sample" },
      "annotate": { "marker_file": "", "celltypist_model": "", ... },
      "advanced": { "trajectory": false, "velocity": false, ... }
    }
  }
}
```

Module reads via: `params.get("qc", {}).get("min_genes", 200)`, `params.get("cluster", {}).get("n_pcs", 50)`, etc.

**Wrong**: flat `params.get("min_genes", 200)`, `params.get("n_pcs", 50)`
**Right**: nested `params.get("qc", {}).get("min_genes", 200)`, `params.get("cluster", {}).get("n_pcs", 50)`

## indir MUST be defined

The module uses `indir` in scanpy_qc input. It must be explicitly defined:
```python
indir = config.get("indir", "input")
```
The subworkflow passes it as `"indir": h5ad_outdir` in scanpy_config.

## scanpy_advanced: n_pcs/n_neighbors from cluster, NOT batch

`scanpy_advanced` uses n_pcs and n_neighbors for trajectory/velocity analysis.
These are general clustering parameters, NOT batch-specific.

**Wrong**: `n_pcs=params.get("batch", {}).get("n_pcs", 50)`
**Right**: `n_pcs=params.get("cluster", {}).get("n_pcs", 50)`

## scanpy_result rule

Every module needs a `<tool>_result` rule for subworkflow dependency aggregation:

```python
rule scanpy_result:
    input:
        h5ad = expand(outdir_combine + "/{t}/{t}_de.h5ad", t=tissues),
        table = expand(outdir_combine + "/{t}/{t}_markers.tsv", t=tissues)
```

## File naming: match directory name

Module files MUST be named after the directory, NOT prefixed with workflow name:
- `modules/scanpy/scanpy.smk` ✅
- `modules/scanpy/scRNAseq_scanpy.smk` ❌

Same for .json, .yaml. The `name:` field in .yaml must match the filename stem.

## User preference: don't modify user's code

When the user says "不要修改我的修改" or indicates they already wrote something correctly,
DO NOT touch it. Verify but don't change. The user knows their codebase better than you.

## counter wildcard in scanpy.smk

All scanpy rules use `{counter}` as a wildcard (e.g. `scTE`, `cellranger`).
This allows running the same scanpy pipeline for different counting methods.

```
input:  indir + "/{sample_id}/{sample_id}_{counter}.h5ad"
output: outdir + "/{sample_id}/{sample_id}_{counter}_qc.h5ad"
```

Config is nested by counter: `params.get(wildcards.counter, {}).get("qc", {})`:
```json
{
  "Params": {
    "scanpy": {
      "cellranger": {
        "qc": {"min_genes": 200, "max_genes": 6000},
        "cluster": {"n_pcs": 50, "resolution": 0.8}
      },
      "scTE": {
        "qc": {"min_genes": 10, "max_genes": 6000},
        "cluster": {"n_pcs": 50, "resolution": 0.8}
      }
    }
  }
}
```

**`--counters` controls which counter module runs:** The subworkflow
(`scRNAseq.smk`) checks `if "scTE" in counters` to include scTE rules,
`elif "cellranger" in counters` for cellranger counter. The `counters`
config is a list, not a wildcard.

**Re-running specific counter:** Use `--forcerun scanpy_qc` (re-runs for
ALL counters). Snakemake's `RULE:WILDCARD=VALUE` syntax may not work in
all versions — if it fails with `MissingRuleException` or `AttributeError`,
use rule names without wildcard constraints.

## Config/schema sync rule

When changing module code (adding/removing config fields, restructuring params),
MUST also update:
1. `config/<Workflow>.json` — the config template
2. `config/<Workflow>.schema.json` — the validation schema
3. `modules/<tool>/<tool>.json` — the module's own config schema
4. `subworkflow/<Workflow>.smk` — the config dict assembly

Missing any of these causes runtime failures or silent config mismatches.

## SIF build verification

After renaming yaml files and rebuilding SIFs, ALWAYS verify the conda env inside:
```bash
apptainer exec /path/to/sif.sif python -c "import <key_package>"
```

The SIF build can silently fail (conda solver issues, network timeouts) and produce
a container with only the base miniconda Python, no actual packages installed.
If verification fails, rebuild with `--force` or troubleshoot the def file.

## infercnvpy: NOT in conda channels

`infercnvpy` is only on PyPI, NOT in conda-forge or bioconda.
If listed as a conda dependency, `conda env create` fails with:
```
ResolvePackageNotFound:
  - infercnvpy
```
This causes SIF builds to silently produce containers with only base miniconda.

**Fix**: put `infercnvpy` under `pip:` in the yaml, AND add `pip` itself as a conda dep:
```yaml
dependencies:
  - python=3.11
  - pip
  - scanpy
  # ... other conda packages ...
  - pip:
    - infercnvpy
```

Without `pip` in conda deps, conda warns: "you have pip-installed dependencies in your environment file, but you do not list pip itself as one of your conda dependencies."

## conda plugin crash (CONDA_NO_PLUGINS=true)

On some systems, `conda env create` fails with:
```
TypeError: expected str, bytes or os.PathLike object, not NoneType
```
in `conda/activate.py` `_get_deactivate_scripts`. This is a conda plugin issue.

**Fix**: use `CONDA_NO_PLUGINS=true conda env create ...` or set in .def:
```bash
export CONDA_NO_PLUGINS=true
```

## SIF silent failure verification

After building a SIF, ALWAYS verify key packages exist:
```bash
apptainer exec /path/to/scanpy.sif python -c "import anndata, scanpy; print('OK')"
```

If the SIF only has base Python (e.g., Python 3.14 instead of 3.11 from yaml),
the conda env creation failed silently. Check:
1. `apptainer exec scanpy.sif which python` — should be in envs/scanpy/bin
2. `apptainer exec scanpy.sif conda env list` — should show scanpy env
3. If missing, rebuild with `--force` after fixing the yaml

## scanpy SIF: use uv, NOT conda

The scanpy conda environment (scanpy + scvelo + liana + celltypist + infercnvpy) takes
2+ hours with conda classic solver and often fails silently. All packages are on PyPI.

Use uv-based def template (see `references/apptainer-sif-build-pitfalls.md` section 9):
```
Bootstrap: docker
From: docker.m.daocloud.io/python:3.11-slim

%post
    set -euo pipefail
    apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
    pip install uv
    uv pip install --system --no-cache \
        scanpy anndata leidenalg python-igraph scrublet \
        scvelo liana celltypist openai requests infercnvpy
```

Build completes in ~2 minutes vs 2+ hours with conda.

## pandas 2.x BooleanArray compatibility (CRITICAL)

`str.startswith()` in pandas 2.x returns `BooleanArray`, NOT numpy bool array.
scipy sparse indexing requires numpy bool. This causes:
```
AttributeError: 'BooleanArray' object has no attribute 'nonzero'
```

**Wrong approaches** (all fail with BooleanArray):
```python
# BooleanArray has no .values
adata.var["mt"] = adata.var_names.str.startswith("MT-").values.astype(bool)  # AttributeError

# Direct assignment keeps BooleanArray type
adata.var["mt"] = adata.var_names.str.startswith("MT-")  # BooleanArray, breaks scipy
```

**Correct**: wrap in `np.array()`:
```python
import numpy as np
adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-") | adata.var_names.str.startswith("mt"))
adata.var["ribo"] = np.array(adata.var_names.str.startswith(("RPS", "RPL")))
```

## Input function references must be defined

If a rule's input uses a function (e.g., `h5ad = get_de_input`), ensure the function
exists. `get_de_input` referenced `get_advanced_input` which was never defined —
a latent NameError that only surfaces when the rule runs.

Fix: simplify input functions to return fixed paths instead of calling other functions.

## anndata nullable string write error

`anndata` refuses to write columns with pandas `StringArray`/`ArrowStringArray` dtype:
```
RuntimeError: `anndata.settings.allow_write_nullable_strings` is False
Error raised while writing key 'gene_barcode' of <class 'h5py._hl.group.Group'>
```

**Fix**: set the flag at the top of the script:
```python
import anndata as ad
ad.settings.allow_write_nullable_strings = True
```

This is needed when h5ad files have string columns created by pandas 2.x (which uses
nullable string types by default). scTE output commonly has `gene_barcode` in obs.

## scTE data QC parameters

scTE output has TE barcodes as var_names (not gene names). TE counts are much lower
than gene counts — median ~25 TEs/cell vs ~2000 genes/cell.

**Wrong**: using gene-expression defaults like `min_genes=200` removes 90%+ of cells.
**Right**: for scTE data, use `min_genes=10` or lower.

The config should reflect this:
```json
"qc": { "min_genes": 10, "max_genes": 6000, ... }
```

## MANDATORY: local testing before pipeline runs

ALWAYS test the script locally with a single input file before running the full
Snakemake pipeline. The user explicitly requires this:
"先用单个文件进行测试,把代码修改好再通知我完成,不要让我每次启动流程都是失败的"

```bash
apptainer exec /path/to/scanpy.sif python /path/to/scRNAseq.py \
  --mode qc --input <single.h5ad> --output /tmp/test_qc.h5ad \
  --metrics /tmp/test.tsv --min-genes 10 --max-genes 6000 --max-pct-mt 20 \
  --n-top-genes 3000 --scrublet --doublet-rate 0.06
```

Only after this succeeds should you tell the user to run the full pipeline.
