---
name: python-scientific-plotting-scripts
description: Refactor and author Python scientific plotting scripts — multi-format output, proper typing, unified CLI, NumPy docstrings, graceful statistical testing. Use when creating or refactoring matplotlib/seaborn-based analysis scripts for genomics/bioinformatics workflows.
tags: [python, matplotlib, typing, argparse, docstrings, bioinformatics, plotting]
---

# Python Scientific Plotting Scripts

Patterns for authoring and refactoring Python scripts that produce publication-quality plots in bioinformatics/genomics pipelines.

## 1. Multi-Format Image Output

Define a `PlotFormat` type alias at module level and use `Optional[List[PlotFormat]]` for function parameters:

```python
from typing import Dict, List, Literal, Optional

PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]

def my_plot_func(
    data: pd.DataFrame,
    out_prefix: str,
    image_formats: Optional[List[PlotFormat]] = None,
) -> None:
    if image_formats is None:
        image_formats = ["png"]
    for fmt in image_formats:
        plt.savefig(f"{out_prefix}.{fmt}", dpi=300)
```

**CLI pattern** — use `action="append"` so users pass `-f png -f pdf`:

```python
parser.add_argument(
    "-f", "--format",
    action="append",
    dest="formats",
    metavar="FMT",
    help="Image output format. Can be specified multiple times. Default: png.",
)
```

### Pitfalls

- **Short-flag collision when retrofitting** — when adding `-f/--format` to an existing script that already uses `-f` for another arg (e.g. `--figsize`), reassign the old arg's short flag first (e.g. `-f/--figsize` → `-s/--figsize`) before adding `-f/--format`. Always grep for existing `-f` short flags before adding the format arg.
- **Never use bare `list`** — always `List[X]` with typing.
- **int values in subprocess command lists** — `subprocess.run()` and similar require ALL list items to be `str`. Always wrap non-string values: `str(ins_bin_size)`. This is a silent bug that only manifests at runtime.
- **Mutable default arguments** — always `None` + if-check, never `list = []`.
- **String concatenation for multi-format** — use `os.path.splitext(out)[0]` to strip existing extension before appending format.
- **output parameter semantics change** — when adding multi-format support to a function that previously took `output="gene_model.png"` (full path with extension), change it to `output="gene_model"` (base path without extension) and update all callers. The function loop appends `.{fmt}` internally. Don't forget CLI callers and batch `run()` functions.

## 2. Optional Dependency Guard

When a script has optional dependencies (e.g. matplotlib), wrap the import in a try/except at the call site rather than at module level. This lets the core logic run even without plotting:

```python
# In main():
try:
    generate_figures(data, outdir, fmts)
except ImportError as exc:
    logger.warning(f"Skipping figures: {exc}. Install matplotlib to enable plotting.")
```

Inside the plotting module, use `matplotlib.use("Agg")` before any pyplot import for headless environments:

```python
def _setup_matplotlib(fmt: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ...
```

### Pitfalls

- **CJK fonts in matplotlib** — when plot labels contain Chinese/Japanese/Korean characters, the default DejaVu Sans font renders them as empty boxes. Fix: use `matplotlib.font_manager.FontProperties(fname="/path/to/cjk-font.ttc")` for tick labels/axis labels, or configure `matplotlib.rcParams["font.sans-serif"]` to include a CJK font (e.g., SimHei, WenQuanYi Zen Hei). Check available CJK fonts with `fc-list :lang=zh`. If no CJK font is available, fall back to English labels.
- **Never import matplotlib at module top-level** in scripts that also run without plotting — it forces the dependency even for non-plot tasks.
- **Mutually exclusive input modes** — use `argparse.add_mutually_exclusive_group(required=True)` when a script supports two alternative input methods (e.g. `--indir` for directory scanning vs `-p` for explicit file lists). This gives clear error messages without manual validation:

