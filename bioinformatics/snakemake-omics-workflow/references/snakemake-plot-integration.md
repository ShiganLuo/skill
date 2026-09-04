# Integrating Plots into Snakemake Pipeline Modules

Pattern for adding visualization to pipeline modules without cluttering analysis logic.

## Directory Output Pattern

Use `directory()` for plot outputs. Each rule owns a unique subdirectory to avoid Snakemake output conflicts:

```python
rule scanpy_qc:
    output:
        h5ad = outdir + "/{sample_id}/{sample_id}_qc.h5ad",
        plot_dir = directory(outdir + "/{sample_id}/plots")
    run:
        os.makedirs(str(output.plot_dir), exist_ok=True)
        cmd = [python, script, "--mode", "qc",
               "--input", input.h5ad,
               "--output", output.h5ad,
               "--plot-dir", str(output.plot_dir)]
```

For tissue-level steps, use mode-specific subdirectories:

```python
# Each rule gets its own subdirectory — no conflicts
plot_dir = directory(outdir_combine + "/{tissue}/plots/cluster")
plot_dir = directory(outdir_combine + "/{tissue}/plots/batch")
plot_dir = directory(outdir_combine + "/{tissue}/plots/annotate")
```

## CLI Convention

Add `--plot-dir` as an optional argument. When empty/omitted, no plots are generated:

```python
parser.add_argument("--plot-dir", default="", help="Directory to save plots (optional)")
```

## Two-File Architecture

Separate analysis from visualization:

```
bin/
  analysis.py   # CLI + analysis logic, NO matplotlib imports
  plot.py       # Plotter class, all visualization code
```

Main script lazy-loads the plotter only when `--plot-dir` is set. This keeps matplotlib out of the import chain for non-plotting runs.

## Pitfalls

- **`directory()` conflicts**: If two rules declare the same `directory()` path as output, Snakemake raises an ambiguity error. Use unique subdirectories per rule.
- **`os.makedirs`**: Must be called in the `run:` block before the script call. The Python plotter also calls `os.makedirs` in `__init__`, but the smk block should do it too for robustness.
- **Don't declare individual PNG files as outputs**: Use `directory()` instead. Listing individual PNGs in Snakemake output is fragile — new plots added later would require smk changes.
