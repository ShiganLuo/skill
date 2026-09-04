# Common.smk Pattern — Implementation Reference

## Problem

Multiple modules need the same utility (e.g., `setup_logger` from `src/common/LogUtil.py`).
Each module had duplicate boilerplate:

```python
import sys
import os
ROOT_DIR = config.get("ROOT_DIR", ".")
src_dir = os.path.join(ROOT_DIR, "src")
sys.path.insert(0, src_dir)
from common.LogUtil import setup_logger
import time
import shutil
```

This fails because `module` + `use rule` loads modules at parse time (§30).

## Solution: `modules/common/common.smk`

### File structure

```
modules/common/
├── common.smk         # shared utilities (include-able)
├── README.md          # usage docs
├── MIGRATION_GUIDE.md # how to migrate existing modules
└── SUMMARY.md         # implementation summary
```

### common.smk (see `templates/common_smk.snippet`)

- Imports standard library: `sys`, `os`, `time`, `shutil`
- Gets `ROOT_DIR` from config
- Adds `ROOT_DIR/src` to `sys.path`
- Imports `setup_logger` from `common.LogUtil`
- Provides `create_logger()` helper

### Usage

**In subworkflow** (top of file):
```python
include: "../modules/common/common.smk"
```

**In module** (top of file):
```python
include: "../common/common.smk"
```

Then in `run:` blocks:
```python
run:
    open(log, "w").close()
    logger = setup_logger(logger_name="rule_name", log_file=log)
    try:
        logger.info(f"Processing {wildcards.sample_id}")
        # ...
    except Exception as e:
        logger.error(f"Failed: {e}")
        raise e
```

### Critical: include does NOT propagate

`include:` in a subworkflow does NOT make the included code available to modules
loaded via `module` + `use rule`. Each module must include common.smk independently.

```
subworkflow/PacVar.smk
  include: "../modules/common/common.smk"   ← only for PacVar.smk itself
  
  module centromere:
      snakefile: "../modules/centromere/centromere.smk"
      # centromere.smk does NOT get setup_logger from this include
```

So `centromere.smk` must also have `include: "../common/common.smk"`.

### Migration pattern

For existing modules with top-level imports:

1. Remove duplicate boilerplate (`import sys/os`, `sys.path.insert`, `from common.LogUtil import`)
2. Add `include: "../common/common.smk"` at top
3. Remove top-level `logger = setup_logger(__name__)`
4. Keep `setup_logger` calls in `run:` blocks (they still work)

### vs PYTHONPATH approach (Option A)

PYTHONPATH in run.py is simpler for subprocess execution (§31 Option A), but
common.smk is better for:
- Read-only run.py (can't modify it)
- Explicit dependency declaration
- Modules that run independently (not via run.py)

Both can coexist: PYTHONPATH ensures `sys.path` is correct in subprocesses,
common.smk ensures imports work during parsing.