```python
input_group = parser.add_mutually_exclusive_group(required=True)
input_group.add_argument("--indir", help="Scan directory for sample subdirs.")
input_group.add_argument("-p", "--passed", help="Comma-separated file list.")
```

## 3. Unified CLI Argument Style

When a project has multiple entry-point scripts, keep argument names consistent:

| Purpose | Short | Long | Style |
|---------|-------|------|-------|
| Image format | `-f` | `--format` | `action="append", dest="formats"` |
| Output dir | `-o` | `--outdir` | single string |
| Groups | `-g` | `--group` | `action="append", metavar="NAME:VCF"` |
| File mappings | | `--tab_files` | `nargs="+", metavar="NAME=PATH"` |

### Dict-Based File Mapping Pattern

When multiple files are paired with names/conditions, use a single `nargs="+"` argument with `name=path` format instead of two parallel lists:

```python
# CLI
parser.add_argument("--deseq2_files", nargs="+", help="format: condition=path")

# Parsing
condition_files = {}
for item in args.deseq2_files:
    if "=" not in item:
        parser.error(f"Invalid format '{item}', expected 'condition=path'")
    name, path = item.split("=", 1)  # split on first = only
    condition_files[name] = path

# Function signature
def Deseq2_oncoprint_data(
    condition_files: Dict[str, str],  # NOT two parallel lists
    ...
):
    for condition, file in condition_files.items():
        ...
```

This eliminates length-mismatch errors and makes the interface self-documenting.

## 3. Typing Conventions

Use modern type hints with full parameterization:

```python
# Good
def run(group_vcf: Dict[str, str], image_formats: Optional[List[PlotFormat]] = None) -> None:

# Bad
def run(group_vcf: dict, image_formats: list = None):
```

Import from `typing`: `Dict`, `List`, `Optional`, `Literal`, `Tuple`, `Union`.

## 4. NumPy Docstring Style

Every function must have a NumPy-style docstring. Template:

```python
def my_func(param1: str, param2: int = 10) -> pd.DataFrame:
    """
    Short summary line (imperative mood).

    Extended description if needed.

    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int, optional
        Description of param2. Default is ``10``.

    Returns
    -------
    pd.DataFrame
        Description of return value.

    Raises
    ------
    ValueError
        When something is wrong.
    """
```

### Pitfalls

- **Docstring placement** — the `"""` block must be the FIRST statement after `def`. If-checks for default args go AFTER the docstring, not before.
- **Batch docstring addition** — use `delegate_task` with 2-3 parallel subagents for projects with 10+ functions across multiple files.

## 5. Graceful Statistical Testing

When using `chi2_contingency` on contingency tables that may have zeros:

```python
table = np.array([...])
# Pre-check for degenerate tables
if table.min() < 0 or table.sum() == 0 or (table.sum(axis=0) == 0).any() or (table.sum(axis=1) == 0).any():
    return None
try:
    _, p, _, _ = chi2_contingency(table)
except ValueError:
    return None
```

## 6. Parallel Plotting (ProcessPoolExecutor)

When a CLI tool plots multiple genes/samples/regions, parallelism speeds things up — but **only with processes, never threads**.

### Why threading fails

1. **GIL**: matplotlib is CPU-bound Python. Threads cannot execute Python bytecode in parallel, so `ThreadPoolExecutor` gives zero speedup (often slower due to context-switch overhead).
2. **SQLite thread safety**: gffutils uses SQLite under the hood. SQLite objects created in one thread cannot be used in another — raises `sqlite3.ProgrammingError`.

### Correct pattern

```python
import concurrent.futures

parser.add_argument("-j", "--threads", type=int, default=1,
                    help="Number of parallel workers (default: 1)")

def _plot_one(gene_name: str) -> None:
    db = create_db(args.gtf)  # Each process gets its own SQLite connection
    transcripts, gene = get_gene_structure_by_transcript(db, gene_name)
    plot_gene_model_all_transcripts(gene, transcripts, ...)

with concurrent.futures.ProcessPoolExecutor(max_workers=args.threads) as executor:
    list(executor.map(_plot_one, args.genes))
```

