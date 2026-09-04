# Scanpy Module Plotting Architecture

## When to use

When adding visualization/figures to any scanpy module in the Omics workflow.

## Architecture (MANDATORY)

Do NOT inline plotting code in the analysis script. Extract into a separate module.

```
bin/
  scRNAseq.py   # Analysis only. NO matplotlib imports. Calls plotter conditionally.
  plot.py       # ScanpyPlotter class. All visualization logic lives here.
```

User explicitly requires "工程化" (engineering-grade) separation of concerns.
"代码要工程化一点" = the user wants proper modular design, not spaghetti.

## plot.py — ScanpyPlotter class

```python
"""Visualization module for Scanpy scRNA-seq pipeline."""
import csv, logging, os
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # MUST set backend before any plt import
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
import seaborn as sns
from anndata import AnnData

sc.set_figure_params(dpi=80, facecolor="white", frameon=False)


class ScanpyPlotter:
    """Generates pipeline stage plots for scanpy scRNA-seq analysis.

    Args:
        plot_dir: Output directory for PNG figures.
        dpi: Resolution for saved figures.
    """
    def __init__(self, plot_dir: str, dpi: int = 300) -> None:
        self.plot_dir = plot_dir
        self.dpi = dpi
        os.makedirs(plot_dir, exist_ok=True)

    def _save(self, filename: str) -> None:
        """Save current matplotlib figure and release memory."""
        plt.savefig(os.path.join(self.plot_dir, filename), dpi=self.dpi, bbox_inches="tight")
        plt.close("all")

    @staticmethod
    def _detect_anno_key(adata: AnnData) -> Optional[str]:
        """Return first available cell-type annotation column."""
        for key in ("cell_type", "celltypist_label", "llm_label", "major_celltype"):
            if key in adata.obs.columns:
                return key
        return None

    @staticmethod
    def _detect_sample_key(adata: AnnData) -> Optional[str]:
        """Return first available sample identifier column."""
        for key in ("sample_id", "sample", "batch"):
            if key in adata.obs.columns:
                return key
        return None

    @staticmethod
    def _umap(adata, color, *, ax, title="", legend_loc="right margin",
              legend_fontsize=8, legend_fontoutline=2):
        """Thin wrapper around sc.pl.umap with standard styling."""
        sc.pl.umap(adata, color=color, frameon=False, show=False, ax=ax,
                   title=title or color, legend_loc=legend_loc,
                   legend_fontsize=legend_fontsize, legend_fontoutline=legend_fontoutline)

    # --- One method per pipeline mode ---
    # plot_qc(adata, adata_before)
    # plot_merge(merged)
    # plot_cluster(adata)
    # plot_batch(adata, method)
    # plot_annotate(adata, marker_file="", annotate_group="")
    # plot_advanced(adata, trajectory=False, cnv=False)
    # plot_de(adata, group)
```

## scRNAseq.py — lazy-load pattern

```python
_plotter_cls = None

def _get_plotter():
    """Lazy-load ScanpyPlotter to avoid matplotlib import at startup."""
    global _plotter_cls
    if _plotter_cls is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from plot import ScanpyPlotter
        _plotter_cls = ScanpyPlotter
    return _plotter_cls

def _make_plotter(plot_dir: str):
    """Instantiate plotter if plot_dir is provided, else return None."""
    if not plot_dir:
        return None
    cls = _get_plotter()
    return cls(plot_dir)

# Usage in each mode function:
def mode_qc(adata, args):
    # ... analysis logic ...
    plotter = _make_plotter(getattr(args, "plot_dir", ""))
    if plotter:
        plotter.plot_qc(adata, adata_before)
```

CLI: add `parser.add_argument("--plot-dir", default="", help="Directory to save plots (optional)")`

## scanpy.smk — directory() output pattern

Each rule gets a `plot_dir` output using `directory()`:

```python
rule scanpy_cluster:
    output:
        h5ad = outdir_combine + "/{tissue}/{tissue}_clustered.h5ad",
        markers = outdir_combine + "/{tissue}/{tissue}_markers.tsv",
        plot_dir = directory(outdir_combine + "/{tissue}/plots/cluster")
    run:
        # ... existing setup ...
        os.makedirs(str(output.plot_dir), exist_ok=True)
        # ... existing cmd construction ...
        cmd += ["--plot-dir", str(output.plot_dir)]
```

Plot directory structure:
- QC (per sample): `outdir + "/{sample_id}/plots"`
- Others (per tissue): `outdir_combine + "/{tissue}/plots/{mode}"`

Where `{mode}` = `merge`, `cluster`, `batch`, `annotate`, `advanced`, `de`

## Scanpy ax parameter pitfalls

Some scanpy plot functions do NOT accept `ax`. Passing `ax` raises TypeError.

**NO `ax` parameter** (call without fig/ax, then `_save()`):
- `sc.pl.highly_variable_genes(adata, show=False)`
- `sc.pl.pca_variance_ratio(adata, show=False)`
- `sc.pl.rank_genes_groups_dotplot(adata, n_genes=3, show=False)`

**HAS `ax` parameter** (create fig/ax first, pass `ax=ax`):
- `sc.pl.umap()`, `sc.pl.violin()`, `sc.pl.scatter()`
- `sc.pl.diffmap()`, `sc.pl.dotplot()`, `sc.pl.rank_genes_groups()`

Pattern for no-ax functions:
```python
sc.pl.highly_variable_genes(adata, show=False)
self._save("qc_highly_variable_genes.png")
```

Pattern for ax functions:
```python
fig, ax = plt.subplots(figsize=(8, 6))
sc.pl.umap(adata, color="leiden", show=False, ax=ax, title="Leiden Clusters")
self._save("cluster_umap_leiden.png")
```

## Verification script

Run against changed code to verify all plot methods work:

```python
# Key checks:
# 1. ScanpyPlotter imports cleanly
# 2. All plot_{mode}() methods exist with correct signatures
# 3. Smoke test each with minimal AnnData (200 cells, 600 genes)
# 4. Verify PNGs are generated (count + filenames)
# 5. CLI --help shows --plot-dir
# 6. plot module NOT loaded at scRNAseq import (lazy load works)
```

Note: bbknn/infercnvpy are conda-only deps — skip those smoke tests in .venv.
