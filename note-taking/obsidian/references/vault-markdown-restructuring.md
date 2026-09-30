# Vault Markdown Restructuring (Frontmatter + Heading Hierarchy)

Workflow for bulk-tidying a poorly-formatted Obsidian vault subfolder:
add YAML frontmatter, inject top-level `#` title, normalize blank lines,
and promote common Chinese chapter markers (`一、xxx`, `1）xxx`) to
`#`/`##` headings.

## When to use

User asks to "整理排版" / "make it look better" / "add structure" for
a vault folder containing many pasted/clipped notes that:
- Have no YAML frontmatter (so Obsidian Dataview / Graph view skips them)
- Use inline `一、xxx` and `1）xxx` markers instead of `#` headings
- Have paragraphs glued together with no blank lines
- Mix markdown with pasted source text that has inconsistent spacing

This workflow is intentionally **conservative**: it does NOT touch the
semantic content (no merging, splitting, or rewording).

## The Three-Phase Script

```python
import re
from pathlib import Path

CN = "一二三四五六七八九十"
# Use character classes directly — Python 3.13 has a quirk where
# string-literal grouping (`^(CN_STR)、`) fails to match but character
# class forms (`^[CN]+、`) work. Always prefer character classes.
RE_CHAPTER     = re.compile(rf"^[{CN}]+(?:[{CN}]|十|百)?、\s*(.+?)\s*$")
RE_SUB_SECTION = re.compile(r"^(\d+)\）\s*(.+?)\s*$")
RE_ITEM        = re.compile(r"^(\d+)、\s*(.+?)\s*$")  # see pitfall below

def split_fm(content):
    """Split into (frontmatter, body). Empty fm if none."""
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return ("\n".join(lines[:i+1]), "\n".join(lines[i+1:]))
    return ("", content)

def has_h1(lines):
    return any(l.lstrip().startswith("# ") for l in lines)

def promote(lines, do_chapter, do_subsec):
    out = []
    in_table = False
    for line in lines:
        s = line.strip()
        if s.startswith("|"):
            in_table = True; out.append(line); continue
        if in_table and not s.startswith("|"):
            in_table = False
        if s == "---":  # frontmatter separator
            out.append(line); continue
        if s.startswith("#"):  # already a heading
            out.append(line); continue
        if do_chapter:
            m = RE_CHAPTER.match(s)
            if m:
                title = m.group(1).strip().rstrip("：:。.、 ")
                out.append(f"# {title}"); continue
        if do_subsec:
            m = RE_SUB_SECTION.match(s)
            if m:
                title = m.group(2).strip().rstrip("：:。. ")
                out.append(f"## {title}"); continue
        out.append(line)
    return out

def normalize_blank(lines):
    """Collapse runs of 2+ blanks to 1, strip trailing."""
    out, blank = [], 0
    for l in lines:
        if l.strip() == "":
            blank += 1
            if blank <= 1: out.append("")
        else:
            blank = 0
            out.append(l)
    while out and out[-1].strip() == "": out.pop()
    return out

def ensure_blank_around_headings(lines):
    """Insert blank lines before and after every #/##/### heading."""
    result = []
    n = len(lines)
    for i, line in enumerate(lines):
        is_h = (line.lstrip().startswith("# ") or
                line.lstrip().startswith("## ") or
                line.lstrip().startswith("### "))
        prev_blank = (i == 0) or (lines[i-1].strip() == "")
        next_blank = (i == n-1) or (lines[i+1].strip() == "")
        if is_h and not prev_blank and result:
            result.append("")
        result.append(line)
        if is_h and not next_blank:
            result.append("")
    return result

def process(path, category_map, tag_list):
    content = path.read_text(encoding="utf-8")
    fm, body = split_fm(content)

    # 1. Inject frontmatter if missing
    if not fm:
        fm = (
            "---\n"
            f"title: {path.stem}\n"
            f"category: {category_map.get(path.parent.name, 'uncategorized')}\n"
            f"aliases:\n  - {path.stem}\n"
            f"tags:\n" + "\n".join(f"  - {t}" for t in tag_list) +
            "\n---\n\n"
        )

    lines = body.split("\n")
    has_top = has_h1(lines)

    # 2. Add top-level title from filename if missing
    if not has_top:
        # Insert before first content line
        insert_pos = next((i for i, l in enumerate(lines) if l.strip()), len(lines))
        lines = [f"# {path.stem}", ""] + lines[insert_pos:]
        has_top = True

    # 3. Promote chapters only if no h1 existed originally
    lines = promote(lines,
                    do_chapter=not has_top,  # if we just added one, don't double-promote
                    do_subsec=True)

    # 4. Blank-line normalization
    lines = normalize_blank(lines)
    lines = ensure_blank_around_headings(lines)

    new_body = "\n".join(lines).rstrip() + "\n"
    new_content = (fm + "\n" + new_body) if fm else new_body
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        return "changed"
    return "unchanged"
```