### Pitfalls

- **`create_db()` must be inside the worker function**, not in the parent process. Each process needs its own SQLite connection. The `.db` file is reused (not re-created) so concurrent `create_db` calls are safe.
- **Don't exceed CPU core count** — `max_workers` > cores causes process thrashing.
- **Parameter is named `--threads` for CLI consistency** (matches other scripts), but the implementation uses `ProcessPoolExecutor`. This is intentional — the user-facing concept is "parallelism level", not the implementation detail.

## 7. Multi-Value Gene/Item Arguments

When a CLI needs to accept multiple genes, samples, or items:

```python
parser.add_argument("-g", "--gene", action="append", dest="genes", required=True,
                    help="Gene symbol. Repeatable: -g TP53 -g BRCA1")
```

Then loop (or submit to process pool):

```python
for gene_name in args.genes:
    _plot_one(gene_name)
```

**Never** use `nargs="+"` for this — `action="append"` is more explicit and matches the `-f`/`--format` pattern used across the project.

## 8. Multi-Group Comparison Plots

For grouped bar charts comparing N groups:

- **Bar offsets**: `total_width / n_groups`, centered: `offset = bar_width * (i - (n_groups-1) / 2)`
- **Pairwise testing**: iterate `C(n, 2)` pairs with chi2, store ALL results including "ns"
- **Bracket style**: 宝盖头 — single polyline from `(x1-tick_x, y_tick)` → `(x1, y_hat)` → `(x2, y_hat)` → `(x2+tick_x, y_tick)`. NEVER draw as 3 separate lines (causes line-cap overlap at junctions).
- **Bracket anti-overlap**: reset `bracket_offset` PER SV type (not globally). Use `tick_depth + TEXT_PT + bracket_gap` as increment. `bracket_gap` controls the actual vertical gap between bracket units.
- **Significance styling**: ns = SAME black color as stars. Distinguish by fontsize (12 vs 9) and weight (bold vs normal) only. `bracket_lw=0.8` for clean look.
- **Broken axis**: auto-detect necessity — only enable when `global_max > sig_max * 2.0`. When all bars are similar height, fall back to single axes to avoid bracket clipping.
- **Test method**: support both `chi2_contingency` and `fisher_exact` via `test_method` parameter. Fisher is better for small samples.

See `matplotlib-significance-brackets` skill for full implementation details.

## 9. Long Categorical Labels and Database Descriptions

Long GO/KEGG/pathway labels can consume the entire figure width and collapse the numeric plotting panel, making bars appear missing. Do not solve this only by shrinking font size.

- Wrap labels before plotting at a controlled character width (about 35–45 characters), using actual newline characters.
- In R, prefer `intToUtf8(10)` as the separator when labels pass through multiple escaping layers; it avoids accidentally rendering a literal `\\n`.
- Sanitize incoming labels before wrapping: replace existing literal `\\n` sequences with spaces, trim whitespace, and provide a fallback for missing descriptions.
- Allocate a wider canvas and scale height with the number of displayed categories, e.g. `width = 12` and `height = max(6, min(18, 2.5 + 0.32 * n_labels))`.
- Add modest plot margins and keep label font readable; use `coord_flip()` only after the labels have been wrapped.
- For KEGG, remove database-added organism suffixes such as ` - Mus musculus (house mouse)` from display labels while retaining the original descriptions in result tables.
- Re-render and inspect the actual image. Confirm that data-colored pixels occupy the plotting region, multiline labels are real line breaks rather than visible escape sequences, and the legend/axis remain readable.

## 10. Focused Verification for Plotting Fixes

