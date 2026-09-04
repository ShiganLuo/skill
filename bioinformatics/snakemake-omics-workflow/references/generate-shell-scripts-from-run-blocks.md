# Generating shell scripts from `run:` blocks — PATH pitfalls

## The Problem

In Snakemake `run:` blocks, you often generate a `.sh` script and execute it via `shell()`.
If the script uses bare `"python"` as the interpreter, it resolves to `/usr/bin/python`
(the system Python), NOT the conda environment's Python. This causes `ImportError` or
`ModuleNotFoundError` for conda-installed packages like `pysam`, `pandas`, `numpy`, etc.

Similarly, CLI tools like `samtools`, `bedtools`, `gsnap`, `usearch` may not be found
if the conda bin directory isn't on PATH.

## The Fix

Always use the FULL conda python path in the generated command, and prepend `export PATH`
to the generated bash script:

```python
CONDA_BIN = "/data/pub/zhousha/env/mutation_0.1/eda061b3f191779ad16ff11ee6fe53b4_/bin"

cmd = [
    f"{CONDA_BIN}/python",  # NOT bare "python"
    params.script,
    "--out", outdir,
    # ...
]

with open(script_path, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(f"export PATH={CONDA_BIN}:$PATH\n")  # For samtools, bedtools, etc.
    f.write(" ".join(cmd) + "\n")

shell(f"bash {script_path} >> {log_path} 2>&1")
```

## Why `conda:` directive doesn't help

Snakemake's `conda:` directive only activates the env for `shell:` blocks, NOT for
`run:` blocks. In a `run:` block, the Python code executes in the Snakemake process's
own Python, and any `shell()` calls within it inherit that environment — not the
conda env specified in the rule.

When a `run:` block generates a `.sh` script and calls `shell("bash script.sh")`,
the bash process inherits the Snakemake process's PATH, which typically does NOT
include the conda env's bin directory.

## Symptoms

- `ModuleNotFoundError: No module named 'pysam'` — bare python can't find conda packages
- `samtools: command not found` — conda bin not on PATH in generated script
- Script runs but produces empty output — silent failure in subprocess
- Snakemake reports `CalledProcessError` exit status 1 — check the rule log

## Checklist for every `.smk` file with `run:` block that generates a script

1. [ ] `cmd` list uses full python path, not bare `"python"`
2. [ ] Generated `.sh` has `export PATH=CONDA_BIN:$PATH` after shebang
3. [ ] mimseq tools: `--out` parameter has trailing `/` (mimseq functions require it)
4. [ ] `log` in `run:` block uses `str(log)` not bare `log` (Snakemake v9 `Log` object)