## Critical Decisions

### DO NOT promote `1、xxx` (the third-tier pattern)

`1、xxx` is ambiguous: it could be a third-level heading **or** a list
item under a `1）xxx` parent. Auto-promotion breaks the user's intent.
Leave `1、xxx` as plain list lines; let them manually demote if needed.

### Add `#` title from filename (when missing) BEFORE promoting `1）xxx`

If you promote `1）xxx → ##` first, then later add a top-level `#`, the
file ends up with no `##` because the promotion logic checks "do we need
an h2" — but you've already added the h1 separately. Order matters:
add h1 first, then promote subsections.

### Do NOT skip files that already have `##` or `###`

Many real-world notes have pre-existing heading levels. Don't be afraid
to touch them — `promote()` has guards (`if s.startswith("#"): continue`)
that preserve existing markdown headings.

### Character classes vs string grouping in regex

`re.compile(rf"^({CN_NUM})、")` **does not match** in CPython 3.13 even
when `CN_NUM` literally equals the same characters you can hardcode.
Use character class form `re.compile(rf"^[{CN_NUM}]、")` — it works
reliably. Always prefer character classes for Chinese range matching.

### NBSP at line end silently breaks matching

Files copied from PDFs/Word often have `\xa0` (NBSP) at end of lines.
Your `(.+?)\s*$` pattern should still match (Python's `\s` includes NBSP
by default), but verify with a sample test before batch-running.

## Pitfalls

- **Run a dry-run on 3-5 sample files first.** Check that the auto-detected
  h1 + promoted h2/h3 hierarchy reads sensibly before touching 200+ files.
- **Some files in the folder may already be damaged** by a previous bad
  script run (e.g. earlier `1、xxx` → `###` promotion without context).
  Add a manual review step: after running, scan for files whose body
  starts with `##` or `###` (potential top-level heading missing) and
  ask the user to fix manually.
- **Frontmatter injection must skip files that already have `---` at
  top.** `split_fm()` handles this.
- **Trailing whitespace (NBSP, full-width space) in heading titles.**
  Strip with `rstrip("：:。.、 ")` after capture — but be conservative:
  don't strip meaningful characters. The `:`, `。`, `.`, `、` rstrip is
  enough for chapter titles.
- **Don't run on a git-untracked vault.** If the user doesn't have version
  control, remind them that damaged files cannot be auto-restored.
  Real session cost: 13 files in a 242-file vault got damaged by an
  earlier regex bug and stayed damaged permanently.
- **Output frontmatter uses English keys** (`title`, `category`, `aliases`,
  `tags`) — these are YAML standards. Do not localize the keys themselves
  (only the values can be Chinese).

## Variant: light-touch pass

For folders where only frontmatter is missing (headings already good),
skip the `promote()` step entirely. Add a `--mode fm-only` flag that
only runs split_fm + frontmatter injection. This is the safest pass
and should be the default for any unfamiliar vault.

## Variant: deep-clean pass

For folders with deeply-broken content (mixed `\r\n`, pasted HTML, etc.),
add pre-processing steps: strip `\r`, normalize `—` (em-dash) to `——`,
collapse multiple spaces. These should be opt-in, never default.

## Related

- `references/batch-operations.md` — general batch file-update patterns
  via `hermes_tools.patch` and `execute_code`. This file covers a more
  specialized case (heading promotion) that the general patterns don't
  address.