When no project test covers a plotting-only change, create a temporary ad-hoc verification script under `/tmp` with an OS-safe `tempfile` path prefixed `hermes-verify-`. Assert the changed behavior directly (syntax parse, label transformation, and no literal escape sequences), run it, clean it up, and report it as ad-hoc verification rather than claiming the suite is green.

## 11. Scanpy Plotting API Pitfalls

### pandas BooleanArray vs numpy bool for var columns

When creating boolean columns in `adata.var`, `str.contains()` and `str.startswith()` return pandas `BooleanArray` (nullable boolean), NOT numpy `bool`. Scipy sparse matrix indexing (used by `sc.pp.calculate_qc_metrics`) requires numpy arrays with `.nonzero()`. Wrap in `np.array()`:

```python
# WRONG — BooleanArray, causes AttributeError: 'BooleanArray' object has no attribute 'nonzero'
adata.var["hb"] = adata.var_names.str.contains(r"^HB[^(P)]")

# CORRECT — wrap in np.array()
adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-"))
adata.var["ribo"] = np.array(adata.var_names.str.startswith(("RPS", "RPL")))
adata.var["hb"] = np.array(adata.var_names.str.contains(r"^HB[^(P)]"))
```

This error only surfaces when `sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo", "hb"], ...)` tries to index the sparse matrix — it's not caught at column creation time.

Several `scanpy.pl.*` functions do NOT accept the `ax` parameter. Always check before passing `ax`:

| Function | Accepts `ax`? |
|----------|:---:|
| `sc.pl.umap` | Yes |
| `sc.pl.violin` | Yes |
| `sc.pl.scatter` | Yes |
| `sc.pl.diffmap` | Yes |
| `sc.pl.dotplot` | Yes |
| `sc.pl.highly_variable_genes` | **No** |
| `sc.pl.pca_variance_ratio` | **No** |
| `sc.pl.rank_genes_groups` | Yes |
| `sc.pl.rank_genes_groups_dotplot` | **No** |
| `sc.pl.rank_genes_groups_heatmap` | **No** |
| `sc.pl.rank_genes_groups_matrixplot` | **No** |
| `sc.pl.rank_genes_groups_stacked_violin` | **No** |

**Pattern**: For functions that don't accept `ax`, call them without creating a figure first:

```python
# Functions WITH ax support:
fig, ax = plt.subplots(figsize=(8, 6))
sc.pl.umap(adata, color="leiden", show=False, ax=ax)
save_fig("umap.png")

# Functions WITHOUT ax support:
sc.pl.highly_variable_genes(adata, show=False)  # creates its own figure
save_fig("hvg.png")
```

**Verification**: check programmatically before using `ax`:
```python
import inspect
has_ax = "ax" in inspect.signature(sc.pl.some_function).parameters
```

## 12. Scientific PPT Report Generation from h5ad Data

When generating a PPTX analysis report from scanpy h5ad files, follow the design language from `workflow/Omics/modules/RNAseq_report/bin/generate_report.py`:

### Design Constants

```python
SLIDE_W = 10.0   # inches, widescreen
SLIDE_H = 5.625
HEADER_H = 0.65
MARGIN_L = 0.45
CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R

C_NAVY   = RGBColor(0x18, 0x25, 0x43)  # header bar, title/conclusion bg
C_ACCENT = RGBColor(0x00, 0x94, 0xD8)  # table header, band, chevron
C_BG     = RGBColor(0xF6, 0xF8, 0xFB)  # content slide background
C_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
C_TEXT   = RGBColor(0x33, 0x33, 0x33)
```

### Slide Structure Pattern

Every content slide: light gray background + navy header bar + content below.

```python
def _header(slide, text):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(SLIDE_W), Inches(HEADER_H))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_NAVY
    bar.line.fill.background()
    tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(0.08), Inches(CONTENT_W), Inches(0.45))
    p = tx.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = C_WHITE
```

Tables: accent blue header row, alternating white/light-blue data rows, centered text.

### Workflow Boxes

