# Batch CLI & Typing Unification Across Multiple Scripts

When a project has multiple Python scripts that evolved independently, their CLI arguments and function signatures drift apart. This reference documents the systematic approach to unify them.

## Audit Phase

Read all scripts and build an inconsistency table:

| File | CLI style | Function param type | Alias name |
|------|-----------|-------------------|------------|
| script_a.py | `-f/--format action="append"` | `Optional[List[PlotFormat]]` | `PlotFormat` |
| script_b.py | `--image_formats nargs="+"` | `Union[PlotFormat, List[PlotFormat]]` | `ImageFormat` |
| script_c.py | (none) | `list = None` | (none) |
| sub/mod.py | (none) | `list = None` | (none) |

## Fix Order

1. **Imports & aliases** — add `from typing import List, Literal, Optional`, define `PlotFormat` at module level
2. **Function signatures** — replace bare `list` with `Optional[List[PlotFormat]]`, replace `Union[X, List[X]]` with `Optional[List[X]]`
3. **Docstring placement** — ensure docstring is BEFORE any `if x is None` body init
4. **Function bodies** — add `if x is None: x = [default]` AFTER docstring
5. **CLI arguments** — unify to `-f/--format action="append" dest="formats"`
6. **Callers** — pass `args.formats` (or whatever `dest=`) to function

## Common Drift Patterns

| Drift | Fix |
|-------|-----|
| `Union[PlotFormat, List[PlotFormat]]` | `Optional[List[PlotFormat]]` — simpler, always list |
| `list = None` (bare) | `Optional[List[PlotFormat]] = None` |
| `Dict` (bare) | `Dict[str, str]` |
| `choices=["png","pdf"]` in argparse | Remove choices, let Literal type handle constraint |
| `--param nargs="+"` | `-f/--format action="append" dest="formats"` |

## Verification

After each file edit:
```python
import ast
ast.parse(open("file.py").read())  # Syntax check
```

After all files done, grep for any remaining bare `list` or `dict` in function signatures:
```bash
grep -n ":\s*list\b\|:\s*dict\b" *.py **/*.py
```
