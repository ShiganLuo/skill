# Package Import Organization & BOM/Append Pitfalls

Recurring issues when refactoring Python scripts in a `src/`-layout project
where scripts are invoked directly (`python script.py`) but need to import from
sibling package trees.

## 1. `__init__.py` Relative Import Bug

### Symptom

`from common.util.SepUtil import detect_delimiter` fails with
`ModuleNotFoundError: No module named 'SepUtil'` -- even though the file exists
at `common/util/SepUtil.py`.

### Root Cause

`common/util/__init__.py` contains an **absolute** import:

```python
# WRONG -- absolute import, Python 3 cannot find top-level 'SepUtil'
from SepUtil import detect_delimiter
```

When Python imports `common.util` (triggered by `from common.util.SepUtil
import ...`), it runs `__init__.py` first. The absolute `from SepUtil import`
fails because `SepUtil` is not a top-level module on `sys.path` -- it is a
sibling file inside the `common/util/` package.

### Fix

Use an explicit relative import:

```python
# CORRECT -- relative import within the package
from .SepUtil import detect_delimiter

__all__ = [
    "detect_delimiter",
]
```

### Audit Pattern

When any `from common.util.X import Y` fails, check the corresponding
`__init__.py` FIRST. A bad absolute import in `__init__.py` breaks ALL imports
through that package, even direct module-path imports like
`from common.util.SepUtil import detect_delimiter`.

Quick audit:

```bash
# Find __init__.py files with bare absolute imports (no dot prefix)
grep -rn "^from [A-Z]" --include="__init__.py" src/
```

Any `__init__.py` line matching `from SomeModule import` (capital first letter,
no leading dot) is suspicious -- it should be `from .SomeModule import`.

## 2. `sys.path` Bootstrap for Package-Style Imports

### Problem

Scripts in `src/download/` need to import from `src/common/util/`, but they are
invoked as `python sra_download.py` (not `python -m download.sra_download`).
When run directly, Python puts the script's own directory (`src/download/`) on
`sys.path`, NOT `src/` -- so `import common` fails.

Existing scripts in this project used the anti-pattern:

```python
# ANTI-PATTERN -- sys.path.append with os.path.dirname chains
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.util.SepUtil import detect_delimiter
```

### Preferred Fix: Package-Root Bootstrap

Compute the package root (`src/`) from `__file__` and insert it at `sys.path[0]`
once. This is NOT a hack -- it is standard "package root discovery" that aligns
with the project's package structure. It works from any CWD.

```python
import sys
from pathlib import Path

# ---- Package import bootstrap: put src/ on sys.path so common.* resolves ----
_SRC_DIR = Path(__file__).resolve().parent.parent  # src/ is parent of download/
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from common.util.SepUtil import detect_delimiter
```

### Key Points

- `Path(__file__).resolve().parent.parent` -- `.parent` is the script's dir
  (`download/`), `.parent.parent` is `src/` (the package root containing
  `common/`).
- `sys.path.insert(0, ...)` (not `append`) -- ensures the project's `common/`
  takes precedence over any same-named installed package.
- The `if str(_SRC_DIR) not in sys.path` guard prevents duplicate entries when
  the module is imported multiple times.
- This works regardless of CWD: `python src/download/sra_download.py` from
  anywhere resolves correctly because `__file__` is absolute.
- `common/` does NOT need `__init__.py` -- Python 3.3+ PEP 420 namespace
  packages handle it. But `common/util/__init__.py` must use relative imports
  (see section 1 above).

### When to Use This vs `python -m`

- `python -m download.sra_download` -- works IF `src/` is already on `sys.path`
  (e.g., installed as a package, or `PYTHONPATH=src`). Cleanest but requires
  invocation change.
- Bootstrap in script -- works with existing `python script.py` invocation
  patterns (shell scripts, Snakemake `shell:` blocks, cron). No invocation
  change needed. Preferred for scripts invoked by external tooling.

## 3. UTF-8 BOM Breaks `csv.DictReader` Column Matching

### User Policy (MUST FOLLOW)

**Use `encoding="utf-8"` everywhere -- both read and write.** Do NOT use
`utf-8-sig` in any context. Fix BOM problems at the **writer** (stop producing
BOM), not at the reader (tolerating BOM). This user does not need Excel
compatibility for TSV/CSV outputs.

### Symptom

```
ValueError: No column 'gsm' in /path/to/all_runinfo.tsv
```

But the file clearly has a `gsm` column as the first header.

### Root Cause

The file has a UTF-8 BOM (`\xef\xbb\xbf`, rendered as `\ufeff` in Python str).
When opened with `encoding="utf-8"`, the BOM is preserved and prepended to the
first column name:

```python
>>> import csv
>>> with open("all_runinfo.tsv", encoding="utf-8") as f:
...     reader = csv.DictReader(f, delimiter="\t")
...     print(reader.fieldnames)
['\ufeffgsm', 'Series', 'FTP download', ...]
```

Case-insensitive comparison `'\ufeffgsm'.lower() == 'gsm'` is `False`.

### Fix: Change the Writer, Not the Reader

The BOM is written by code using `encoding="utf-8-sig"` for file **output**.
`utf-8-sig` is dual-purpose: strips BOM on read, **adds** BOM on write. Find
all write-side uses and change them to plain `utf-8`:

```python
# WRONG -- produces BOM on write
df.to_csv(path, encoding="utf-8-sig")
# or
with open(path, "w", encoding="utf-8-sig") as f: ...

# CORRECT -- no BOM
df.to_csv(path, encoding="utf-8")
# or
with open(path, "w", encoding="utf-8") as f: ...
```

