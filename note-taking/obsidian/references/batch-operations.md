# Batch Operations in Obsidian Vault

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
