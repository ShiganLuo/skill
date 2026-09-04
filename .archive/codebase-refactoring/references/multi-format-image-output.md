# Multi-Format Image Output Pattern

Reusable pattern for adding configurable image format output to matplotlib-based pipelines.

## Module-Level Type Alias

```python
from typing import Literal, List, Optional
PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]
```

Use the SAME alias name (`PlotFormat`) across all files in the project — don't call it `ImageFormat` in one file and `PlotFormat` in another.

## Function Signature

```python
def run_analysis(
    data: pd.DataFrame,
    out_dir: str,
    plot_formats: Optional[List[PlotFormat]] = None,
) -> None:
    """
    Docstring MUST come before the if-check.
    """
    if plot_formats is None:
        plot_formats = ["png"]
    ...
```

**CRITICAL**: Docstring goes FIRST, then `if plot_formats is None`. Python treats the first string literal after `def` as the docstring — if the if-check comes first, the docstring is lost.

**WRONG**:
```python
def run_analysis(plot_formats: Optional[List[PlotFormat]] = None):
    if plot_formats is None:
        plot_formats = ["png"]
    """Docstring after if-check — this is NOT a docstring, just a dangling string."""
```

## Multi-Format Save Loop

```python
# Pattern A: each plot function called once per format
for fmt in plot_formats:
    plot_sv_type_barplot(
        summary_df=type_summary,
        outpng=f"{out_dir}/plot/sv_type_barplot.{fmt}",
        xlabel="SV type",
        ylabel="SV count",
    )

# Pattern B: savefig loop inside a plot function
out_prefix = os.path.splitext(out_png)[0]
for fmt in image_formats:
    plt.savefig(f"{out_prefix}.{fmt}", dpi=dpi)
plt.close()
```

## CLI Argument (argparse)

Unified style for ALL scripts in a project:

```python
parser.add_argument(
    "-f", "--format",
    action="append",
    dest="formats",
    metavar="FMT",
    help="Image output format (png, pdf, svg, ...). Can be specified multiple times. Default: png.",
)

# Pass through
run_analysis(data=data, out_dir=args.outdir, plot_formats=args.formats)
```

Usage:
```bash
python script.py -g C:ctrl.vcf -g E:exp.vcf -f png -f pdf -f svg
```

**DO NOT** use `--image_formats nargs="+"` in one script and `-f/--format action="append"` in another. Pick one style and use it everywhere.

## Propagation Checklist

When adding `plot_formats` / `image_format` to a top-level function:

1. [ ] Top-level function has the parameter with `Literal` type constraint
2. [ ] All same-directory plot functions receive it
3. [ ] All subdirectory plot functions (e.g., `enricher/function.py`) receive it
4. [ ] CLI `argparse` has `-f/--format` with `action="append"`
5. [ ] Default fallback (`["png"]`) at the point of use, not in argparse
6. [ ] Same alias name used across all files

## Batch Consistency Refactoring Workflow

When unifying typing/CLI across multiple scripts:

1. Read ALL files first to audit current state
2. Create a comparison table of inconsistencies
3. Fix in order: imports → type aliases → function signatures → function bodies → CLI args → callers
4. Verify with `ast.parse()` after each file
5. Check that docstring placement is correct (before if-check, after def)