Use `ROUNDED_RECTANGLE` + `CHEVRON` arrows for pipeline flow diagrams:

```python
steps = ["FASTQ\n7 samples", "Cell Ranger\nscTE", "QC & Filter", "Harmony", "UMAP + Leiden"]
colors = [RGBColor(0xE8,0xF1,0xFB), RGBColor(0xE9,0xF7,0xF1), RGBColor(0xF9,0xEE,0xD7), ...]
for idx, step in enumerate(steps):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ...)
    shape.fill.fore_color.rgb = colors[idx]
    shape.line.color.rgb = C_ACCENT
    if idx < len(steps) - 1:
        arrow = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, ...)
        arrow.fill.fore_color.rgb = C_ACCENT
```

### Stat Cards on Conclusion Slide

Navy background + rounded rect cards with accent border:

```python
card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ...)
card.fill.fore_color.rgb = RGBColor(0x25, 0x38, 0x5A)
card.line.color.rgb = C_ACCENT
# Two paragraphs: label (small, muted) + value (large, bold white)
```

### Standard scRNA-seq Report Slide Order

1. Title (navy bg, centered white text, accent band)
2. Workflow overview (colored boxes + chevron arrows)
3. Sample overview (table + cell count bar chart)
4. QC metrics (table with median genes/counts/MT%)
5. UMAP cell type (Cell Ranger)
6. UMAP cell type (scTE)
7. Cell type composition (grouped bar, CR vs scTE)
8. Marker dotplot (Cell Ranger)
9. Marker dotplot (scTE)
10. Batch correction (sample UMAP showing mixing)
11. Rare cell types (highlighted on UMAP)
12. Doublet validation (doublet score + predicted)
13. Annotation confidence (pie chart)
14. Key conclusions (navy bg, stat cards)
15. Thank you slide

### Pitfalls

- **Don't load h5ad twice** — if `build_sample_slide` needs cell counts, pass them from the already-loaded adata objects instead of re-reading the file.
- **Image fallback chain** — always check v3 plots > v2 plots > dynamically generated. Use `_get_plot(name, pipeline)` helper that tries directories in order.
- **`_add_picture` aspect ratio** — compute from PIL image dimensions, center within max_w/max_h bounds. Never stretch.
- **Chinese font for matplotlib** — configure `rcParams["font.sans-serif"]` with CJK font BEFORE any plot call. Check `fc-list :lang=zh` for available fonts.
- **Typing module** — use `Dict`, `List`, `Optional` from `typing`, not Python 3.10+ `dict[str, ...]` syntax.

## 13. h5ad Data Inspection Pitfalls

### Categorical columns with NaN

Scanpy h5ad files often have categorical obs columns where "not applicable" is represented as NaN, not False. Common examples: `rare_cell_type`, `predicted_doublet`.

```python
# WRONG — .astype(bool) on categorical with NaN doesn't work as expected
is_rare = adata.obs["rare_cell_type"].astype(bool).values  # TypeError: bad operand type for unary ~

# CORRECT — use .notna() for categorical NaN
is_rare = adata.obs["rare_cell_type"].notna().values
```

### predicted_doublet may be object/categorical

```python
pred = adata.obs.get("predicted_doublet", pd.Series(False, index=adata.obs.index))
is_doublet = pred.astype(bool).values  # .astype(bool) works on boolean-like values
```

### anndata 0.13.2: empty layers group reads as `{None: X}`

anndata 0.13.2 has a bug where an h5ad file with an empty HDF5 `layers` group (written as `{}`) reads back with a spurious `None` key that maps to the same data as `.X`. This is common with scTE-generated h5ad files. The `None` layer propagates through the entire pipeline (`3_raw_h5ad` → `4_qc_h5ad` → `5_combine_h5ad`).

**Detection**:
```python
>>> list(adata.layers.keys())
[None]
>>> adata.layers[None] is adata.X  # or np.array_equal
True
```

