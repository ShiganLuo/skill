# Bioinformatics Visualization Pipeline

Patterns for building Python CLI tools that produce publication-quality plots from genomics SV (structural variant) data.

## Core Patterns

### PlotFormat Type Alias

Always define at module level, constrain function params via type hint:

```python
from typing import Literal, List, Optional
PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]

def my_plot(
    data: pd.DataFrame,
    out_prefix: str,
    image_formats: Optional[List[PlotFormat]] = None,
) -> None:
    if image_formats is None:
        image_formats = ["png"]
    # ...
    for fmt in image_formats:
        plt.savefig(f"{out_prefix}.{fmt}", dpi=300)
```

### CLI Argument Patterns

Unified style across all scripts:

```python
# Multi-format output
parser.add_argument("-f", "--format", action="append", dest="formats",
                    metavar="FMT", help="Image format, repeatable. Default: png.")

# Dict-like inputs: use "key=value" or "key:path" format
parser.add_argument("-g", "--group", action="append", metavar="NAME:VCF")
# Parse: name, path = item.split(":", 1)
```

**Never** use paired parallel lists (`--files` + `--names`). Always use a single parameter with `key=value` format.

### N-Group Comparison Bar Chart

Support arbitrary number of groups, not just 2:

```python
n_groups = len(group_order)
total_width = 0.8
bar_width = total_width / n_groups
offsets = [bar_width * (i - (n_groups - 1) / 2) for i in range(n_groups)]

# Auto-generate colors from tab10
cmap = plt.cm.tab10
colors = {g: cmap(i / max(n_groups - 1, 1)) for i, g in enumerate(group_order)}

# Draw bars
for i, g in enumerate(group_order):
    ax.bar(x + offsets[i], pivot[g], bar_width, color=colors[g], label=legend_map[g])
```

### Auto-Detect Broken Axis

Don't always use broken axis — only when an outlier dominates:

```python
global_max = pivot.values.max()
sig_max = pivot.loc[sig_sv].values.max() if sig_sv else np.median(pivot.values)
need_broken = use_broken_axis and (global_max > sig_max * 2.0)
```

### Significance Brackets (宝盖头 Style)

Single polyline avoids line-cap overlap at junctions. Diagonal ticks point at bar centers:

```python
tick_x = bar_width * 0.25
_, y_tick = inv.transform((0, y_hat_disp - tick_depth))

# Single polyline: left tick bottom → left top → right top → right tick bottom
ax.plot(
    [x1 - tick_x, x1, x2, x2 + tick_x],
    [y_tick, y_hat, y_hat, y_tick],
    lw=bracket_lw, c="black",
)
```

Key parameters:
- `bracket_gap: float = 10.0` — vertical gap between stacked bracket units (display points)
- `tick_depth: float = 6.0` — diagonal tick depth (display points), controls steepness
- `bracket_lw: float = 0.8` — line width, 0.8 is clean and thin

**Never** draw bracket as 3 separate lines — always use single polyline.

### OncoPrint Visualization

Layout: main grid + right frequency bar + top count bar.

**CRITICAL — gridspec ratios must be FIXED, never raw data dimensions:**

```python
# CORRECT: fixed ratios, main grid gets most space
gs = fig.add_gridspec(2, 2,
    width_ratios=[4, 1],
    height_ratios=[1, 4],
    wspace=0.04, hspace=0.04)

ax_top = fig.add_subplot(gs[0, 0])
ax_main = fig.add_subplot(gs[1, 0])
ax_right = fig.add_subplot(gs[1, 1])   # NO sharey — set limits independently
```

**WRONG — causes extreme compression when n_genes or n_samples is large:**
```python
# NEVER DO THIS — when n_genes=20, height_ratios=[0.8, 20] compresses main grid to nothing
gs = fig.add_gridspec(2, 2,
    width_ratios=[n_samples, 1.2],
    height_ratios=[0.8, n_genes], ...)
ax_right = fig.add_subplot(gs[1, 1], sharey=ax_main)  # sharey couples coordinate systems
```

**Pitfalls:**
1. **Never use `n_samples` / `n_genes` as gridspec ratios** — a gene list of 20 gives `height_ratios=[0.8, 20]`, squeezing the main grid into ~4% of vertical space. Use `[1, 4]` instead.
2. **Never use `sharex`/`sharey`** between main grid and margin axes — coordinate coupling causes barh direction mismatches. Set `xlim`/`ylim` independently on each axis.
3. **Set `xlim`/`ylim` BEFORE drawing bars** — especially for `barh` with inverted y-axis (`set_ylim(n_genes-0.5, -0.5)`). Drawing first then setting limits can clip or misplace bars.

Margin axis setup order (correct):
```python
# Right margin — set ylim first, then draw barh
ax_right.set_ylim(n_genes - 0.5, -0.5)   # same orientation as main (row 0 at top)
ax_right.barh(range(n_genes), mut_freq, color="#34495E", height=0.6)
ax_right.set_xlim(0, 100)
ax_right.invert_xaxis()

# Top margin — set xlim first, then draw bar
ax_top.set_xlim(-0.5, n_samples - 0.5)   # same orientation as main
ax_top.bar(range(n_samples), sample_counts, color="#34495E", width=0.6)
```

SV type colors: DEL=#E74C3C, DUP=#3498DB, INS=#2ECC71, INV=#9B59B6, BND=#F39C12, OTHER=#95A5A6.

Multi-type cells: stack colored rectangles vertically within the cell (k=0 at bottom, k=n-1 at top).

### Pairwise Significance for N Groups

When comparing N groups, iterate all pairs and keep best p-value:

```python
for sv in pivot.index:
    best_p = 1.0
    for i, g1 in enumerate(group_list):
        for g2 in group_list[i + 1:]:
            # build 2x2 table, compute p
            best_p = min(best_p, p)
    stars[sv] = p_to_star(best_p)
```

## Pitfalls

### Parallel plotting: use ProcessPoolExecutor, never ThreadPoolExecutor

gffutils uses SQLite internally — SQLite objects cannot cross thread boundaries (`sqlite3.ProgrammingError`). Even if thread-safe, Python's GIL prevents true parallelism for CPU-bound matplotlib work. Always use `concurrent.futures.ProcessPoolExecutor` with `-j/--threads` arg. Move `create_db()` inside the worker function so each process gets its own connection.

### chi2_contingency with zero expected frequencies

When a group has zero counts for an SV type, the contingency table degenerates. Always guard:

```python
table = np.array([[a, b], [c, d]])
if table.min() < 0 or table.sum() == 0 or (table.sum(axis=0) == 0).any():
    continue
try:
    _, p, _, _ = chi2_contingency(table)
except ValueError:
    continue
```

### int in command list

Command lists require all `str` items. Always convert: `str(ins_bin_size)`.

### Docstring placement with default-param initialization

When using `if param is None: param = default`, place the `if` block **after** the docstring, not before:

```python
def foo(x: Optional[List] = None) -> None:
    """Docstring goes here."""
    if x is None:
        x = []
```

### Hardcoded group counts

Never hardcode `group_order[0]` / `group_order[1]`. Always iterate with `enumerate(group_order)`.

## Function Signature Conventions

- Optional list params: `param: Optional[List[Type]] = None` + `if param is None: param = [default]`
- Dict params instead of paired lists: `condition_files: Dict[str, str]` not `files: List[str], names: List[str]`
- Use `from __future__ import annotations` for forward refs
- All functions get NumPy-style English docstrings