### Full BOM Audit Pattern

1. **Confirm BOM on the file**: `head -1 file.tsv | xxd | head -3` -- look
   for `ef bb bf` at the start.
2. **Find ALL writers**: search for `utf-8-sig` and `utf_8_sig` across the
   entire codebase:
   ```bash
   grep -rn 'utf-8-sig\|utf_8_sig' --include="*.py" .
   ```
   Any `to_csv`, `open(..., "w")`, or `DictWriter` with `utf-8-sig` is a BOM
   producer. Change them ALL to plain `utf-8`.
3. **Regenerate affected files** after fixing the writer -- existing files
   still carry BOM until overwritten.
4. **Do NOT use `utf-8-sig` as a read-side workaround.** The user wants no BOM
   in any file. If a legacy file still has BOM, regenerate it.

### Why pandas Doesn't Have This Problem

`pd.read_csv()` with default `encoding="utf-8"` automatically detects and strips
UTF-8 BOM. Only manual `open()` + `csv.DictReader` is affected. So scripts using
pandas for CSV/TSV reading are immune; scripts using the `csv` module are not.

### Other Affected Read Patterns

Any manual `open(path, encoding="utf-8")` that then parses headers is affected
by legacy BOM files:

- `csv.DictReader` -- BOM on first column name
- `csv.reader` -- BOM on first cell of first row
- Manual `f.readline().split(delim)` -- BOM on first token
- `json.load(f)` -- BOM causes `json.JSONDecodeError` (JSON spec forbids BOM)

For legacy files that cannot be regenerated, a one-time `sed` strip is cleaner
than code-level `utf-8-sig`:

```bash
sed -i '1s/^\xef\xbb\xbf//' file.tsv
```

## 4. `write_tsv` Append Mode Silently Duplicates Rows

### User Policy (MUST FOLLOW)

**Remove append entirely. `write_tsv` must always overwrite (`"w"` mode).**
Multi-execution safety comes from overwrite semantics, not append. Do not
provide `--append` CLI flags or `append=` parameters on write functions.

### Symptom

A TSV file has N unique records but N*k data rows -- every record appears k
times, all with identical content. The header appears only once (BOM only at
file start).

### Root Cause

`write_tsv` with `append=True` adds rows to the end of the file without
deduplicating against existing content. If `collect_gse_runinfo` (or any
function using `write_tsv`) is called k times with `--append` on the same
output file and the same input data, each run appends the full record set.
The result is k identical blocks of records.

### Fix: Remove Append, Always Overwrite

```python
def write_tsv(records, output_tsv, fieldnames):
    """Write records to a TSV file (always overwrite)."""
    if not records:
        logger.warning("No records to write: %s", output_tsv)
        return

    output_path = Path(output_tsv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
```

Remove the `append` parameter from `write_tsv` and ALL callers
(`collect_gse_runinfo`, CLI `main()`, etc.). Remove `--append` from argparse.
This ensures every run produces a clean, single-copy file.

### Detection (for diagnosing existing duplicated files)

```bash
# Check if all duplicates are identical blocks
total=$(tail -n +2 file.tsv | wc -l)
unique=$(tail -n +2 file.tsv | cut -f1 | sort -u | wc -l)
echo "total=$total unique=$unique ratio=$((total / unique))"
# If ratio > 1 and total % unique == 0, it's k identical appends

# Verify blocks are identical
tail -n +2 file.tsv | head -$unique | sort > /tmp/b1.txt
tail -n +2 file.tsv | sed -n "$((unique+1)),$((2*unique))p" | sort > /tmp/b2.txt
diff /tmp/b1.txt /tmp/b2.txt  # empty diff = identical blocks
```

After fixing the code, regenerate the duplicated file by running the writer
once in overwrite mode.

## 5. Content-Based File Parsing (Not Extension-Gated)

### Problem

A file like `GSM.txt` contains TSV content (`gsm\tSeries\tFTP
download\tOrganism\tSource name`) but has a `.txt` extension. If the parser
dispatches on extension (`.csv`/`.tsv` -> table parser, else -> plain text),
the entire line is treated as a single ID:

```
GSM4110156\tGSE138518\tN/A\tHomo sapiens\tNormal
```

This string (with embedded tabs and spaces) is then used as a filename in
`os.path.join(outdir, f"{acc}.html")`, producing an invalid path and
`[Errno 2] No such file or directory`.

### Fix: Parse Based on Content, Not Extension

```python
def _from_file(self, path: str) -> Set[str]:
    gsms: Set[str] = set()

    try:
        delimiter = detect_delimiter(path)
    except ValueError:
        delimiter = None

    if delimiter:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            col = self._find_id_column(reader.fieldnames)
            if col:
                for row in reader:
                    val = row.get(col)
                    if val:
                        gsms.add(val.strip())
                return gsms

    # Fallback: plain text, one ID per line
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                gsms.add(line)

    return gsms
```

### Key Points

- `detect_delimiter` raises `ValueError` for single-column plain-text files
  (no delimiter found). Wrap in `try/except ValueError` to handle this.
- If a delimiter IS found but the ID column doesn't match, fall through to
  plain-text mode rather than raising -- the file might have an unrelated
  header.
- This pattern handles ALL cases uniformly:
  - `.txt` file with TSV content -> table parse
  - `.txt` file with CSV content -> table parse
  - `.csv` file -> table parse
  - `.tsv` file -> table parse
  - `.txt` file with one ID per line (no delimiter) -> plain text fallback
- The old extension-gated approach (`ext in (".csv", ".tsv")`) is fragile
  because downstream tools (Excel, shell redirects, manual exports) may
  produce tabular content with arbitrary extensions.
