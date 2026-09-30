# --forcerun and --target-jobs in run.py

## How run.py processes `--forcerun`

In `execute_workflows`, `args.forcerun` goes through prefix logic:
1. File paths (`/` in t) → pass through as-is
2. Wildcard specs (`:` and `=` in t) → prefix rule part only, e.g. `scanpy_auto:tissue=Uterus` → `scRNAseq_scanpy_auto:tissue=Uterus`
3. Plain rule names → prefix with workflow name, e.g. `scanpy_auto` → `scRNAseq_scanpy_auto`

In `build_snakemake_cmd`, the processed targets are split:
- Plain targets (no `:` + `=` combo) → `--until TARGET --forcerun TARGET` (original behavior)
- Wildcard targets (`:` + `=` combo) → `--target-jobs RULE:wildcard=value --force` (new feature)

## snakemake CLI behavior (tested with 9.14.0)

| Command | Behavior |
|---------|----------|
| `--forcerun scRNAseq_scanpy_auto` | Works if rule is aliased via `use rule ... as scRNAseq_scanpy_auto` |
| `--forcerun scanpy_auto` | FAILS — snakemake doesn't recognize original name when aliased |
| `--until + --forcerun` with rule name | Works — original behavior |
| `--forcerun rule:wildcard=value` | CRASHES — snakemake treats it as file path |
| `--target-jobs rule:wildcard=value --force` | Works — forces specific wildcard instance |
| `--target-jobs rule_name` (no wildcards) | CRASHES — `ValueError: not enough values to unpack` |
| `--list-target-rules` | Only shows rules WITHOUT wildcards |
| `--list-rules` | Shows ALL rules including wildcard rules |

## Detection pattern

Use `":" in t and "=" in t` to detect wildcard specs. NOT just `"=" in t` — file paths may contain `=`.

```python
# CORRECT
if ":" in t and "=" in t:  # wildcard spec

# WRONG — too crude
if "=" in t:  # matches file paths with = too
```

## Critical: `--target-jobs` requires RULE:WILDCARD=VALUE format

snakemake's `--target-jobs` parser calls `entry.split(":", 1)` and unpacks into `(rulename, wildcards)`. A bare rule name without `:` causes `ValueError: not enough values to unpack`.

This means you CANNOT use `--target-jobs` to force a wildcard rule without specifying wildcard values. If you need to force ALL instances of a wildcard rule, you must enumerate each wildcard combination.

## Critical: preserve original behavior when adding features

When modifying `build_snakemake_cmd`, NEVER change the `plain_targets` branch. Only ADD new branches for new input formats. The user corrected: "保留当前用法,增加功能" (preserve current usage, add features).

Check `git diff HEAD -- run.py` before making changes to verify you're not accidentally modifying existing code paths.

## Debugging checklist

1. Check the actual snakemake command in the log (`grep 'Running:' <logfile>`)
2. Verify the rule name matches the alias (not the original)
3. For wildcard targets, verify `--target-jobs` is used (not `--forcerun`)
4. Check `git diff HEAD -- run.py` to see what changed from the working version
5. Use `--list-rules` to discover all available rules (including wildcard ones)
6. If `--forcerun` shows "Nothing to be done", the rule may have wildcards — use `--target-jobs` with explicit wildcard values instead