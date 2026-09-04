---
name: safe-file-editing
description: >-
  How to safely modify files using Hermes Agent tools without corruption.
  Covers: write_file vs patch tool selection, file-type-specific rules,
  recovery procedures, and batch-edit safety. Trigger: any session that
  modifies source code files, config files, or structured documents.
tags: [hermes-tools, file-editing, safety, pitfall, vue, patch]
related_skills: [full-stack-model-migration, systematic-debugging]
---

# Safe File Editing with Hermes Agent

## The Core Rule

**NEVER use `write_file` on existing files that have content you want to preserve.**

`write_file` replaces the ENTIRE file content. If the tool encounters an issue
(serialization, encoding, path resolution), it may write an EMPTY file instead,
silently destroying the original content.

## Tool Selection Matrix

| Situation | Tool | Why |
|-----------|------|-----|
| Modify existing file (any type) | `patch` | Preserves unchanged content, only modifies matched sections |
| Create brand-new file | `write_file` | Full content replacement is correct for new files |
| Replace entire file intentionally | `write_file` | Only when you've read the full content and are rewriting it |
| Batch-modify many files | `patch` (one per file) | `execute_code` + `write_file` in a loop is the #1 corruption vector |
| Vue `.vue` files | `patch` ONLY | `write_file` on `.vue` files has a high corruption rate |
| TypeScript `.ts` files | `patch` preferred | `write_file` works but `patch` is safer for small changes |

## File-Type-Specific Rules

### Markdown (.md) — especially Obsidian vault files
`write_file` is acceptable for creating brand-new files or complete rewrites of
nearly-empty files (<10 lines of real content). For any file with substantial
content (>10 lines), use `patch` to avoid silent corruption.

Obsidian-specific:
- To resize embedded images: `![[image.png|500]]` (width in px)
- To resize with dimensions: `![[image.png|300x200]]`
- Attachments live in `<filename>_Attachments/` directories

Pitfall: When patching markdown with Chinese text, the old_string must match
the file's exact byte sequence. If patch fails with "hunk not found", read
the file first to get the exact text — CJK encoding can cause invisible
differences.

### Vue Single-File Components (.vue)
**DANGER: High corruption risk with `write_file`.**

Vue SFCs must contain `<template>` or `<script>` tags. When `write_file` fails
to serialize the content correctly, it produces an empty file, and Vite reports:
```
At least one <template> or <script> is required in a single file component.
```

**Rules:**
1. NEVER use `write_file` on existing `.vue` files
2. ALWAYS use `patch` with precise old_string/new_string
3. For adding imports: match the exact import line and prepend/append
4. For adding variable declarations: match the first `const` line after imports
5. For updating function bodies: match the function signature + first line

**Recovery:**
```bash
git checkout -- path/to/corrupted-file.vue
```

### TypeScript Files (.ts, .d.ts)
`write_file` works but is risky for files with complex content. Prefer `patch`
for modifications. `write_file` is acceptable for small files you've fully read.

**Pitfall: backtick template literals get corrupted.** When `write_file` processes
TypeScript containing template literals like `` `Bearer ${accessToken}` ``, the
backticks can be silently replaced with `***`, producing broken syntax that still
"looks right" on casual inspection. Always grep for `***` in `.ts` files after
any write operation. If corruption has already occurred, use Python with
`open(path, "rb")` + byte-level `replace()` to fix — `patch` cannot match the
corrupted `***` reliably since it's not the original text.

### Java Files (.java)
`patch` is safe. `write_file` works for complete rewrites (e.g., rewriting a
service implementation). Always verify line count after writing.

### MyBatis XML (.xml)
`patch` preferred for targeted changes. `write_file` acceptable for full
rewrites of mapper files since they're often rewritten entirely.

### SQL Files (.sql)
`patch` preferred. `write_file` acceptable for small schema files.

## Batch Modification Safety

### WRONG: execute_code + write_file
```python
# THIS CORRUPTS FILES — do not do this
for f in files:
    content = read_file(f)
    content = content.replace("old", "new")
    write_file(f, content)  # Can empty the file on failure
```

### RIGHT: execute_code + patch
```python
# THIS IS SAFE
for f in files:
    patch(f, "old_pattern", "new_pattern")
```

### RIGHT: Sequential patch calls
```python
# Also safe — explicit patch per file
patch("file1.vue", "old1", "new1")
patch("file2.vue", "old2", "new2")
```

## Verification Checklist

After any batch file modification:

1. **Check file sizes**: `wc -l` on all modified files — any zero-line files
   are corrupted
