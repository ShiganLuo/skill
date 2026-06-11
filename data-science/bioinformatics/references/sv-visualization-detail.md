# SV Visualization — Full Implementation Detail

## PlotFormat Type Alias

```python
from typing import Literal, List, Optional
PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]
```

## CLI Argument Patterns

Unified style — never use paired parallel lists:

```python
# Multi-format output
parser.add_argument("-f", "--format", action="append", dest="formats",
                    metavar="FMT", help="Image format, repeatable. Default: png.")

# Dict-like inputs: "key=value" or "key:path"
parser.add_argument("-g", "--group", action="append", metavar="NAME:VCF")
# Parse: name, path = item.split(":", 1)
```

## N-Group Comparison Bar Chart

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

## OncoPrint Layout (CRITICAL)

Layout: main grid + right frequency bar + top count bar.

**Gridspec ratios must be FIXED:**

```python
gs = fig.add_gridspec(2, 2,
    width_ratios=[4, 1],
    height_ratios=[1, 4],
    wspace=0.04, hspace=0.04)

ax_top = fig.add_subplot(gs[0, 0])
ax_main = fig.add_subplot(gs[1, 0])
ax_right = fig.add_subplot(gs[1, 1])   # NO sharey
```

**WRONG — causes extreme compression:**
```python
# NEVER: when n_genes=20, height_ratios=[0.8, 20] compresses main grid to nothing
gs = fig.add_gridspec(2, 2,
    width_ratios=[n_samples, 1.2],
    height_ratios=[0.8, n_genes], ...)
ax_right = fig.add_subplot(gs[1, 1], sharey=ax_main)
```

**Pitfalls:**
1. Never use `n_samples`/`n_genes` as gridspec ratios — use `[1, 4]` instead
2. Never use `sharex`/`sharey` between main grid and margin axes
3. Set `xlim`/`ylim` BEFORE drawing bars

### Margin Axis Setup Order (Correct)

```python
# Right margin — set ylim first, then draw barh
ax_right.set_ylim(n_genes - 0.5, -0.5)
ax_right.barh(range(n_genes), mut_freq, color="#34495E", height=0.6)
ax_right.set_xlim(0, 100)
ax_right.invert_xaxis()

# Top margin — set xlim first, then draw bar
ax_top.set_xlim(-0.5, n_samples - 0.5)
ax_top.bar(range(n_samples), sample_counts, color="#34495E", width=0.6)
```

## SV Type Colors

DEL=#E74C3C, DUP=#3498DB, INS=#2ECC71, INV=#9B59B6, BND=#F39C12, OTHER=#95A5A6

Multi-type cells: stack colored rectangles vertically (k=0 at bottom, k=n-1 at top).

## Pairwise Significance for N Groups

```python
for sv in pivot.index:
    best_p = 1.0
    for i, g1 in enumerate(group_list):
        for g2 in group_list[i + 1:]:
            # build 2x2 table, compute p
            best_p = min(best_p, p)
    stars[sv] = p_to_star(best_p)
```

## Additional Pitfalls

- **Parallel plotting**: use ProcessPoolExecutor (gffutils uses SQLite internally — cannot cross thread boundaries)
- **chi2_contingency with zero expected frequencies**: always guard with pre-check + try/except
- **int in command list**: always `str(ins_bin_size)` — subprocess requires all str items
- **Docstring placement**: with `if param is None: param = default`, place `if` block AFTER the docstring
- **Hardcoded group counts**: never `group_order[0]`/`group_order[1]`, always iterate with `enumerate`
