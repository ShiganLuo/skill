---
name: codebase-management
description: "Inspect, analyze, and refactor codebases — LOC metrics, language breakdown, code quality review, file renaming, import updates, and restructuring workflows."
tags: [codebase, refactoring, LOC, pygount, code-quality, snake_case, restructuring]
triggers:
  - "How big is this repo"
  - "What languages does this project use"
  - "Review this code"
  - "Refactor this project"
  - "Rename files to follow conventions"
  - "Restructure the project"
  - "Clean up the codebase"
  - "Apply software engineering best practices"
  - "Add type constraints"
  - "Validate function parameters"
---

# Codebase Management

Class-level skill for inspecting, analyzing, and restructuring codebases. Covers metrics/analysis (LOC, language breakdown) and refactoring workflows (code quality, file renaming, import updates).

---

## Section A: Codebase Inspection with pygount

Analyze repositories for lines of code, language breakdown, file counts, and code-vs-comment ratios using `pygount`.

### When to Use

- User asks for LOC (lines of code) count
- User wants a language breakdown of a repo
- User asks about codebase size or composition
- User wants code-vs-comment ratios
- General "how big is this repo" questions

### Prerequisites

```bash
pip install --break-system-packages pygount 2>/dev/null || pip install pygount
```

### Basic Summary (Most Common)

Get a full language breakdown with file counts, code lines, and comment lines:

```bash
cd /path/to/repo
pygount --format=summary \
  --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,.cache,dist,build,.next,.tox,.eggs,*.egg-info" \
  .
```

**IMPORTANT:** Always use `--folders-to-skip` to exclude dependency/build directories, otherwise pygount will crawl them and take a very long time or hang.

### Common Folder Exclusions

Adjust based on the project type:

```bash
# Python projects
--folders-to-skip=".git,venv,.venv,__pycache__,.cache,dist,build,.tox,.eggs,.mypy_cache"

# JavaScript/TypeScript projects
--folders-to-skip=".git,node_modules,dist,build,.next,.cache,.turbo,coverage"

# General catch-all
--folders-to-skip=".git,node_modules,venv,.venv,__pycache__,.cache,dist,build,.next,.tox,vendor,third_party"
```

### Filter by Specific Language

```bash
# Only count Python files
pygount --suffix=py --format=summary .

# Only count Python and YAML
pygount --suffix=py,yaml,yml --format=summary .
```

### Output Formats

```bash
# Summary table (default recommendation)
pygount --format=summary .

# JSON output for programmatic use
pygount --format=json .
```

### Interpreting Results

The summary table columns:
- **Language** — detected programming language
- **Files** — number of files of that language
- **Code** — lines of actual code (executable/declarative)
- **Comment** — lines that are comments or documentation
- **%** — percentage of total

Special pseudo-languages: `__empty__`, `__binary__`, `__generated__`, `__duplicate__`, `__unknown__`

### Pitfalls

1. **Always exclude .git, node_modules, venv** — without `--folders-to-skip`, pygount will crawl everything and may take minutes or hang on large dependency trees.
2. **Markdown shows 0 code lines** — pygount classifies all Markdown content as comments, not code. This is expected behavior.
3. **JSON files show low code counts** — pygount may count JSON lines conservatively. For accurate JSON line counts, use `wc -l` directly.
4. **Large monorepos** — for very large repos, consider using `--suffix` to target specific languages rather than scanning everything.

---

## Section B: Codebase Refactoring

Workflow for reviewing, refactoring, and restructuring Python projects following software engineering best practices.

### User Style Preferences (MUST FOLLOW)

- **Docstrings**: Always English, never Chinese. Use **NumPy style** (see `references/numpy-docstring-template.md` for the exact format). For R scripts, use roxygen2 style (`#' @param`, `#' @return`).
- **Logging format**: Use f-strings (`logger.info(f"Processing: {name}")`), NOT `%s` style (`logger.info("Processing: %s", name)`)
- **File naming**: snake_case with descriptive names reflecting functionality
- **Type hints**: Use modern syntax with `from __future__ import annotations`
- **Relationship modeling**: Prefer explicit one-to-many modeling when the user states it; do not introduce many-to-many sample/file links unless the user explicitly allows them.

### Phase 1: Code Quality Review

When user asks "how is this code" or requests a review:

1. Scan the project structure (`search_files` target=files)
2. Read key files to understand functionality
3. Evaluate against these criteria:
   - Docstrings and documentation quality
   - Type hints usage
   - Error handling robustness
   - Code duplication
   - Hardcoded paths
   - Mutable default arguments
   - Naming conventions (snake_case for files/vars, PascalCase for classes)
   - Import organization