2. **Check for empty files**: `find . -name "*.vue" -empty` after Vue edits
3. **Check syntax**: If the project has a dev server running, watch for errors
4. **Grep for old patterns**: Ensure no stale references remain
5. **Git diff**: Review all changes before committing
6. **Build after fix**: for Vue/Vite repair sessions, rerun `npm run build`
   (or the repo's equivalent) and verify it exits 0 before reporting success.

## Vue/Vite Build Repair Notes

See `references/vue-vite-build-fix-notes.md` for repo-specific build-repair notes
and verified chunk-splitting patterns.

See `references/repo-history-artifact-purge.md` for the verified orphan-branch +
force-push workflow to remove tracked build artifacts from repository history.

Practical notes:
- Keep `.vue` edits on `patch` only.
- If build failures come from generated Element Plus / auto-import typings, verify whether the repo expects full typecheck in the build script or just a Vite production bundle.
- When you touch bundling, re-run the build and note the largest emitted chunks after optimization.
- Before history-rewrite or artifact-purge work, save a patch of source changes that excludes `dist/`, `node_modules/`, and other generated trees so you can safely reconstruct the working tree after an orphan-branch reset.
- For repos polluted by tracked build output, a practical cleanup path is: expand `.gitignore`, confirm tracked artifact scope, create an orphan branch, `git reset`, `git clean -fdX`, re-add only source files, commit the clean tree, then force-push after verifying `git ls-tree -r --name-only HEAD` contains no `dist/`, `node_modules/`, or `target/` paths.

```bash
# Quick verification after batch edits
for f in modified_files; do
  lines=$(wc -l < "$f")
  echo "$f: $lines lines"
done
```

## Pitfall: `sed -i` for Vue/TypeScript file edits

`sed -i` is extremely fragile for inserting multi-line content into `.vue` and `.ts` files. It frequently:
- Breaks JavaScript/TypeScript syntax (missing commas, unclosed braces)
- Inserts content in wrong locations (after the wrong line)
- Produces unparseable files that pass `sed` but fail `vue-tsc` or `vite build`

**Real incident**: Used `sed -i` to insert a new route object into `router/index.ts`. The insertion broke the array syntax — missing comma between objects, extra closing brace. The error was:
```
ERROR: Expected identifier but found "{"
```

**Rule**: NEVER use `sed -i` for inserting structured content (objects, arrays, function bodies) into `.vue` or `.ts` files. Use `patch` tool or `write_file` (for complete rewrites) instead.

`sed -i` is acceptable ONLY for simple single-line replacements (renaming a class, changing an import path) where the replacement is the same structure as the original.

## Patch Tool Best Practices

### Finding the right anchor string
1. Read the file first to find unique, stable strings near the change point
2. Include enough context to make the match unique (not just "const")
3. Prefer matching complete lines over partial lines
4. If a line appears multiple times, include surrounding lines for uniqueness

### When patch fails
- The old_string wasn't found exactly — re-read the file to get current content
- The file was modified externally — re-read and retry
- The match is ambiguous — add more context to old_string

### When patch mangles special characters (regex backslashes, template literals)
The `patch` tool sometimes corrupts backslash sequences in TypeScript/JavaScript — particularly regex patterns like `path.replace(/^\\/api/, '/api')` where `\\/` means "escaped forward slash." The patch tool may double the backslashes to `\\\\/` during string matching, producing invalid syntax.

**Escape hatch: Python script via `execute_code`**:
```python
from hermes_tools import terminal
# Write a Python script that reads the file as bytes and does precise replacement
terminal("python3 -c \"\nimport sys\nwith open(sys.argv[1], 'rb') as f:\n    content = f.read()\ncontent = content.replace(b'old_bytes', b'new_bytes')\nwith open(sys.argv[1], 'wb') as f:\n    f.write(content)\n\" -- /path/to/file.ts")
```

**Verification**: After any backslash-sensitive edit, run `xxd <file> | grep <pattern>` to verify the exact byte sequence. In the `cat -A` output, `\\` represents one actual backslash character.

**Recovery**: If the patch already corrupted the file, use `git checkout -- <file>` to restore and retry with the Python approach.

## Recovery Procedures

### Single file corrupted
```bash
git checkout -- path/to/file
```

### Multiple files corrupted — BUT BE SURGICAL
```bash
# CORRECT: only revert the actually-corrupted files
git checkout -- corrupted-file1.vue corrupted-file2.vue

# DANGEROUS: reverting a mix of valid + invalid changes
git checkout -- file1 file2 file3  # may revert valid edits too!
```

**Pitfall: `git checkout` reverts ALL listed files, including valid changes.**
When you've made both good and bad changes across multiple files, doing
`git checkout -- good-file bad-file` silently destroys the good changes.
Always inspect `git diff --stat` first, then revert ONLY the files that
need reverting. If the user says "the image library feature was valid",
do NOT include those files in the checkout command.

**CRITICAL: Before ANY `git checkout`, follow this checklist:**
1. Run `git diff --stat` to see ALL changed files
2. Categorize each file: "keep" vs "revert"
3. NEVER list "keep" files in the checkout command
4. If unsure which files are valid, ASK THE USER before reverting
5. Prefer `git checkout -- specific-file` over `git checkout -- .`

**Real incident**: Session reverted 10+ files with valid feature additions
(ImagePicker component, backend API, env vars) when only the Editor.vue
needed reverting. User lost hours of work and was extremely frustrated.
The user explicitly said "你这样批量返回导致有效修改全部被你覆盖了"
(your batch revert overwrote all valid changes).

### No git history available
- Check editor undo history
- Check IDE local history (IntelliJ, VS Code)
- Re-derive content from the original source you read before editing

## Real-World Incident

Session: multi-user blog migration (this project).
- **What happened**: `execute_code` with `write_file` inside a loop emptied
  8 `.vue` files and 1 `.ts` file simultaneously
- **Root cause**: `write_file` tool serialization failure silently produced
  empty files instead of the intended content
- **Recovery**: `git checkout -- .` restored all files
- **Lesson**: Always use `patch` for modifications, never `write_file` in loops
