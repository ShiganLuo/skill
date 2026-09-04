# Silent Patch Failure: Diagnosis and Recovery

## The Problem

The `patch()` tool — both standalone and inside `execute_code` — returns `{"success": true}` even when the file was NOT modified. This happens when `old_string` doesn't match the actual file content exactly (whitespace, indentation, line endings, encoding).

## This Session's Failure Record

In a single session adding `projectId` + `metaContent` + `metaType` + `extraParams` to the Pipeline domain, patches failed silently on **4 out of 6 files**:

| File | Patch Target | Result |
|------|-------------|--------|
| `Pipeline.java` | Add 3 new fields | FAILED — field not added |
| `PipelineMapper.xml` | Add columns to resultMap/insert/update | FAILED — columns not added |
| `PipelineServiceImpl.java` | Add constructor param + 2 new methods | FAILED — methods not added |
| `AdminProjectController.java` | Add analysis endpoints + PipelineService injection | FAILED — endpoints not added |
| `AdminPipelineDTO.java` | Rewrite via `write_file` | OK |
| `PipelineService.java` | Rewrite via `write_file` | OK |

Every failed patch returned `{"success": true, ...}`. The only way to detect failure was post-hoc grep verification.

## Why It Happens

The `patch()` tool uses fuzzy matching (9 strategies). When the `old_string` contains:
- Multi-line content with mixed indentation
- Generic type parameters like `<Pipeline>` that appear in multiple places
- Content adjacent to other similar patterns

...the fuzzy matcher may find no unique match or match the wrong location, and silently skip.

## Diagnosis Pattern

After ANY patch on a Java/XML file, verify immediately:

```python
# In execute_code:
result = terminal("grep -c 'expected_new_text' target_file.java")
if '0' in result['output']:
    print("PATCH FAILED — file unchanged")
```

Or after standalone patch calls:
```bash
grep -c 'expected_new_text' /path/to/file.java
# 0 = failed, 1+ = succeeded
```

## Recovery: Always Use write_file

When a patch fails on a file, **stop trying patches on that file immediately**. Switch to `write_file`:

1. `read_file` to get current content
2. Make the changes mentally or in a variable
3. `write_file` with the complete corrected file

This is always more reliable than debugging why `old_string` doesn't match.

## Prevention Rules

1. **For critical Java files** (controllers, services, entities, mappers) with multiple changes: prefer `write_file` from the start
2. **For single-line changes** in well-understood files: `patch()` is usually fine
3. **For router files**: always verify with grep after patching
4. **Batch edits via execute_code**: include grep verification after each patch group

## User Feedback

The user reported: "当前后端代码存在错误,无法启动" — the backend couldn't start because the controller was missing the analysis endpoints and PipelineService dependency injection that patches failed to add.
