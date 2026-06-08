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
