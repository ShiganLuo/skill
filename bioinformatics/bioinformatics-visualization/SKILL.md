---
name: bioinformatics-visualization
description: Build Python CLI tools for genomics SV visualization — OncoPrint, comparison bar charts, significance brackets, multi-format output.
triggers:
  - oncoprint
  - SV comparison plot
  - significance bracket
  - plot_svtype_comparison
  - multi-format image output
  - bioinformatics plotting CLI
---

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

## Genome Browser Element Conventions (gene structure plots)

When plotting gene structure on DNA-level figures (circular ecDNA maps, SV context plots):

- **Shape = element identity.** Exon: solid full-height bar. Intron: thin connector line (~8% of exon width). UTR: same band as exon but paler (white overlay ~65% alpha on the gene-colour block) — never a separate half-height block layered on top; layered blocks read as unrelated elements.
- **UTR coordinates in GENCODE exons include the UTR span** — the exon block is the full exon; overlay the UTR interval paler rather than drawing UTR as an extra feature, otherwise blocks look inflated.
- **Gene-level truncation marks (`//`) go only on the gene span ends at the cycle junction** — never per-exon/per-UTR. Per-feature boundary checks misfire on terminal UTRs (they sit exactly on clip boundaries) and scatter `//` across internal features, which readers read as extra junctions.
- **Proportions are read literally by reviewers**: the intron connector must be visibly thinner than the exon block; if the two widths are within ~2x, users complain the intron is 'thicker than the exon'. Keep connector width ≤10% of the block width.
- **Legends list functional elements, not miniature models.** One horizontal straight swatch per element (exon / intron / UTR / coverage / break), same width-height ratios and opacity as the plot. No arc-shaped or curved legend samples (a lone arc has no frame of reference), no colour duplicates — all gene elements share the gene colour; shape and opacity carry the distinction, colour does not. State marks (oncogene highlight, junction break) are conditional entries, shown only when present.
- **Don't draw redundant junction markers**: if the data layer already shows fragment joins (e.g. white gaps in a coverage ring) and `//` marks clipped genes, a third dedicated tick/mark at every join point is triple encoding — remove it.

### Circular Genome Map Radii (CGView-style)

Declarative width/radius constants at module top; users tune proportions by editing constants, so name and comment them clearly:

```python
R_RULER = 1.0    # outer tick ruler
R_COV_OUT = 0.90 # coverage ring outer
R_COV_IN = 0.72  # coverage ring inner
R_GENE = 0.60    # outermost gene lane
LANE_W = 0.13    # gene lane width
EXON_W = 0.10    # exon block radial width
INTRON_W = 0.008 # intron line width (~8% of EXON_W)
```

- Map genomic intervals to angles through one central helper (`interval -> (a0, a1)`); per-feature recomputation must reuse it or arcs misalign with blocks.
- Multiple genes on one circle: greedy lane assignment longest-arc-first; collision test on angular overlap.

### One Pass Over Large GTFs

Loading gene + exon + UTR features from a full GENCODE GTF: read the file ONCE and bucket by feature type in the same loop (4 separate passes over a 700 MB GTF ≈ 6 s; 1 pass ≈ 3 s; gffutils build ≈ 145 s + 1.5 GB db — worse for one-shot full loads, only worth it for repeated incremental region queries). gffutils may be absent from the runtime container anyway — keep optional: `try: import gffutils except ImportError: gffutils = None` when a function using it is never called by the CLI.

## Pitfalls

### Parallel plotting: use ProcessPoolExecutor, never ThreadPoolExecutor

gffutils uses SQLite internally — SQLite objects cannot cross thread boundaries (`sqlite3.ProgrammingError`). Even if thread-safe, Python's GIL prevents true parallelism for CPU-bound matplotlib work. Always use `concurrent.futures.ProcessPoolExecutor` with `-j/--threads` arg. Move `create_db()` inside the worker function so each process gets its own connection. See `python-scientific-plotting-scripts` skill §6 for full pattern.

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

## Verify Plot Refactors Inside the Execution Container

Matplotlib/pandas deps usually live in the pipeline's SIF, not the host. Smoke test with synthetic fixtures (2 fragments + a 3-gene GTF covering intact / truncated / UTR-bearing genes) via:

```bash
apptainer exec --bind /tmp/fixtures:/smoke --bind <repo>:/proj <env.sif> python /smoke/run_test.py
```

and inspect the PNG with vision analysis, checking specific claims (symbol positions, legend correspondence, colour separation) rather than trusting exit code 0.
