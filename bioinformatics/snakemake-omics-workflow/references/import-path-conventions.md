# Import Path Conventions for Omics Python Scripts

## The Unified Rule

All Python scripts in the Omics project that reference `src/common/util/` modules
must use:

```python
from src.common.util.<Module> import <symbol>
```

This requires the **Omics root directory** (the dir containing `run.py`, `src/`,
`modules/`, `subworkflow/`) to be in `sys.path`.

## Why `src.common.util.*` (not `common.util.*`)

- `run.py` (the main entry point) uses `from src.common.util.*` — it sets the
  standard.
- `src/` has `__init__.py`, `src/common/util/` has `__init__.py`, but
  `src/common/` does NOT (namespace package). This works fine in Python 3.
- `from common.util.*` requires `src/` in sys.path (so Python finds
  `common/util/` under `src/`). This is fragile and inconsistent with `run.py`.
- `from common.X` (without `.util.`) is always wrong — the modules live under
  `common/util/`, not directly under `common/`.

## sys.path Depth Cheat Sheet

Each script must add the Omics root to sys.path via `os.path.dirname()` nesting.
The depth depends on the script's location relative to the Omics root:

| Script location                          | dirname depth | Example                                              |
|------------------------------------------|---------------|------------------------------------------------------|
| `modules/<mod>/bin/*.py`                 | x4            | bin → mod → modules → Omics                          |
| `modules/<mod>/bin/utils/*.py`           | x5            | utils → bin → mod → modules → Omics                  |
| `modules/arriba/bin/summarize_*.py`      | x4 (ROOT_DIR) | Uses `ROOT_DIR = dirname x4`, then `sys.path.append(ROOT_DIR)` |
| `src/common/ml/MSI/data/*.py`            | x6            | data → MSI → ml → common → src → Omics               |
| `src/common/ml/MSI/other/*/run_msi.py`   | x7            | run_msi → msisensor-pro → other → MSI → ml → common → src → Omics |
| `src/common/ml/Semi-Supervised/sv/*.py`  | x6            | sv → Semi-Supervised → ml → common → src → Omics     |
| `src/common/ml/Semi-Supervised/sv/*/features.py` | x7     | features → sv_freq_correction → sv → Semi-Sup → ml → common → src → Omics |
| `src/download/*.py`                      | x3            | download → src → Omics                               |

### Verification formula

```python
# After computing the sys.path target:
import os
omics_root = os.path.dirname(os.path.dirname(os.path.dirname(...)))  # adjust depth
assert os.path.isdir(os.path.join(omics_root, "src", "common", "util"))
```

## Common patterns by location

### modules/sv/bin/*.py (and similar module bin scripts)

```python
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from src.common.util.LogUtil import setup_logger
```

### modules/sv/bin/utils/*.py (one level deeper)

```python
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
from src.common.util.LogUtil import setup_logger
```

### modules/arriba/bin/summarize_arriba_fusions.py (uses ROOT_DIR variable)

```python
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from src.common.util.LogUtil import setup_logger
```

### src/download/*.py (or uses _SRC_DIR = parent.parent.parent)

```python
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.common.util.SepUtil import detect_delimiter
```

Or with Path:
```python
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_SRC_DIR))
from src.common.util.SepUtil import detect_delimiter
```

## Local sibling imports are unaffected

Scripts in `modules/sv/bin/` that import `from utils.VEP_SV import VEP_SV` still
work because Python automatically adds the script's own directory to
`sys.path[0]`. The sys.path change for `src.common.util.*` only adds the Omics
root — it does not remove the script directory.

## Git submodule: src/common/ml

`src/common/ml` is a git submodule pointing to `github.com:ShiganLuo/ML.git`.
When modifying files under it:
1. Commit and push within the submodule first
2. Then commit the updated submodule reference in the parent (Omics) repo
3. Push the parent repo

## How scripts are invoked

Snakemake `.smk` rules invoke scripts via:
```python
cmd = ["python", params.script, "-arg", value, ...]
# Written to a .sh file, then: shell(f"bash {script} >> {log} 2>&1")
```

- cwd = snakemake's working directory (the output dir, NOT Omics root)
- sys.path[0] = the script's own directory (Python default)
- No PYTHONPATH is set by snakemake or the .smk rules
- Therefore, the ONLY way imports work is via explicit `sys.path` manipulation
  inside each script

## Pitfalls

- **Wrong dirname depth**: The most common bug. A script at
  `modules/sv/bin/utils/SV_TYPE.py` needs x5 dirname to reach Omics root, but
  was using x3 (pointing to `modules/sv/` which has no `src/`).
  Always verify: `os.path.isdir(os.path.join(target, "src", "common", "util"))`.
- **`from common.X` without `.util.`**: Modules like `CmdUtil`, `MatchUtil` live
  under `common/util/`, not directly under `common/`. The import must be
  `from src.common.util.CmdUtil import _run_cmd`.
- **Duplicate imports**: `ftp_download.py` had `from common.util.LogUtil import
  setup_logger` twice. Always deduplicate when refactoring imports.
- **Forgetting the submodule**: Changes under `src/common/ml/` must be pushed to
  the ML repo separately before the parent Omics repo can reference the new
  commit.
