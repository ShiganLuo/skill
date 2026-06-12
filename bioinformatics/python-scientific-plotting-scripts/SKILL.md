---
name: python-scientific-plotting-scripts
description: Refactor and author Python scientific plotting scripts — multi-format output, proper typing, unified CLI, NumPy docstrings, graceful statistical testing, significance brackets (宝盖头 style). Use when creating or refactoring matplotlib/seaborn-based analysis scripts for genomics/bioinformatics workflows.
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

## 8. Multi-Group Comparison Plots & Significance Brackets

### Grouped Bar Chart Layout

For N groups, compute bar positions:

```python
n_groups = len(group_order)
total_width = 0.8
bar_width = total_width / n_groups
offsets = [bar_width * (i - (n_groups - 1) / 2) for i in range(n_groups)]

cmap = plt.cm.tab10
colors = {g: cmap(i / max(n_groups - 1, 1)) for i, g in enumerate(group_order)}

for i, g in enumerate(group_order):
    ax.bar(x + offsets[i], pivot[g], bar_width, color=colors[g], label=legend_map[g])
```

### Pairwise Chi2 with Degenerate Table Guard

Iterate all C(n, 2) pairs and store ALL results including "ns":

```python
all_pairs: Dict[str, List[tuple]] = {}
for sv in pivot.index:
    pairs = []
    for i, g1 in enumerate(group_order):
        for g2 in group_order[i + 1:]:
            idx1 = list(group_order).index(g1)
            idx2 = list(group_order).index(g2)
            table = np.array([
                [pivot.loc[sv, g1], pivot[g1].sum() - pivot.loc[sv, g1]],
                [pivot.loc[sv, g2], pivot[g2].sum() - pivot.loc[sv, g2]],
            ])
            if table.min() < 0 or table.sum() == 0 \
               or (table.sum(axis=0) == 0).any() \
               or (table.sum(axis=1) == 0).any():
                continue
            try:
                _, p, _, _ = chi2_contingency(table)
            except ValueError:
                continue
            pairs.append((idx1, idx2, p_to_star(p)))
    all_pairs[sv] = pairs
```

Support both `chi2_contingency` and `fisher_exact` via a `test_method` parameter — Fisher is better for small samples.

### Auto-Detect Broken Axis

Only enable when the tallest bar dominates — otherwise fall back to single axes to avoid bracket clipping:

```python
global_max = pivot.values.max()
sig_sv_list = [sv for sv, pairs in all_pairs.items()
               if any(s != "ns" for _, _, s in pairs)]
sig_max = pivot.loc[sig_sv_list].values.max() if sig_sv_list else np.median(pivot.values)
need_broken = use_broken_axis and (global_max > sig_max * 2.0)
```

### 宝盖头 Bracket Style (Full Implementation)

Horizontal line from bar1 center to bar2 center, with OUTWARD diagonal ticks `\` and `/` pointing at bar centers. Drawn as a SINGLE polyline to avoid line-cap overlap at junctions.

```python
LEG_PT = 8    # initial gap from bar top to first bracket (display points)
TEXT_PT = 3   # text offset above bracket line (display points)

for i_sv, sv in enumerate(pivot.index):
    pairs = all_pairs.get(sv, [])
    if not pairs:
        continue
    y_base = max(pivot.loc[sv, g] for g in group_order)
    bracket_offset = 0.0

    for idx1, idx2, star in pairs:
        ax = ax_bottom if (need_broken and y_base <= low_max) else ax_top
        trans = ax.transData
        inv = ax.transData.inverted()

        _, y_disp = trans.transform((0, y_base))
        y_hat_disp = y_disp + LEG_PT + bracket_offset
        y_text_disp = y_hat_disp + TEXT_PT
        _, y_hat = inv.transform((0, y_hat_disp))
        _, y_text = inv.transform((0, y_text_disp))

        x1 = x[i_sv] + offsets[idx1]
        x2 = x[i_sv] + offsets[idx2]

        is_sig = star != "ns"
        fs = 12 if is_sig else 9
        fw = "bold" if is_sig else "normal"

        # Single polyline: left tick → left top → right top → right tick
        tick_x = bar_width * 0.25
        _, y_tick = inv.transform((0, y_hat_disp - tick_depth))

        ax.plot(
            [x1 - tick_x, x1, x2, x2 + tick_x],
            [y_tick, y_hat, y_hat, y_tick],
            lw=bracket_lw, c="black",
        )

        ax.text((x1 + x2) / 2, y_text, star,
                ha="center", va="bottom",
                fontsize=fs, fontweight=fw, color="black")

        bracket_offset += tick_depth + TEXT_PT + bracket_gap
```

Visual result:
```
   \──────────/     \──────/
     ****              ns
  [bar1] [bar2]   [bar3] [bar4]
```

### Bracket Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bracket_gap` | 10.0 | Vertical gap (display pts) between stacked bracket units |
| `tick_depth` | 6.0 | Depth of diagonal ticks (display pts). Larger = steeper |
| `bracket_lw` | 0.8 | Line width — 0.8 is clean and publication-ready |
| `use_broken_axis` | True | Enable broken axis; auto-disabled if data doesn't need it |
| `test_method` | "chi2" | `"chi2"` or `"fisher"` (for small samples) |

### Significance Bracket Pitfalls

