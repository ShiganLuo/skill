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

- **CJK fonts in matplotlib** — when plot labels contain Chinese/Japanese/Korean characters, the default DejaVu Sans font renders them as empty boxes. Fix: use `matplotlib.font_manager.FontProperties(fname="/path/to/cjk-font.ttc")` for tick labels/axis labels, or configure `matplotlib.rcParams["font.sans-serif"]` to include a CJK font (e.g., SimHei, WenQuanYi Zen Hei). Check available CJK fonts with `fc-list :lang=zh`. In apptainer/SIF runs the container typically ships Latin-only fonts (host `fc-list` shows CJK but matplotlib inside the container sees none): copy a host CJK `.ttc` to a bind-mounted path (e.g. `/tmp/fonts/`), then `font_manager.fontManager.addfont(path)` and set `rcParams["font.family"]` to `FontProperties(fname=path).get_name()`. Success criterion: zero `Glyph ... missing` warnings on `savefig`. Only fall back to English labels when no CJK font can be obtained at all.
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

Small-n rank tests have a hard p floor — Mann-Whitney on n=3 vs 8 cannot produce p below ~1/C(11,3)≈0.006, so genome-wide BH over hundreds of thousands of tests returns zero significant loci even where effect sizes are huge (min padj≈0.3 measured). For per-locus significance across genome-wide tests use a borrow-strength model (DESeq2/edgeR); if the figure marks loci by effect size alone (e.g. a log2FC threshold), state that in the legend/doc rather than implying significance.

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

## 9. Figure Layout Pitfalls (grouped bar charts)

- **Legend must never cover bars — and never fix it by inflating figure height** — an in-axes legend lands on the tallest bars; moving it to another in-axes corner just overlaps different bars; extra `figsize` height only stretches the bars and does not clear space (rejected in review). The verified pattern for multi-panel figures is a DEDICATED legend strip: split the gridspec into an extra row (`height_ratios=[0.5, 8]`), put a dummy `axis('off')` axes there holding the legend (`loc="center left", ncol=len(entries)`), and keep the real panel in the row below at its normal height. One shared figure-level legend beats a legend per axes (less duplication, no overlap).
- **Iterate on figure review via vision on the rendered PNG, in whole-panel framing** — the user rejects figures with any text/element collision; after each fix re-render and inspect the FULL figure (legibility of small fonts, label vs line collisions, legend placement) before answering, and when the user says a spot is still colliding, fix the named collision directly — do not re-derive from code alone.
- **Reference-line (axhline/axvline) labels: line-end placement in empty space, staggered** — labels written inline where lines cross data collide with bars/points. Anchor each label at the end of its line in the empty margin (ha toward the plot edge), and when two reference lines sit close together, stagger vertically (one above its line, one below) — side-by-side offsets still collide when the lines are <1 data unit apart.
- **No redundant identity labels on ordered bars** — when bars are already ordered by a key the user specified (e.g. ascending fragment length along x), the position encodes identity; per-bar letter/number annotations are clutter and get removed on review. Add a label only if the ordering key itself is not legible from the figure.
- **A filter that drops items from a panel must render them, not silently omit** — when unestimable entries (inf/NaN from empty background, zero-count rows) are excluded from an evidence plot, draw them at a fixed anchor (e.g. x of the axis minimum) as hollow markers with an 'n.e.' note, or the figure loses whole circles/genes and the user asks why items are missing.
- **Change of data source is a statistics change: re-derive every derived number in the doc** — when a figure's input switches (e.g. decoil reconstruct.json → filtered.bed, or flank windows start masking circle intervals), the companion doc's numbers (METHOD.md tables, summary counts) no longer match the figure. Re-run the stats, update every quoted value, and note the superseded source explicitly; stale numbers in docs are caught by the user as "数据和文档对不上".
- **When one dot encodes two variables, one of them must move off the y axis** — stacking per-category dots on a single y=0 line collapses same-x points into one blob (the user reads it as missing items). Dodge co-located points vertically in fixed order (e.g. 0.075 * rank within rounded-x bucket) and switch the color encoding to the category dimension the user names (sample), with a matching legend; order the legend to the sample list, not alphabetically.
- **Rotated x-tick labels overlap when the figure is too narrow** — long pathway/sample names at rotation=30 on a 13-inch 2-panel figure still collide. Widen the figure (e.g. 15x6) AND raise rotation to 45 with `ha="right"` (the rotation anchors the label end, keeping alignment); verify visually, not by code review. In multi-row panel grids the row above's rotated tick labels reach DOWN into the next row's panel titles — reserve `hspace` (e.g. `row_spacing` ≈ 0.6 as a gridspec param) for that label band instead of discovering it at render time.
- **Stat annotations (p values) need reserved in-axes headroom** — placing p texts just above the tallest group and letting autoscale decide puts them over the panel title or through the violin tops. Compute the data range once, `set_ylim(bottom - 0.08*span, top + headroom*span)` with `headroom` ≈ 2.4 as a parameter, stagger the p texts inside that band at `top + 0.06*span`, and `clip_on=True` — the reserved band IS the non-overlap guarantee.
- **pandas index alignment silently shrinks data** — building a DataFrame from per-key Series with slightly different indexes (duplicate gene_name rows, renamed columns) yields NaN gaps or missing columns without erroring. `groupby(level=0).mean()` + explicit `.reindex()` on a shared index after every reshape; print shapes before plotting.
- **Exclude-before-rename when sample names collide** — if kept samples are renamed onto names used by excluded ones (e.g. keep hFibroblasts4/6/7, rename to hFibroblasts1/2/3, while hFibroblasts1/2/3 are excluded), applying EXCLUDE after RENAME deletes the wrong columns and the group silently becomes empty. Filter originals first, then rename; print group counts to catch an empty group.

