# Omics `src/` Package Structure & Import Patterns

The Omics project's Python source lives under `workflow/Omics/src/`. Scripts in
`src/download/`, `src/count/`, `modules/*/bin/`, `src/common/ml/`, etc. need to
import shared utilities from `src/common/util/` (e.g. `SepUtil.py`, `LogUtil.py`,
`CmdUtil.py`, `MatchUtil.py`).

## Canonical import style (MUST FOLLOW)

All scripts MUST use `from src.common.util.<Module> import <Symbol>` and MUST
add the **Omics project root** (not `src/`) to `sys.path`:

```python
import sys
from pathlib import Path

# _PROJECT_ROOT = workflow/Omics/ (parent of src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # adjust depth per file location
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.common.util.LogUtil import setup_logger
from src.common.util.SepUtil import detect_delimiter
from src.common.util.CmdUtil import _run_cmd
```

This is the ONLY correct pattern. The older `from common.util.*` and
`from common.X` styles are deprecated and were removed in a project-wide
cleanup (August 2026).

## Why `src.common.util.*` (not `common.util.*`)

- `run.py` (the main entry point) uses `from src.common.util.*` -- all scripts
  must match for consistency.
- `from common.util.*` requires `src/` on `sys.path`, while `from src.common.util.*`
  requires the **Omics root** on `sys.path`. The Omics root is the natural
  anchor point since it's the directory containing `run.py`, `src/`, `modules/`,
  and `subworkflow/`.
- `from common.CmdUtil import _run_cmd` was a common bug -- it skipped the
  `.util.` segment entirely, resolving to a nonexistent `common/CmdUtil.py`.

## sys.path depth cheat sheet

The `__file__`-relative dirname depth needed to reach the Omics root varies by
file location. Count carefully -- off-by-one is the #1 cause of broken imports:

| File location | dirname depth to Omics root |
|---|---|
| `src/download/*.py` | 3 (`parent.parent.parent`) |
| `src/common/ml/MSI/data/*.py` | 6 |
| `src/common/ml/MSI/other/msisensor-pro/*.py` | 7 |
| `src/common/ml/Semi-Supervised/sv/*.py` | 6 |
| `src/common/ml/Semi-Supervised/sv/sv_freq_correction/*.py` | 7 |
| `modules/sv/bin/*.py` | 4 |
| `modules/sv/bin/utils/*.py` | 5 |
| `modules/arriba/bin/*.py` | 4 |

For files using a named variable (e.g. `_SRC_DIR`, `SCRIPT_DIR`, `ROOT_DIR`),
compute the Omics root, not `src/`:

```python
# CORRECT for src/download/ files (depth 3):
_SRC_DIR = Path(__file__).resolve().parent.parent.parent  # Omics root

# WRONG (old pattern, resolves to src/):
# _SRC_DIR = Path(__file__).resolve().parent.parent  # src/ -- too shallow
```

## Directory layout

```
workflow/Omics/
├── run.py                    # main entry point, uses src.common.util.*
├── src/
│   ├── __init__.py           # empty (makes src/ a package)
│   ├── common/
│   │   ├── (no __init__.py)  # PEP 420 namespace package
│   │   ├── util/
│   │   │   ├── __init__.py   # re-exports via relative imports
│   │   │   ├── CmdUtil.py
│   │   │   ├── EnvUtil.py
│   │   │   ├── LogUtil.py
│   │   │   ├── MatchUtil.py
│   │   │   ├── MetaUtil.py
│   │   │   ├── SchemaValidatorUtil.py
│   │   │   ├── SepUtil.py
│   │   │   ├── SmkUtil.py
│   │   │   └── type.py
│   │   └── ml/               # ML scripts (MSI, Semi-Supervised)
│   ├── download/             # SRA/ENA/GSM download scripts
│   └── count/
├── modules/
│   ├── sv/bin/               # SV analysis scripts
│   ├── sv/bin/utils/         # SV utility scripts
│   ├── arriba/bin/           # Fusion detection scripts
│   └── common/               # Shared Snakemake includes (common.smk)
└── subworkflow/              # Subworkflow .smk files
```

## How scripts are invoked

Snakemake `.smk` files invoke scripts via `python` in `run:` blocks:

```python
cmd = ["python", params.script, "-c", input.control_vcf, ...]
with open(script_path, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(cmd) + "\n")
shell(f"bash {script_path} >> {log_path} 2>&1")
```

Key implications:
- `ROOT_DIR` (Omics root) is passed via Snakemake config, not env vars
- `cwd` during execution is the **output directory**, NOT the Omics root
- Python's `sys.path[0]` is the **script's own directory**, NOT cwd
- Therefore, explicit `sys.path` manipulation in each script is REQUIRED
- `PYTHONPATH` is NOT set by Snakemake or the shell wrappers

## `__init__.py` rules

1. `src/common/util/__init__.py` must use **explicit relative imports**:
   ```python
   from .SepUtil import detect_delimiter  # CORRECT
   __all__ = ["detect_delimiter"]
   ```
   NOT `from SepUtil import detect_delimiter` (absolute -- fails).

2. `src/common/` has NO `__init__.py` -- intentional PEP 420 namespace package.
   Do NOT add one.

3. `src/__init__.py` is empty -- marks `src/` as a package so `from src.common...` works.

## Audit: finding wrong import patterns

Search for any imports NOT using `src.common.util.*`:

```bash
# Find deprecated common.util.* or common.X imports (all are wrong now)
grep -rn "from common\.\(util\.\)\?\(CmdUtil\|EnvUtil\|LogUtil\|MatchUtil\|MetaUtil\|SchemaValidatorUtil\|SepUtil\|SmkUtil\|type\)" --include="*.py" .
```

Any match is a file that needs to be updated to `from src.common.util.*`.

## Common pitfalls

- **Off-by-one dirname depth**: The #1 error. Always verify the resolved path
  contains `src/common/util/` before writing the import. A quick check:
  ```python
  assert (_PROJECT_ROOT / "src" / "common" / "util").is_dir(), f"Wrong root: {_PROJECT_ROOT}"
  ```

- **`from common.X` missing `.util.`**: `from common.CmdUtil import _run_cmd`
  skips the `util` package segment. Must be `from src.common.util.CmdUtil import _run_cmd`.

- **Duplicate imports**: `ftp_download.py` had `from common.util.LogUtil import setup_logger`
  twice (lines 6 and 9). Always check for and remove duplicates during cleanup.

- **Local sibling imports still work**: Scripts in `modules/sv/bin/` that import
  `from utils.VEP_SV import ...` or `from enricher.function import ...` work
  because Python auto-adds the script's own directory to `sys.path[0]`. Changing
  the sys.path to point to Omics root does NOT break these -- they coexist.

- **`run.py` is the reference**: `run.py` at the Omics root uses
  `from src.common.util.*` without any sys.path manipulation (because it's
  already at the root). All other scripts should match this import style.
