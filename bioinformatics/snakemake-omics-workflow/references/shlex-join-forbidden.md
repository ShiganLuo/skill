# Command joining in run block scripts — `shlex.join` vs `shlex.quote`

## `shlex.join()` is forbidden

`shlex.join()` requires Python 3.8+. Module conda envs with `python>=3.6` (scTE) or `python>=3.7` (mimseq)
may resolve to <3.8, causing `AttributeError: module 'shlex' has no attribute 'join'`.

## Two safe alternatives (both Python 3.3+)

```python
# Option A: plain join — safe args only
f.write(" ".join(cmd) + "\n")

# Option B: shlex.quote each arg — handles spaces and shell metacharacters
f.write(" ".join(shlex.quote(str(x)) for x in cmd) + "\n")
```

## Decision rule

| Scenario | Use |
|---|---|
| All args are hardcoded strings, flags, numbers, standard paths | `" ".join(cmd)` |
| Any arg is dynamic, user-provided, or may contain spaces/metas | `" ".join(shlex.quote(str(x)) for x in cmd)` |

## Why not always use shlex.quote?

`shlex.quote` wraps every arg in single quotes, which makes the generated script less readable
for debugging. When all args are safe (tool paths, flags, numbers), plain join is cleaner.

## Import

`import shlex` is already in `common.smk`; no extra import needed in modules that include it.

## Related pitfall

Section 7b in SKILL.md covers a different issue: multi-word parameter values (e.g. Java JVM options)
that need shell-level quoting inside the cmd list. That uses `f'"{value}"'` wrapping, not `shlex.quote`.
Use `shlex.quote` when the concern is argument-level safety, not shell-level value grouping.