### Phase 2: Refactoring a Single File

When refactoring a specific file:

1. Read the entire file first
2. Identify issues:
   - Hardcoded paths → convert to CLI args or config
   - Mutable defaults (e.g., `def f(x=[])`) → use `None` with initialization
   - Code duplication → extract common functions
   - Poor naming → rename to descriptive snake_case
   - Missing type hints → add them
   - Mixed language comments → standardize to English
3. Write the refactored version preserving all original functionality
4. Use `write_file` to create new version (keep old for comparison)

### Phase 3: Project-Wide File Renaming

When renaming files across a project:

#### Step 1: Inventory and Plan

Create renaming plan with old → new mapping. Group by directory for batch operations.

#### Step 2: Create New Directories

```bash
mkdir -p new_dir1 new_dir2
```

#### Step 3: Use `git mv` for Each File

```bash
git mv old/path/file.py new/path/file_name.py
```

**Critical**: Always use `git mv` not plain `mv` to preserve git history.

#### Step 4: Update All Import References

Search for all imports referencing old module names:
```bash
grep -r "old_module_name" --include="*.py" .
```

Use `execute_code` with `patch` tool for batch import updates:
```python
from hermes_tools import patch
files = ["file1.py", "file2.py"]
for f in files:
    patch(f, "from old.module import", "from new.module import")
```

#### Step 5: Clean Up

- Remove `__pycache__` directories
- Remove empty directories
- Verify with `git status`

#### Step 6: Commit and Push

```bash
git add -A
git commit -m "refactor: descriptive commit message listing all changes"
git push
```

### Common Renaming Patterns

| Current (Bad)              | Target (Good)                |
|---------------------------|------------------------------|
| `LogUtil.py`              | `logger.py`                  |
| `MatchUtil.py`            | `sample_matcher.py`          |
| `chipevalute_interval.py` | `chip_evaluator.py`          |
| `stanard_pipeline.py`     | `pipeline.py` (fix typos)    |
| `result_plot.py`          | `validation_plots.py`        |
| `depth.py`                | `sensitivity.py`             |
| `run.py`                  | `run_simulation.py`          |
| `HD/`                     | `hrd/`                       |
| `task/`                   | `workflow/`                  |
| `assests/`                | `assets/`                    |

### Directory Naming Conventions

- Use lowercase with underscores: `bed_formatting/`, `frequency_correction/`
- Abbreviations should be lowercase: `hrd/` not `HD/`
- Names should describe content: `workflow/` not `task/`

### Single-File Refactoring Checklist

When refactoring an individual Python script, address these in order:

1. **Remove hardcoded values** — file paths → CLI args or config; magic numbers → named constants; column names → constants
2. **Fix mutable default arguments** — `def f(x=[])` → `def f(x=None): x = x or []`
3. **Merge duplicate functions** — if two functions share >50% logic, extract common helpers
4. **Use pathlib consistently** — `Path(dir) / filename` not `os.path.join`
5. **Add module/script docstring** with usage example
6. **Add constants at top** — `DEFAULT_SUFFIX`, `MAX_RETRIES`, etc.
7. **Improve type hints** — use specific types (`List[Path]`, `Dict[str, pd.DataFrame]`) not `Any`
8. **Improve error handling** — check file existence, validate inputs early, use specific exceptions

### Naming Conventions (Detailed)

| Element    | Pattern              | Good example                | Bad example           |
|------------|----------------------|-----------------------------|-----------------------|
| File       | `<action>_<object>`  | `aggregate_depth_stats.py`  | `stat_xishu.py`       |
| Function   | `verb_noun`          | `normalize_dep_factor()`    | `normalize()`         |
| Variable   | descriptive          | `dep_factor_series`         | `dfs`                 |
| Class      | PascalCase           | `SampleMatcher`             | `sample_matcher`      |

### Quality Checks (Pre-Commit)

- [ ] All docstrings in English
- [ ] No hardcoded paths/numbers
- [ ] No mutable defaults
- [ ] Consistent pathlib usage
- [ ] Clear file/function/variable names
- [ ] Type hints on public functions
- [ ] Error handling with context
- [ ] Script runnable without path edits (paths are args or config)

### Type-Level Constraints (Literal, Enum)

**User preference (MUST follow)**: put constraints directly on function parameter definitions, NOT as runtime `if/raise` blocks in the function body. The type signature IS the contract.