**Fix** — delete at QC entry point:
```python
def mode_qc(adata, ...):
    if None in adata.layers:
        del adata.layers[None]
```

HDF5-level verification (h5py): the `layers` group exists but has zero keys — the bug is in anndata's read path, not the file.

### scanpy `sc.pl.scatter` colorbar positioning

`sc.pl.scatter` auto-creates a colorbar, but its position is not controllable and has no label. To get a properly positioned colorbar with a label, remove the auto-created one and use `make_axes_locatable`:

```python
from mpl_toolkits.axes_grid1 import make_axes_locatable

fig, ax = plt.subplots(figsize=(8, 6))
sc.pl.scatter(adata, "total_counts", "n_genes_by_counts",
              color="pct_counts_mt", show=False, ax=ax)
ax.set_title("Before Filtering")

if ax.collections:
    old_cbar = ax.collections[0].colorbar
    if old_cbar is not None:
        old_cbar.remove()  # remove scanpy's auto-colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cbar = fig.colorbar(ax.collections[0], cax=cax)
    cbar.set_label("pct_counts_mt")
```

**Unified axes for before/after comparison** — compute global xlim/ylim/clim from both datasets before drawing, then apply to both plots:

```python
all_counts = np.concatenate([adata_before.obs["total_counts"].values,
                             adata.obs["total_counts"].values])
x_min, x_max = float(all_counts.min()), float(all_counts.max())
x_margin = (x_max - x_min) * 0.05
x_lim = (x_min - x_margin, x_max + x_margin)
# Apply ax.set_xlim(x_lim) to both plots
# Same for ylim and clim (set_clim on the collection)
```

### Inspection checklist before generating plots

```python
adata = sc.read_h5ad(path)
adata.obs_names_make_unique()  # suppress non-unique warning
print(f"Shape: {adata.shape}")
print(f"obs columns: {list(adata.obs.columns)}")
print(f"obsm keys: {list(adata.obsm.keys())}")  # need X_umap, X_pca, X_pca_harmony
print(f"uns keys: {list(adata.uns.keys())}")     # need rank_genes_groups
if "cell_type" in adata.obs.columns:
    print(adata.obs["cell_type"].value_counts())
```

### Finding the right Python environment

scanpy is rarely in conda base. Check project `.venv` first:

```bash
# Find which python has scanpy
for p in .venv/bin/python /home/*/miniconda3/envs/*/bin/python; do
  echo -n "$p: "; $p -c "import scanpy" 2>&1 && echo "YES" || echo "NO"
done
```

## 14. Class-Based Plotter for Snakemake Pipeline Modules

When a Snakemake pipeline module needs visualization, extract plotting into a separate `plot.py` module rather than inlining matplotlib code in the analysis script.

### Architecture

```
bin/
  scRNAseq.py   # Analysis logic + CLI (no matplotlib imports)
  plot.py       # ScanpyPlotter class (all visualization)
```

### plot.py — ScanpyPlotter class with explicit parameters

Plot function parameters must be **explicit** — never hardcode adata column names inside the plotter. The caller declares what columns to plot:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scanpy as sc

class ScanpyPlotter:
    def __init__(self, plot_dir: str, dpi: int = 300) -> None:
        self.plot_dir = plot_dir
        self.dpi = dpi
        os.makedirs(plot_dir, exist_ok=True)

    def _save(self, filename: str) -> None:
        plt.savefig(os.path.join(self.plot_dir, filename), dpi=self.dpi, bbox_inches="tight")
        plt.close("all")

    def plot_qc(self, adata, adata_before,
                counts_col="total_counts",
                genes_col="n_genes_by_counts",
                mt_col="pct_counts_mt") -> None: ...

    def plot_cluster(self, adata,
                     cluster_key="leiden",
                     sample_key="sample") -> None: ...

    def plot_batch(self, adata, method: str,
                   cluster_key="leiden",
                   sample_key="sample") -> None: ...

    def plot_annotate(self, adata,
                      marker_file="",
                      annotate_group="leiden",
                      annotation_keys=None,
                      score_col="celltypist_score",
                      has_rank_genes=False) -> None: ...

    def plot_advanced(self, adata, *,
                      trajectory=False, cnv=False,
                      annotation_key=None,
                      cluster_key="leiden",
                      pseudotime_col="dpt_pseudotime") -> None: ...