## 10. Crowded Label Layouts (rotated-text collision resolution)

When many text labels surround a circular or dense figure (ring plots, circos-style layouts), naive separation fails. Verified procedure:

- **Fix axes limits BEFORE any collision loop** — `get_window_extent()` measured under auto-scale gives pixel distances that do not match the final layout; the loop then misses real overlaps (a geometrically overlapping pair reads as separated in-loop) no matter how many iterations run. Call `set_xlim/set_ylim` first, then iterate draw → measure → push.
- **Rotated text's axis-aligned bbox badly overestimates** — `Bbox.overlaps()` flags phantom overlaps (two visually separated tangential labels always "overlap" via AABB corners). Invert the rotation projection for true text length/height: `L=(w·|cosθ|−h·|sinθ|)/(cos²θ−sin²θ)`, `H=(h·|cosθ|−w·|sinθ|)/(cos²θ−sin²θ)` (θ = rotation mod 180°; at exactly 45° fall back to max/min of w,h). Then use oriented-rectangle SAT distance — max of the 4 center-delta projections onto both rectangles' axes minus half-extents; < 0 ⇒ overlap.
- **Greedy angular push must be wrap-aware** — sort labels by angle, start pushing from the largest angular gap, and shrink the step proportionally when labels cannot fit the arc. A naive forward push drives late labels across 360° back onto the first ones.
- **Dense clusters: radial stacking columns** — group labels within an angular window into radial columns (row height ≈ 2-3× text height, small per-row angular spiral offset to spread each column, cap rows per column so extreme columns don't shrink the plot via expanded limits) instead of relying on push-apart alone.
- **Verify programmatically** — after rendering, run an all-pairs SAT scan over label segments and assert 0 overlaps; eyeballing misses diagonal near-collisions that become overlaps at different DPI.
- **Fix axes limits before drawing gene models on arcs** — when annotating genes on a circular track (exon blocks / intron arcs mapped from genomic coordinates to angles), the intron backbone must be drawn as a thin arc (a Wedge), never a two-point straight line: a truncated or large gene whose body spans a wide angle produces a chord that cuts across the circle center. Same for arrow heads: derive them from the tangent at the endpoint angle, not from the chord direction.
- **Detection guard before per-item structure drawing** — when a step plots per-item structures from a filtered file, check for data lines first: header-only AND blank files both raise `pandas.errors.EmptyDataError` on `read_csv` (catch it explicitly); emit a labeled placeholder figure instead so downstream file expectations stay stable.
- **One-image-per-item output must still emit a fixed summary file** — when a pipeline rule declares a fixed output (e.g. a combined grid PNG) but a new option also writes a runtime-variable number of per-item images (one file per gene/cycle), the variable-count files cannot be rule outputs; generate them inside the rule as extra artifacts AND keep writing the declared fixed file, or Snakemake fails with MissingOutputException. Also `makedirs` the output directory when per-item paths build it lazily.

## 11. Circular Ring/Plasmid-Map Aesthetics (design-first)

For ecDNA/plasmid ring figures the user demands publication aesthetics (SnapGene/Circos standard) and design BEFORE code: render a draft, self-review it with vision against those references, list concrete flaws, then fix — do not iterate blindly. Verified design rules:

- **Features grow out of the backbone; never float** — gene arrow-blocks start at the ring's outer edge (petals on the backbone). Blocks drawn at a fixed radius away from the ring look detached and the gene-to-ring mapping is lost.
- **The backbone ring is the visual anchor** — medium width, muted low-saturation color. Coverage/dosage rings go INSIDE, thin, pale, translucent (background layer); a thick bright dosage ring competes with and beats the protagonist.
- **Labels stay HORIZONTAL, always** — rotated/tangential text around a circle is the #1 readability killer. Anchor each label next to its feature (ha by sign of cos(theta)); drop leader lines except a hairline gray connector when a label was pushed away from its feature angle.
- **Filter invisible features** — features shorter than ~0.4% of the ring circumference are sub-degree arcs: clutter on the figure. Keep them in the companion TSV, skip drawing.
- **Low-saturation palette** — multiple high-saturation hues (bright blue ring + bright orange coverage + pure red/orange features) read as toy charts. Desaturate everything; one hue family per layer; white hairline edges separate adjacent feature blocks.
- **kb ticks** — short white tick lines across the backbone + sparse horizontal labels (every other tick); plasmid-map convention that instantly reads as professional. Never rotate tick text.
- **Center hub text** for per-cycle stats (gene count / truncated count) instead of scattering them in the title.

### Geometry pitfalls specific to ring gene-models

- **Clip exon coordinates to the fragment before mapping to angles AND skip exons entirely outside** — an exon beyond the fragment end yields gs > 1 in the angle mapping and draws a giant wedge arc covering a quarter of the ring. Same clipping for gene bodies.
- **Never wrap-normalize angles that to_theta already mapped inside the current fragment arc** — values are by construction within [theta−span, theta]; a `% 360` normalization on them scatters blocks around the whole circle and paints over other features.
- **Draw the intron backbone as a thin arc (Wedge), never a two-point straight line** — a large or truncated gene spanning a wide angle produces a chord cutting across the circle center.
- **Arrowhead: clamp to ≤ half the body angle** (min 0.8°, max ~3°) and order Wedge theta args with min/max — the naive `if t_s > t_e` direction guard silently skips +strand genes, leaving only arrowhead triangles on the plot.
- **Horizontal labels use plain AABB overlap push** — with rotation=0 the oriented-rectangle SAT machinery is unnecessary; push colliding labels outward along their radial direction and re-measure.

See `matplotlib-significance-brackets` skill for full implementation details.

## 12. Programmatic figure QA + schematic generation

- **Audit text overlap with renderer bboxes, never eyeballs** — after any
  figure with floating labels, draw the canvas and check all-pairs
  `Text.get_window_extent(renderer)` overlap area (>4 px² counts). Floating
  annotations near panel titles/captions overlap at final DPI far more often
  than they appear to.
- **Audit ring geometry from pixels** — palette-color mask + largest
  connected component (excludes same-color text glyphs, the top false-
  positive source) + polar scan at band mid-radius; 0.2° gaps = anti-aliasing
  noise.
- **Schematics/legends: matplotlib Wedge patches only, never HTML+
  headless-Chrome screenshots** — hand-written SVG arcs are unverifiable
  (full-circle dasharray covers the whole ring; transform-rotate draws stray
  shapes).
- **Degenerate Wedge range** — `Wedge(..., 32, 392)` renders a FULL ring
  (392 = 360 + 32); a slit needs end < start + 360 − slit_width.
- **Show orientation reversal as large white arrows on the band with
  opposite reference arrows on flanking normal segments** — small
  dark-on-dark triangles are invisible; the direction CONTRAST carries the
  meaning.

## 15. Genome-wide Manhattan scatters (millions of points)

- Cap background points at render time (~300k, seeded subsample, log the reduction) but always draw burst/highlight points in full — 3.8M scatter markers take >15 min to raster, the plot itself stays honest when the cap is a documented rendering detail.
- One text artist per point label is the real killer: labeling every highlighted locus (32k texts) hangs matplotlib indefinitely. Give labels a budget (top-N by |value| among marked loci, keep N <= 30).
- Rotated tick labels (45°): the binding collision constraint is PERPENDICULAR distance between neighboring label baselines — required center distance = (text_height + gap)/sin(theta). The AABB footprint (W·cos + H·sin) overestimates and over-thins (dropped chr16/chr18 while chr1-19 all fit). Near-horizontal (<15°) packs by width instead.
- Small scaffolds (unplaced contigs) have tiny observed spans so their centers nearly coincide: thin tick LABELS greedily by spacing, keep every chromosome's minor tick, and log kept/total. Calibrate the spacing threshold against the render: if a primary chromosome label (chr1-19/X/Y) gets thinned, the axes-width estimate is too generous or the gap too large — tighten until thinning removes only scaffolds.
- Label dodge must be deterministic stacking, not pairwise push iterations — pairwise push oscillates (a middle label gets pushed both ways every round) and leaves residual stroke overlaps after the iteration cap. Measure annotation bboxes AFTER one `fig.canvas.draw()` (annotation offsets are unresolved before it — measuring early silently disables collision avoidance), cluster labels by x overlap with a small horizontal margin (~10 px), stack each cluster bottom-up with a fixed gap, and flip a cluster to stack downward from a below-point anchor when upward stacking would overflow the axes top.
- Reference-line labels and other in-plot text need zorder above the scatter layers (burst points at zorder 4 covered a zorder-3 line label — the label "vanished" although it was drawn).
- Locus-level TE input for Manhattan plots: count per locus with featureCounts `-t exon -g transcript_id` on the rmsk TE GTF (transcript_id is the unique locus id) and join values back keyed by that id. subread 2.x counts fragments only with `-p --countReadPairs` on paired-end BAMs (bare `-p` aborts), and apptainer-run tools need the data tree bound explicitly (`-B`).

Full recipes: `references/decoil-legend-and-audit.md`.

## 13. Genome-browser gene-model tracks (region figures)

When a region figure shows genes under sample/interval tracks (ecDNA families,
locus maps), the user's verified conventions:

- **Gene models in decoil_structure style** — exon blocks (one distinct hue per
  gene, keyed by name), thin intron connector lines between blocks, pale
  half-height UTR overlays on exon ends, a SMALL chevron on the body midline at
  the 3' end for strand. Gene-colored chevrons need a white stroke
  (`path_effects=[pe.Stroke(linewidth=1.8, foreground="white"), pe.Normal()]`)
  to stay visible on the exon fill; keep them subtle (width ~0.4% of span,
  height ~0.16×bar) — oversized arrows read as "喧宾夺主".
- **Largest gene in the innermost lane** (closest to the circle/sample tracks);
  sort by length descending, place each gene in the first lane with no overlap.
- **Labels: one fixed zone below the whole gene band, drawn in genomic order**
  (ascending start) so name order matches model order; center each label on
  its VISIBLE model center (clip gene to locus first); process labels
  largest-first so the biggest genes take the first label row (mirrors lane
  priority — the user checks that label order matches gene-size order);
  collision-check with estimated text width (char_w = fs × 0.72 pt→data;
  0.52 and even 0.66 underestimates — three rounds of "labels touch" on the
  same figure before 0.72 cleared it); label row height 0.30 (0.26 puts
  consecutive rows within glyph descender distance); wrap to next row on
  collision; clamp inside xlim with a 15% margin on the right clamp AND
  `clip_on=True` on the text — matplotlib text is unclipped by default and
  edge labels will overflow the panel.
  Do NOT place labels above models per-lane: it floats into the sample tracks
  and breaks left-to-right name/model ordering (both rejected in review).
- **Bottom-row labels need reserved space against the axis and the figure
  legend** — the last label row, the x tick numbers, and a figure-level legend
  at the panel bottom are three stacked layers; give the axes a bottom margin
  (gridspec `bottom`) and anchor the legend below it (`bbox_to_anchor` y<0),
  or the three collide (seen on the densest bottom family).
- **Label band height = exact**: lanes × pitch + label rows × row height;
  estimate label rows greedily. Oversized bands leave dead whitespace the user
  flags; too small and labels collide with x tick labels of the next panel.
- **One gene track per FAMILY/locus, not per sample** — samples sharing a locus
  share genes; drawing per-sample gene tracks duplicates information. Gene
  count per family differs by locus content (2–31 genes here) — that is
  biology, not a rendering bug.
- **Annotate locus genes for interpretation** — overlapping-gene TSV
  (full/partial containment vs the locus, GENCODE vM38 basic) plus named-gene
  summary per family in METHOD.md; the biological reading (MHC-I cluster,
  Hmgb1, chitinase cluster) lives in the doc, the figure shows structure only.
- **Hard-coded sample→circle-id maps are a single point of failure in
  cross-sample comparison figures** — before rendering a figure that compares
  "the same locus" across samples, verify each sample's circle id against the
  filtered.bed locus coordinates (chrom + span). A stale mapping (e.g. P20 →
  circ82 instead of circ22) silently compares the WRONG circles; the fix is
  one dict literal but the figure and its conclusions are invalid.
- **Explicitly report the full analysis inventory, not only the hits** — the
  user asks "确定分析了所有环吗" when a results doc lists only positives.
  State: total circles analyzed, coverage proof (regions.bed fragment count ==
  filtered.bed fragment count per sample), that every circle had nonzero
  internal/aligned reads (real negatives, not technical failures), and explicit
  zero-evidence rows for the remainder. Cross-reference high-RNA circles that
  still show zero junction reads — it is the strongest form of the
  "coverage is not evidence" argument.
- **Method/results docs state the FINAL method only — no error-process
  narratives** (user: "直接讲最终怎么做的就可以,我不关心错误做法"). Strip
  初版/修正/撤回/作废/重测 phrasing and before-after comparisons from
  METHOD.md/RESULTS.md; keep operation-critical warnings phrased as
  requirements ("四个文件必须全部喂入,否则静默漏检"), not history
  ("初版因此全部漏检"). Pre-compute the whole layout (lane counts, label
  rows, band heights) in one pass before drawing, so no per-family estimates
  leak into the docs as numbers.
- **Every evidence figure ships a companion RESULTS.md in the same directory** —
  the user asks "怎么没有输出结果文档" when a figure lands without one. Content:
  method summary (masking/dedup/empty-handling rules), one table per panel with
  the exact numbers verified against the source TSVs (re-derive after any data
  change — stale ranges get caught), and conclusions with an explicit boundary
  statement (what this evidence does NOT prove) plus a cross-reference to the
  stronger-evidence document.
- **Data-source change invalidates downstream statistics — re-verify both
  sources when a path discrepancy appears** — `reconstruct.ecDNA.filtered.bed`
  (filtered, 26 circles) and `reconstruct.json` (28 circles; filtered-out
  nodes like circ96 / PlaB circ83@chr17:36 live only in json) give different
  family counts and member lists. Decide the canonical source explicitly
  (the filtered bed, as the downstream standard), state it in METHOD.md, and
  re-run any figure/stats built on the other source.
- **Biological conclusions pair gene content with expression, per family** —
  for each breakpoint-sharing family join: locus genes (named, full/partial)
  × mean RNA/background ratio per member circle. Silent loci with heavy gene
  loads (H2-T MHC-I cluster ≤1.1x) vs extremely active loci with few named
  genes (Hmgb1/Alox5ap locus 141–244x) show transcription follows inherited
  chromatin state, not gene count; four-sample-consistent activity across
  treatment groups means the phenotype is not treatment-induced at the ecDNA
  level. State the boundary: ratio = regional transcription; circular
  transcription still requires seam reads (evidence 2).
- **Iterative figure restyling has a hard stop: revert beats refine** — when a
  layout experiment (per-family variable row heights, uniform-scale two-pass
  sizing) makes the figure visibly worse, revert to the last user-approved
  version wholesale instead of patching forward; cascading fixes on a bad
  layout produce aFrankenstein figure and user frustration ("恢复原状"). For
  spacing experiments, render a throwaway confirmation draft first and only
  replace the real figure after approval.
- **Fix label/gap complaints by measuring the actual rendered geometry, not by
  re-deriving constants from code** — a family of near-identical complaints
  ("labels overflow the axis", "names collide with models", "distance to the
  axis differs per panel") usually shares one root cause: text widths
  estimated too small (raise the char-width factor), text not clipped
  (`clip_on=True` on ax.text — matplotlib text is unclipped by default), or
  per-panel ylim ranges that differ while subplot heights stay equal (equal
  subplot heights + different data ranges = different data-units-per-pixel,
  so identical data gaps LOOK different; either normalize the scale with
  height_ratios proportional to the data range, or accept and revert).
  Diagnose which of the three before touching constants.
- **Separate layout planning from drawing — the user rejects monolithic draw
  loops ("代码不够抽象化,前后耦合太重;总体函数只负责调用和安排空间")** —
  structure these multi-row figures as: pure `plan_*` functions (data in →
  positions/counts out, no axes touched), one `draw_*` function per visual
  layer (tracks / breakpoints / gene models / labels), and `plot()` reduced to
  plan-all → allocate figure → call drawers. Incremental patches onto a single
  draw loop are what produced cascading "fix one thing break three" churn.
- **One packing implementation, run once** — label-row assignment must exist in
  ONE function that both the ylim calculation and the drawing call. A planning
  pass and a draw pass that each re-implement the packing drift apart (a gene
  present in one, missing in the other → KeyError; row counts differ →
  reserved band ≠ actual labels) and the figure breaks in ways only visible
  at render time.
- **Variable row heights: derive height_ratios from the precomputed layout** —
  when families differ in data volume (lane count × label rows), give each
  subplot `height_ratios = its data-unit total` at one common inches-per-unit
  scale; then every constant gap (header band, axis pad) renders at identical
  pixel size across rows. Equal-height rows + per-family ylim is what makes
  identical gaps LOOK different.
- **先恢复原状,再单独优化 — revert beats refine, and never mix the two** — when
  a layout experiment renders worse, restore the last user-approved version
  exactly (including undoing stacked "improvements") FIRST; then propose
  structural refactoring as a separate step. Mixing revert with new
  restructuring repeated the churn the revert was meant to end. When the user
  says a fix is wrong ("错的离谱"), stop patching — re-read their requirement,
  restate the concrete problems, and confirm the approach before the next
  render.

## 14. Heatmaps (imshow) — layout and contrast

Before writing the plot function, compute figure size from the MATRIX **and** its LABELS: `fig_w = base + n_cols * cell_w + longest_label_chars * char_w`. Sizing from matrix dimensions alone lets long gene-set/pathway names (60–80 chars) eat half the canvas and squeeze the heatmap into a sliver with dead whitespace.

- **Wrap long labels, never shrink font** — `textwrap.wrap(name, 40)` per y label, joined with `\n`; wrap x (sample) labels at ~12 chars. Put the wrap widths in function parameters (`label_wrap=40, sample_wrap=12`), not magic constants inline.
- **constrained_layout for colorbars** — `plt.colorbar(im, ax=ax)` creates a separate axes that `tight_layout()` does not manage; stacking `bbox_inches="tight"` on top leaves the colorbar floating detached with a whitespace band. Use `plt.subplots(constrained_layout=True)` and plain `fig.savefig(path, dpi=300)` (no bbox_inches).
- **Row-scale averaged z matrices by default** — a heatmap of set-level mean z-scores (mean of many gene z-scores) has variance shrunk well below ±1; with a global symmetric vmax the whole grid renders pale pink/blue with one or two dark outlier cells. Standardize each row to zero mean/unit variance before plotting (`row_scale=True` default) and size vmax from `nanmax(abs(values))` with a `or 1.0` guard for all-equal rows.
- **Cell crispness** — always `interpolation="nearest"` on imshow (default interpolation blurs cells under `aspect="auto"`); add white minor-grid separators: `set_xticks(np.arange(-0.5, n), minor=True)` (same for y) + `ax.grid(which="minor", color="white", linewidth=0.6)` + suppress minor tick marks.
- **Colorbar label semantics** — z-scores are dimensionless; never append the pre-transform as a unit ("Mean z-score (log2 TPM)" misreads as a unit). State the full chain: "Row z-score of mean gene z (log2(x+1) of TPM before z)".
- **Values outside the colorbar norm wrap around to mid-colormap colors** — `plt.Normalize` does NOT clip: an unbounded value (log2 ≈ −9 from a ~0.002 ratio, or > +7 from 200x) maps outside [0,1] and RdBu renders it near-WHITE, so an extreme cell looks empty/missing data ("这一格没有颜色"). Always `imshow(np.clip(mat, vmin, vmax))` — saturation at the endpoint color is the correct visual for beyond-scale values; name-check the most extreme cells when reviewing the render.
- **Elements that must sit OUTSIDE the heatmap get their own axes, never data-coordinate patches in the heatmap axes** — a `Rectangle`/text drawn at negative data x in the imshow axes shares its coordinate system, so xlim changes (auto-expansion, later rescaling) slide it back over cells and it reads as "画进图里/遮挡内容" no matter how the offset is tuned. Give side annotations (family color strips, per-group strength bars) a dedicated narrow axes with `set_ylim` matching the heatmap rows and ticks/spines off; the physical axes separation IS the guarantee of non-overlap. Side bars drawn in axes-fraction x (blended transform, x≈0.01) fail the same way — that lands INSIDE the heatmap data area, on the first column.
- **Gridspec wspace is uniform — for independent per-gap control use explicit `fig.add_axes([l, b, w, h])`** — when one gap must be near-zero (side bar column hugging the heatmap edge, user: "紧贴,不要空隙") while another must stay wide (previous panel to the labels), a shared wspace cannot satisfy both; set the bar column's right coordinate equal to the heatmap's left coordinate for true zero-gap adjacency, and give y tick labels breathing room via `tick_params(axis="y", pad=2.5)` instead of axes gaps.
- **Panel scope changes must update coverage AND the title** — when panels merge (e.g. drop a standalone bar panel and move its family into the shared heatmap), re-add the previously excluded rows to the data filter, verify per-group rendered row counts against the source tables before answering "有没有缺漏", and fix the panel title if the old scope word ("Non-homolog") no longer matches the content — a stale title is caught immediately.
- **Unbounded color values also break side strips keyed to the same colormap** — any family-mean strip colored via the same Normalize must apply the same `np.clip(vmin, vmax)` before mapping, or its extreme families render mid-colormap colors and misread the glance scale.
- **Verify file edits actually landed before rendering/reporting** — an edit script that does `src.replace(...)` then `assert old2 in src` then `write` aborts BEFORE the write when the second match fails, leaving ALL old content in place while the session moves on and reports a fix the file never contained (user: "标注并没有被删除"). Structure batched edits as all-asserts-first then one write, and after every edit grep the file for the new text before rendering or claiming success.
- **Check the render before answering when a fix was contested** — after repeated layout complaints, a vision pass on the saved PNG (gap sizes, presence/absence of the contested element, per-group row counts) is part of the fix, not an optional extra; reporting an unverified layout re-escalates the same complaint.
- **An 'n.e.' cell means the background window has zero reads in the RNA-seq BAM — verify against the right BAM before doubting it** — RNA-seq BAMs live under `output/iteration/RNAseq/common/11_featureCounts_bam/<ref>/<sample>_<rep>.bam`; the PacVar `common/{1_raw_data,2_sorted_bam,3_markdup_bam}` BAMs are WGS/PacBio and always have coverage, so counting reads there 'disproves' flank_empty falsely. Re-count with the same MAPQ/dedup filters in the RNA BAM before changing any n.e. rendering.
- **Annotate exact values in cells when a colorbar also exists** — small matrices with `f"{ratio:.1f}x"` text per cell (white text when |norm| > 0.47, else dark) make the colorbar a redundant glance-scale, which is what lets side strips/summary bars reuse its colormap without ambiguity.
- **Clip for COLOR, annotate with TRUE values** — `imshow(np.clip(mat, vmin, vmax))` fixes cell color, but cell text computed from the clipped matrix renders beyond-scale values wrong (243.8x shows as 8.0x = 2^3). Keep the matrix unclipped; clip only at the imshow call and at any side-strip colormap mapping; cell annotations display the real ratio.
- **One function owns each axes' tick/label state** — when a figure splits into multiple functions sharing axes (heatmap fn + side-bar fn), a leftover `set_yticks([])` "reset" in one function silently erases the labels the other set, whenever call order puts it last (user: "y轴刻度标签被你弄消失了"). Assign tick/label ownership exclusively (bar fn: x ticks + spines only; heatmap fn: y labels) and note the ownership in comments at the touched lines.
- **Calibrate quality thresholds from the metric's actual distribution** — an a-priori cutoff (background exonic kb < 20) flagged 55/66 windows low_conf because gene-sparse flanks have little exonic sequence by nature; inspect the distribution first and set the cutoff where the noise argument actually bites (here 5 kb), or the flag swamps the data and the figure is unusable.
- **Refactor plot scripts to explicit CLIs when generalizing** — replace hard-coded sample/id dicts with CLI inputs: `--sample-map "PREFIX=Name,..."` (order defines column order) and external assignment TSVs (`--family-tsv` with sample/circ_id/family columns); validate inputs with clear errors (dir missing, no matching files, missing columns) instead of failing deep inside plotting; write the assignment TSV once from the upstream source (e.g. expand a families TSV's members column) and commit it as an input.
- **RNA-seq interval ratios must be exon-normalized** — RNA-seq signal only lands on exons, so interval-RPK ratios conflate transcription with exon density (measured: fragments 0-14.4% exonic vs flank windows 1.0-10.9%, a 10x structural bias; a family's 'activity' collapsed 6-8x -> 0.3-2.5x after normalization). Denominators = merged-GENCODE-exon intersection lengths on BOTH sides; zero-intersection sides flag no_exonic (non-coding circle content, itself a result). Before trusting any interval-based expression ratio, quantify the density confound first.

### Align a standalone re-plot script with the canonical module plot style

When a one-off re-plot script under `output/**/corrected/` must match the plotting style of the canonical module script (e.g. `workflow/Omics/modules/function/bin/gsva.py::plot_heatmap`), port the plotting body VERBATIM (row_scale, textwrap widths, constrained_layout, symmetric vmax, white minor-grid separators, interpolation="nearest", figure sizing from longest label) rather than restyling by hand — partial ports are how style drifts apart again. Keep the domain-specific data surgery (sample exclusion, renaming, column ordering) in a separate `load_scores()` function so the plot function stays a verbatim copy. Two further rules:

- **Exclude-before-rename ordering still applies** — the re-plot keeps the original exclude/rename logic; see §9 for the collision pitfall.
- **LogUtil is not importable from output/ scripts** — standalone scripts outside the workflow tree cannot `from LogUtil import setup_logger`; insert the canonical bin dir first: `sys.path.insert(0, "<repo>/workflow/Omics/modules/function/bin")`, then import and `logger = setup_logger(__name__)`. Replace `print()` with `logger.info` to match module style.

### Verify a plotting edit without rerunning the pipeline

Plot functions take a DataFrame — feed them the TSV the pipeline already wrote (`<outdir>/*.tsv`, `index_col=0`) and render for visual inspection, instead of rerunning the Snakemake rule. Find an interpreter with the deps via `conda env list`; any env with pandas+matplotlib works since the function only needs the matrix (this project: the `DNA` env has pandas+matplotlib/numpy; the project `.venv` does not). After saving, inspect the PNG with vision — layout bugs (squeezed heatmaps, detached colorbars) pass code review but fail on canvas.

### Test renders use real project data

- Exercise new plot scripts with real project data (existing tables, BAMs, annotations), not simulated fixtures — a simulated-value figure proves layout only. Do not spin up new heavy analyses (new DE pipelines, new quantifications) to manufacture test inputs; the project's existing outputs usually already cover every input contract, and the user will ask why real data wasn't used.
- If a required input genuinely does not exist yet, state the exact missing artifact in one line and stop there — do not fabricate a substitute and do not build the missing analysis unasked.
- Report tersely: deliverable paths + what was verified + open items in one short block. No process replay, no re-summarizing decisions the user already made. When given full authority, run to completion and fix failures in place instead of asking.
