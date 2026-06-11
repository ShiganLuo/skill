# Plotting Utilities for SV Frequency Correction

Location: `workflow/gene/sv/question.py`

Publication-quality plotting functions for SV frequency analysis.
All share the same style conventions: `pdf.fonttype=42`, `ps.fonttype=42`,
`sns.set_style("whitegrid")`, no top/right spines, y-axis grid, 600 dpi output.

## Functions

### `single_violin_plot(df, value, key=None, threshold=None, ...)`

Single or per-category violin + strip plot with box interior.

- `key=None`: one overall violin
- `key="FusionType"`: one violin per category
- `inner="box"`: shows Q1/median/Q3/whiskers inside violin
- `cut=0`: violin clipped at data range (no extension beyond min/max)
  - `cut=1` (seaborn default): extends 1 bandwidth beyond extremes
  - Use `cut=0` for bounded data like frequencies (0~1)
- `threshold=0.02`: red dashed line + legend showing % below threshold
  - Single violin: `"< 0.02: 23.5%"`
  - Per-category: `"< 0.02: CTX-1 15.3%, CTX-2 8.2%"`
- `show_median=False` by default (box interior already shows median)
- `show_points=False` by default (overlay individual data points as strip plot)
- `xtick_fontsize=10`: x-axis tick label font size

### `single_bar_plot(df, value, key=None, threshold=None, errorbar="se", ...)`

Bar chart with error bars + individual data points.

- `show_mean=True`: bars show mean; `False` for median
- `show_bar=True`: whether to draw bars (set `False` to show only points)
- `show_points=False`: overlay individual data points as strip plot
- `errorbar`: `"se"` (SEM), `"sd"` (SD), `"ci95"` (95% CI)
- `threshold`: same red dashed line + percentage legend as violin
- Points jittered with fixed seed (reproducible)
- **Default sort: descending by mean value** (largest bar first)
  - `sort_keys=False` preserves original data order
  - `order=[...]` overrides with explicit ordering
- `xtick_fontsize=10`: x-axis tick label font size
- X-axis labels rotated 45° with `ha="right"` to avoid overlap

### `paired_violin_plot(df, key, values, ...)`

Two violins side-by-side with paired connecting lines per sample.
`values` must be exactly 2 columns. Gray lines connect paired observations.

### `violin_plot(df, key, values, ...)`

Grouped violins with per-mutation base colors and per-group lightness/saturation
adjustment via `adjust_group_color()`. Uses `inner="quartile"`.

## Common Parameters

| Param | Description |
|-------|-------------|
| `order` | Explicit x-axis category ordering |
| `sort_keys` | In `single_bar_plot`: sort by descending mean (default). In `violin_plot`: alphabetical |
| `palette` | seaborn colormap name (default `"Set2"`) |
| `figsize` | Tuple in inches |
| `point_size` / `violin_alpha` / `bar_alpha` | Visual tuning |
| `threshold` | Float for red dashed line + % legend |
| `xtick_fontsize` | X-axis tick label size (default 10) |

## Key Seaborn/Matplotlib Notes

- `inner="box"` vs `inner=None"`: `"box"` draws a mini box plot inside the violin
  (Q1, median, Q3, whiskers). `None` draws nothing — if you want just a median line,
  use `inner=None` + custom `ax.hlines()`.
- `cut` parameter: multiplier for bandwidth beyond data extremes.
  `cut=0` is safest for bounded data.
- Always rotate x-axis labels (`rotation=45, ha="right"`) when category names are long.
- Font size 12 is too large for x-tick labels with many categories; default to 10.

## Usage Pattern

```python
from question import single_violin_plot, single_bar_plot

# Delta frequency violin with threshold
single_violin_plot(
    df, value="delta_frequency_Freq", key="mutation",
    threshold=0.02, ylabel="Delta Frequency",
    outfile="delta_violin.png",
)

# Bar chart — bars sorted largest-first by default
single_bar_plot(
    df, value="Freq", key="FusionType",
    threshold=0.01, errorbar="se",
    xlabel="SV Type", ylabel="Frequency",
    xtick_fontsize=8,
    outfile="freq_bar.png",
)

# Single violin (no grouping)
single_violin_plot(
    df, value="Freq", threshold=0.01,
    ylabel="Frequency", outfile="freq_single.png",
)
```