```

### scRNAseq.py — explicit call sites

```python
# NO matplotlib imports at top level
_plotter_cls = None

def _get_plotter():
    global _plotter_cls
    if _plotter_cls is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from plot import ScanpyPlotter
        _plotter_cls = ScanpyPlotter
    return _plotter_cls

def _make_plotter(plot_dir: str):
    if not plot_dir:
        return None
    return _get_plotter()(plot_dir)

def mode_qc(adata, output, plot_dir="", ...):
    # ... analysis logic ...
    plotter = _make_plotter(plot_dir)
    if plotter:
        plotter.plot_qc(adata, adata_before,
                        counts_col="total_counts",
                        genes_col="n_genes_by_counts",
                        mt_col="pct_counts_mt")
    adata.write_h5ad(output)

def mode_annotate(adata, output, marker_file="", celltypist_model="",
                  llm_method="", annotate_group="", plot_dir="", ...):
    # ... annotation logic ...
    plotter = _make_plotter(plot_dir)
    if plotter:
        anno_keys = []
        if marker_file:     anno_keys.append("cell_type")
        if celltypist_model: anno_keys.append("celltypist_label")
        if llm_method:      anno_keys.append("llm_label")
        plotter.plot_annotate(adata, marker_file=marker_file,
                              annotate_group=annotate_group or "leiden",
                              annotation_keys=anno_keys,
                              has_rank_genes="rank_genes_groups" in adata.uns)
    adata.write_h5ad(output)
```

### scanpy.smk — plot directory output pattern

```python
rule scanpy_cluster:
    output:
        h5ad = outdir + "/{tissue}/{tissue}_clustered.h5ad",
        plot_dir = directory(outdir + "/{tissue}/plots/cluster")
    run:
        os.makedirs(str(output.plot_dir), exist_ok=True)
        cmd = [python, script, "--mode", "cluster",
               "--input", input.h5ad,
               "--output", output.h5ad,
               "--plot-dir", str(output.plot_dir)]
```

### Pitfalls

- **Plot stage mismatch** — each `plot_*` method must only use data that exists at that pipeline stage. For example, `sc.pl.highly_variable_genes()` requires `adata.uns["hvg"]` which is set by `sc.pp.highly_variable_genes()` in `mode_cluster`, NOT `mode_qc`. Putting it in `plot_qc` causes `KeyError: 'hvg'`. Place HVG plots in `plot_cluster`.
- **Implicit column names** — never hardcode `"total_counts"`, `"leiden"`, `"sample"` etc. inside plotter methods. Always accept them as parameters with sensible defaults. The caller knows the data schema; the plotter should not guess.
- **`_detect_*` helpers are fragile** — auto-detecting `sample_key` or `annotation_key` from adata columns hides dependencies. Prefer explicit parameters with fallback detection only at the call site (in the analysis script, not in the plotter).
- **Snakemake log cascade** — the outer `.snakemake/log/<timestamp>.snakemake.log` shows `SpawnedJobError` from failed jobs, but the real error is in individual sample logs at `log/sample/<sample>/<rule>.log`. Always read the sample-specific log for the root cause traceback.

### Benefits
- Analysis script imports no matplotlib — faster startup, no display dependency
- Plotter loaded only when `--plot-dir` is provided (lazy)
- Each pipeline stage has a dedicated plot method — easy to add/remove
- `directory()` output tracked by Snakemake DAG
- All column names explicit — no hidden dependencies on adata schema