```python
# CORRECT: constraint on the parameter
PlotFormat = Literal["png", "pdf", "svg", "ps", "eps", "tif", "tiff", "jpg", "jpeg", "pgf", "raw", "rgba"]

def generate_plot(
    data: pd.DataFrame,
    out_path: str,
    fmt: PlotFormat = "png",
) -> None:
    ...

# WRONG: constraint hidden in function body
def generate_plot(data, out_path, fmt="png"):
    valid = {"png", "pdf", "svg", "ps", "eps", "tif", "tiff"}
    if fmt not in valid:
        raise ValueError(f"Unsupported format '{fmt}'")
    ...
```

### Propagation Pattern

When adding a constrained parameter to a top-level function, trace the **entire call chain** and propagate it to every downstream function — including modules in subdirectories. A format parameter on `run_analysis()` is useless if `plot_bar()` downstream still hardcodes `.png`.

See `references/multi-format-image-output.md` for a complete worked example with CLI integration and savefig patterns.

See `references/batch-cli-typing-unification.md` for unifying CLI args and typing across multiple scripts in a project.

See `references/download-data-management.md` for one-to-many sample/file modeling and download registry conventions.

```
run_analysis(fmt: PlotFormat)        # top-level
  ├── plot_bar(outpng, fmt)          # same directory
  ├── plot_boxplot(outpng, fmt)      # same directory
  └── enrich_go(gene_list, fmt)      # subdirectory/enricher.py  ← DON'T FORGET
```

Batch consistency rule: when the same constrained parameter is added to multiple files, use the **same type alias name** (e.g., `PlotFormat`) across all files — don't call it `ImageFormat` in one file and `PlotFormat` in another.

### Rules

- Define `Literal` or `Enum` aliases at module level for reuse across functions
- Use `Optional[List[PlotFormat]]` for list parameters with item-level constraints
- CLI argparse `choices=` should mirror the same set for end-user validation
- Keep runtime validation only when the valid set is truly dynamic (e.g., loaded from config)
- When propagating through call chains, downstream functions use `str` (not the Literal) if they're in a different module — the Literal is the caller's contract, not the callee's

### Docstring Conventions

See `references/numpy-docstring-template.md` for the full NumPy docstring format, minimal examples, class method conventions, R roxygen2 style, and the placement rule (docstring must come BEFORE `if x is None` body init).

### Pitfalls

- **Forgetting to update imports**: Always grep for old module names after renaming
- **Using `mv` instead of `git mv`**: Loses git history
- **Not cleaning `__pycache__`**: Can cause confusion with stale bytecode
- **Renaming without understanding dependencies**: Check for hardcoded script paths in shell scripts and argparse defaults
- **Committing too much at once**: Keep refactoring commits separate from feature changes
- **Incomplete propagation of new parameters**: When adding a parameter (e.g., `image_format`) to a top-level function, always trace through the full call graph — including functions in subdirectory modules — and update every downstream callee. Missed propagation leaves hardcoded values in leaf functions.
- **Docstring placement with None-default initialization**: When converting mutable defaults to `Optional[T] = None` + body init, the docstring MUST come BEFORE the `if x is None` check. Python treats the first string literal after `def` as the docstring — placing the if-check first makes it unreachable and the docstring lost.
- **Inconsistent CLI arg style across project scripts**: When multiple scripts in a project accept the same kind of parameter (e.g., image formats), unify the argparse definition: same short flag (`-f`), same long flag (`--format`), same `action="append"`, same `dest="formats"`, same help text. Don't use `--image_formats nargs="+"` in one script and `-f/--format action="append"` in another.
- **Bare `list`/`dict` in function signatures**: Always use `typing.List[str]`, `typing.Dict[str, str]`, etc. Bare `list` loses item-level type information. When the parameter is optional, use `Optional[List[PlotFormat]]` not `list = None`.
- **Over-generalizing a user-reviewed design before implementation**: If the user narrows a domain rule (for example, 'sample to file is one-to-many, never many-to-many'), encode that invariant directly into the implementation plan, schema, and naming logic before adding generic exception tables. Do not keep speculative flexibility that the user explicitly ruled out.
- **Unsafe first test on existing data-management code**: When introducing file-management scripts (rename/store/register/dedupe), first test with read-only actions or writes confined to a temporary destination. Explicitly separate non-mutating commands (`scan`, `identify`, `register`) from mutating ones (`store`, `move`, rename-on-copy), and explain the risk boundary before running anything against user data.
- **Using opaque IDs too early for review-heavy workflows**: Hash-derived IDs are technically stable but hard for users to audit. When the user is reviewing data-management naming schemes, prefer a human-auditable numbering strategy unless the user explicitly accepts opaque IDs.
