# Extracting long run: blocks into helper scripts

Use this reference when a Snakemake `run:` block grows beyond ~40 lines of business logic. The user explicitly prefers extracting the logic into a standalone Python script under the module's `bin/` directory, with the `.smk` file becoming a thin wrapper that constructs an argument list and calls the helper via `shell()`.

## When to extract

Extract when the `run:` block contains any of:
- Multi-stage pipeline logic (e.g. three-pass alignment with 4+ STAR invocations, pipe lines, intermediate file management)
- Helper functions defined inline (`def star_options(...)`, `def samtools_fastq(...)`) that make the block hard to scan
- More than ~40 lines between `run:` and `except`
- Logic that would benefit from standalone testing (argparse `--help`, unit-test imports)

Do NOT extract when:
- The `run:` block is a simple 10-20 line "build cmd list, write script, shell()" pattern (the standard rule template)
- The block has no helper functions and no multi-stage logic

## Pattern: thin .smk wrapper + bin/ helper script

### .smk file (thin wrapper)

The `.smk` keeps only:
1. Config reads at module scope
2. `input`/`output`/`log`/`threads`/`conda` declarations
3. A `run:` block that builds a `cmd = ["python", HELPER, "--arg", value, ...]` list and calls `shell(f"{shlex.join(cmd)} > {shlex.quote(log_path)} 2>&1")`

```python
"""Module docstring."""

include: "../../common/common.smk"

import json
import os
import shlex

# ... config reads ...
HELPER = os.path.join(config["ROOT_DIR"], "modules/<tool>/bin/<helper>.py")

rule example_rule:
    input: ...
    output: ...
    log: ...
    threads: 12
    conda: "<tool>.yaml"
    run:
        log_path = str(log)
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            cmd = [
                "python", HELPER,
                "--input", str(input.bam),
                "--output", str(output.bam),
                "--log", log_path,
                "--threads", str(threads),
                "--tool-bin", STAR,
                # ... pass all config-derived values as CLI args ...
                "--params-json", json.dumps(some_config_dict),
            ]
            if some_bool_flag:
                cmd.append("--bool-flag")
            shell(f"{shlex.join(cmd)} > {shlex.quote(log_path)} 2>&1")
        except Exception as exc:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"rule failed: {exc}\n")
            raise
```

### bin/ helper script

The helper script is a standard Python CLI with:
1. `argparse` for all parameters (paths, threads, binary paths, config dicts as JSON strings)
2. A `build_script(args) -> str` function that constructs the shell script content (using the list-based pattern from `references/shell-script-command-construction.md`)
3. A `main()` that creates output directories, writes the timestamped script, and executes it via `subprocess.run(["bash", script], ...)`

```python
#!/usr/bin/env python3
"""Description of what this helper does."""

from __future__ import annotations
import argparse, json, os, shlex, subprocess, time

def build_script(args: argparse.Namespace) -> str:
    """Build the shell script content as a single string."""
    lines = ["#!/usr/bin/env bash", "set -euo pipefail"]
    # ... construct commands as lists, shlex.join each ...
    cmd = [args.star, "--runThreadN", str(args.threads), ...]
    lines.append(shlex.join(cmd))
    return "\n".join(lines) + "\n"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--input", required=True)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--params-json", default="{}",
                        help="JSON string of parameter overrides")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    # Parse JSON config dicts
    params = json.loads(args.params_json) if args.params_json else {}
    # Create output directories
    for path in (args.output_bam, args.log):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    # Generate and execute timestamped script
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    script = os.path.join(os.path.dirname(args.output_bam), f"run_{stamp}.sh")
    try:
        content = build_script(args)
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(content)
        subprocess.run(["bash", script],
                       stdout=open(args.log, "w"),
                       stderr=subprocess.STDOUT, check=True)
    except Exception as exc:
        with open(args.log, "a", encoding="utf-8") as handle:
            handle.write(f"failed: {exc}\n")
        raise

if __name__ == "__main__":
    main()
```

## Key design rules

1. **Pass config dicts as JSON strings.** The `.smk` serializes `three_pass_params` or `local` dicts with `json.dumps()`, and the helper deserializes with `json.loads()`. This avoids dozens of individual `--key value` flags for nested config.

2. **Pass binary paths as explicit CLI args** (`--star`, `--samtools`, `--bedtools`). Do not assume the helper can resolve `config.get("Procedure")` — the helper is a standalone script with no Snakemake context.

3. **The helper owns script generation and execution.** The `.smk` does NOT write the shell script; it only calls the helper. The helper generates the timestamped `.sh` file internally.

4. **Keep the try/except in the .smk** for Snakemake-level error logging, AND in the helper's `main()` for script-level error logging. Both layers append to the same log file.

5. **Helper path resolution uses `config["ROOT_DIR"]`** in the `.smk`, not relative paths, because the working directory at execution time may differ from the module directory.

6. **Boolean flags use `action="store_true"`** in the helper's argparse, and `cmd.append("--flag")` conditionally in the `.smk`. Do not pass `"--flag"` or `""` as a string value.

## Verification

When verifying this pattern:
1. `python3 -c "import py_compile; py_compile.compile('bin/helper.py', doraise=True)"` — helper syntax
2. `python3 bin/helper.py --help` — argparse works, all expected flags present
3. Import the helper module and call `build_script(mock_args)` directly — verify generated script content
4. `snakemake --dry-run` — the `.smk` wrapper parses and loads in the DAG
5. Check the generated script has correct command count, pass structure, and shell variable handling

## Session example

The star_3pass module was refactored from two ~160-line `run:` blocks (with inline `star_options()` and `samtools_fastq()` helpers, 20+ `handle.write(f"...")` calls) into:

```
star_3pass/
├── star_3pass.smk          # ~60 lines: config + thin run: wrapper
├── star_3pass_gene.smk     # ~50 lines: same pattern
└── bin/
    ├── three_pass_align.py      # ~250 lines: build_script() + main()
    ├── gene_specific_align.py   # ~180 lines: build_script() + main()
    └── prepare_gene_inputs.py   # (pre-existing, unchanged)
```

The `.smk` `run:` blocks went from ~160 lines to ~25 lines each. All list-based command construction (from `references/shell-script-command-construction.md`) moved into the helper's `build_script()` function.
