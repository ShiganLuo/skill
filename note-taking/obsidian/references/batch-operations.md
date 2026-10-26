# Batch Operations in Obsidian Vault

## Long-running batch tasks (user preference)

This user has low patience for repeated plan-and-confirm cycles when they have already given an execution task. They explicitly correct this pattern:

- **Don't repeat the plan** — they already gave one (e.g. "translate each paper"). Just do it.
- **Don't ask for permission** on scope decisions (which papers, in what order, how many) — pick a sensible default and proceed. State the default in one line so they can override.
- **Don't surface "we should discuss this first"** before starting. The first response after a batch task should be execution, not clarification.
- **Self-manage context**: write a progress file (`_translation_progress.md` or similar) with checkboxes before starting. Stop at the first quality cliff. Don't ask the user "should I stop?" or "do you want a status update?" — write the progress file and report.
- **Don't recap the problem** at length before each unit of work. One line of "now doing N" is enough.

The contrast to remember: the user does want pre-execution review for **design / architectural decisions** (e.g. "design the schema before implementing" — see User profile). Batch-execute tasks are different: just go.

## Batch file updates via execute_code

When updating many vault files at once (e.g., filling in templates for 30+ company notes), use `execute_code` with `patch()` from `hermes_tools`.

### Correct patch signature in execute_code

```python
from hermes_tools import patch
r = patch(path, old_string, new_string)
# Returns: {"success": True/False, ...}
```

**NOT** `patch(mode, path, old, new)` — the standalone `patch` tool has different args than `hermes_tools.patch`.

### Common failure modes

1. **File content mismatch**: Files that look identical may have different whitespace, extra tags, or encoding. Always `cat -A <file>` or `read_file` first if patch fails with "Could not find a match".

2. **Empty files**: If a file is completely empty (0 bytes), `patch` will fail. Use `write_file` instead.

3. **Identical old/new**: `patch` fails if old_string == new_string. Skip or adjust.

### Batch workflow pattern

```python
from hermes_tools import patch, write_file

updates = [
    {"path": "/path/to/file.md", "old": "old content", "new": "new content"},
    # ... more updates
]

for u in updates:
    r = patch(u["path"], u["old"], u["new"])
    name = u["path"].split("/")[-1]
    status = "OK" if r.get("success") else f"FAIL: {r.get('error', r)}"
    print(f"{name}: {status}")
```

### Pre-flight checks

Before batch-updating many files with similar templates:
1. Read a few sample files to verify the exact content/whitespace
2. Check for files with unexpected content (extra tags, different formatting)
3. Use `terminal` with `cat -A` to see hidden characters if patches fail

## Large batch file creation

For creating many similar files (e.g., company profiles from search results):
- Use `execute_code` with a loop over `write_file` or `patch`
- Group updates by similarity to reduce template duplication
- Print success/failure status for each file to catch issues early