- **ns color MUST be same as stars (black)** — user explicitly rejected gray. Distinguish by fontsize (12 vs 9) and weight (bold vs normal) only.
- **Diagonal ticks must be OUTWARD** — `\` goes down-LEFT from bar1, `/` goes down-RIGHT from bar2.
- **Reset `bracket_offset` per SV type** — NOT globally. Each type's brackets start fresh from its own `y_base`.
- **`bracket_offset` increment** — use `tick_depth + TEXT_PT + bracket_gap`, NOT `LEG_PT + TEXT_PT + bracket_gap`.
- **Store ALL pairs including ns** — so every comparison gets a bracket annotation.
- **Draw bracket as SINGLE POLYLINE** — never 3 separate `ax.plot()` calls (causes line-cap overlap at junctions).
- **`bracket_lw` default 0.8** — thicker lines (1.2+) look heavy.

## 9. Vertical Reference Lines with Threshold Annotations

When drawing vertical reference lines (e.g. threshold depth markers) with `ax.vlines()`, the threshold value must be clearly visible without colliding with x-axis tick labels.

### Correct pattern: clean ticks + always-on leader line annotation

**Never** add threshold values to x-axis tick labels. Keep x-axis ticks clean (base positions only). Use `ax.annotate` with a leader line below the x-axis to show every threshold value:

```python
# Draw full-length vertical line (y_bottom to target)
ax.vlines(threshold_x, y_bottom, target_y,
          colors=["red"], linestyles="dashed",
          label=f"threshold={value:.2f}")
ax.scatter([threshold_x], [target_y], color="red", s=26, zorder=4)

# Leader line: ALWAYS show threshold value below x-axis
ax.annotate(
    f"{threshold_x:.0f}x",
    xy=(threshold_x, y_bottom),       # anchor at line bottom
    xytext=(8, -28),                   # offset in display points
    textcoords="offset points",
    ha="left", va="top", fontsize=8, fontweight="bold", color="red",
    arrowprops=dict(arrowstyle="-", color="red", lw=0.8,
                    connectionstyle="angle,angleA=-90,angleB=180,rad=0.2"),
    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="red", lw=0.5, alpha=0.9),
)
```

### Multiple curves: same pattern, per-curve colors

```python
for idx, x_threshold in enumerate(warped_threshold_x):
    ax.vlines(x_threshold, y_bottom, sensitivity_threshold,
              colors=[threshold_colors[idx]], linestyles="dashed", alpha=0.85)
    ax.scatter([x_threshold], [sensitivity_threshold],
               color=threshold_colors[idx], s=24, zorder=4)
    ax.annotate(
        f"{threshold_x_values[idx]:.0f}x",
        xy=(x_threshold, y_bottom), xytext=(8, -28),
        textcoords="offset points",
        ha="left", va="top", fontsize=8, fontweight="bold",
        color=threshold_colors[idx],
        arrowprops=dict(arrowstyle="-", color=threshold_colors[idx], lw=0.8,
                        connectionstyle="angle,angleA=-90,angleB=180,rad=0.2"),
        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                  ec=threshold_colors[idx], lw=0.5, alpha=0.9),
    )
```

### Raw scatter + smoothed curve + method annotation

Always show raw data points alongside the smoothed curve, and annotate the fitting method:

```python
ax.scatter(x_raw, y_raw, color="#1f77b4", alpha=0.85, label="Raw points")
ax.plot(x_smooth, y_smooth, color="#ff7f0e", linewidth=2.2,
        label=f"Smoothed curve ({method})")

# Method annotation — bottom-right corner
if method != "none":
    ax.text(0.98, 0.02, f"fit: {method}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color="gray",
            style="italic", alpha=0.7)
```

For multiple curves, use per-curve colors for scatter:

```python
ax.scatter(map_x(x_raw), y_raw, color=color, alpha=0.25, s=20)  # raw
ax.plot(map_x(x_smooth), y_smooth, color=color, linewidth=2.2)  # smoothed
```

### Threshold label naming

Use `"threshold"` not `"Sensitivity threshold"` — shorter, cleaner:

```python
# vlines legend label
label=f"threshold={value:.2f}"
# horizontal reference line legend label
label=f"threshold = {value:.2f}"
```

### Pitfalls

- **Anti-pattern: add threshold to x-ticks** — causes tick label to sit directly on the dashed vertical line. Even hiding the label with `""` leaves a tick mark that clutters the axis. Never add threshold values to `ax.set_xticks()`.
- **Anti-pattern: shorten the vertical line + text below axis** — visually ugly, rejected by user. Never use `y_line_bottom = y_bottom + 0.06 * y_range` + `ax.text()` below the axis.
- **Anti-pattern: conditional leader line only on overlap** — if you only show leader lines when threshold is close to an existing tick, thresholds far from any tick have NO visible value at all. Always show the leader line.
- **Keep consistent styling across related functions** — when you have a single-item and multi-item variant of the same plot, they must share: `ax.grid(alpha=0.3, linestyle="--")`, same vlines/scatter/leader-line style, same method annotation. Don't let the multi variant drift into a different visual language.
- **Leader line `xytext=(8, -28)` offset** — empirically good for most figure sizes. `(4, -22)` is too tight; `(8, -28)` gives enough clearance from the axis.
- **Multiple curves with warped x-axis** — when using x-axis warping (e.g. steep-region emphasis), the leader line anchor uses `warped_threshold_x` (display position), but the label text uses `threshold_x_values` (actual depth value).

## 10. Common Matplotlib API Pitfalls

- **`ax.legend()` does NOT accept `alpha`** — use `framealpha` for legend box transparency. `alpha` is for plot elements (lines, bars), not the legend container.
- **Title parameter pattern** — when adding optional `title: str = ""` to plotting functions, use conditional placement before `fig.tight_layout()`:

```python
if title:
    ax.set_title(title, fontsize=12, fontweight="bold")
fig.tight_layout()
```
