---
name: academic-paper-translation
description: "Translate academic PDFs to Chinese markdown for Obsidian. Also: generate Chinese academic theses as .docx."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [PDF, Translation, Academic, Obsidian, Zotero, Literature-Review]
    related_skills: [ocr-and-documents, pdf, obsidian, bioinformatics-wiki]
---

# Academic Paper Translation (English → Chinese)

Translate academic PDF papers into structured Chinese markdown notes, typically appended to existing Obsidian notes with YAML frontmatter.

## User's Formatting Requirements (MANDATORY)

All eight rules must be followed exactly:

1. **Complete translation**: Translate abstract, introduction, results, discussion, and methods sections fully
2. **Figure cross-references**: Preserve ALL references to figures (Fig. 1a, Fig. 2b, etc.) with original numbering and citation format
3. **Abbreviations**: Do NOT translate abbreviations (SMAC-seq, ATAC-seq, Fiber-seq, ChIP-seq, NMI, etc.)
4. **LaTeX formulas**: Use `$...$` for inline, `$$...$$` for block. No extra `$` signs
5. **Heading level**: Start from `###` (third-level) as the highest heading. Never use `#` or `##` for the translation
6. **Paragraph spacing**: One blank line between every paragraph
7. **No extra links**: Do not add any hyperlinks not in the original
8. **Literature cross-references**: Preserve original citation numbering (e.g., $^{1-3}$, $^{4,5}$)

## Workflow

### Step 1: Read existing target file

The target markdown file usually already has YAML frontmatter. Read it first:

```
cat "<target_path>"
```

### Step 2: Extract PDF text

Use `terminal` or `execute_code` to extract:

```python
import pymupdf
doc = pymupdf.open('<pdf_path>')
out = []
for i in range(len(doc)):
    out.append(f'--- PAGE {i+1} ---')
    out.append(doc[i].get_text())
# Save to temp file
with open('/tmp/<name>_raw.txt', 'w') as f:
    f.write('\n'.join(out))
```

For large PDFs (>10 pages), save to temp file and read in chunks via `read_file`. Use `read_file` with offset/limit pagination to page through the extracted text.

### Step 3: Translate section by section

Parse the extracted text to identify paper structure:
- Title, authors, affiliations
- Abstract / Summary
- Introduction
- Results (with subsections)
- Discussion
- Methods
- References (usually just note count, don't translate)

Then translate each section following the 8 formatting rules above.

### Step 4: Write the complete file

**CRITICAL**: The target file has existing frontmatter. You MUST:
1. Read the existing content first
2. Use `write_file` to write the COMPLETE file (existing frontmatter + new translation)

Do NOT use heredoc append (`cat >> ... << 'EOF'`) — it can timeout on large content.
Do NOT use `patch` to append — it's fragile for large additions.
Do NOT use `terminal` with `python3 -c "..."` for large translations — it can timeout or get BLOCKED.

The best approach is `execute_code` with `hermes_tools`:

```python
from hermes_tools import read_file, write_file

existing_content = read_file(target_path)["content"]
translation = "..."  # full translated content
write_file(target_path, existing_content + "\n\n---\n\n" + translation)
```

This avoids terminal timeouts entirely — `execute_code` runs with a 5-minute timeout and 50KB stdout cap, which is sufficient for any single paper translation.

### Step 5: Verify

```bash
# Check line count, heading levels, Figure references, abbreviations preserved
wc -l "<target_path>"
grep -n "^#" "<target_path>"
grep -c "Fig\.\|Figure" "<target_path>"
```

## Zotero Storage Paths

User's Zotero PDFs are typically at:
`~/Zotero/storage/<HASH>/<Author et al. - Year - Title>.md`

Target Obsidian notes are at:
`~/Work/luosg/work/笔记/Wiki/文献阅读笔记/文献/<@citationKey>.md`

## Translation Quality Notes

- Preserve technical precision — don't oversimplify domain terminology
- For genomics/bioinformatics terms, keep English in parentheses on first use if helpful
- Method sections: translate procedures faithfully but keep reagent names, concentrations, and catalog numbers in English
- Figure legends: translate the narrative but keep axis labels, abbreviations, and statistical annotations as-is

## Chinese Thesis Docx Generation

For generating Chinese academic theses (硕士/博士论文) as .docx files, see [references/chinese-thesis-docx.md](references/chinese-thesis-docx.md). Key: use direct python-docx script, not the JSON spec approach from the `docx` skill — the JSON approach breaks with large Chinese text containing special characters.

## Pitfalls

1. **Terminal timeout**: `terminal` commands with large Python -c strings (especially embedding full translations) can timeout or get BLOCKED. Always use `execute_code` with `hermes_tools` for the read+write step — it runs with a 5-minute timeout and handles large content reliably.
2. **Heredoc timeout**: Large heredocs in `terminal` can timeout. Always use `write_file` instead.
3. **Heading level**: User explicitly wants `###` as max level. The existing note may have `## 主要内容` — do NOT change existing headings, only ensure new translation starts at `###`.
4. **Frontmatter preservation**: NEVER overwrite or modify the YAML frontmatter. Read it, keep it, append after it.
5. **Read-before-write**: When the file already exists, MUST read it before writing. `write_file` overwrites everything.
6. **PDF text extraction noise**: Academic PDFs have page headers/footers (journal name, page numbers, copyright). Strip these during translation — don't translate them.
7. **Formula rendering**: Check that `$` and `$$` are properly paired. Inline math like `$\alpha = \beta = 10$` not `$\alpha$ = $\beta$ = 10.
8. **Table translation**: When translating tables, preserve the original structure. Use markdown tables for simple data. Keep numeric data, p-values, and statistical annotations in their original form. Translate only the row/column headers and descriptive text.
9. **Long papers**: For papers >10 pages, the full translation of all sections (abstract through methods) can be very large. Write the entire translation in one `execute_code` call — do NOT split across multiple terminal calls.
10. **Wrong SQL in `_translation_progress.md` examples**: The example `WHERE itemData.fieldID = 64` is broken in user's actual Zotero DB — returns no citekey rows. The verified-working query binds citekey as a parameter against `itemDataValues.value` directly:
    ```python
    cur.execute("""
        SELECT id.itemID, ia.parentItemID, ia.path
        FROM itemData id
        JOIN itemDataValues v ON id.valueID = v.valueID
        JOIN itemAttachments ia ON ia.parentItemID = id.itemID
        WHERE v.value = ? AND ia.path LIKE '%.pdf'
    """, (citekey,))
    ```
    When delegating PDF lookup to a subagent, **always tell it the working query upfront** — never make it rediscover the workaround.
11. **Concurrent subagent dispatch >2 → silent partial failure**: `delegate_task` with 4 concurrent leaf subagents each running 5 papers caused 18/20 papers to silently fail — only 2 of 20 PDFs produced output files. The subagents reported `dispatched` status and then the orchestrator received no completion messages (only the first subagent timed out at 420s). The remaining files were never written and no error surfaced.
    - **Limit concurrent subagents to 2**, each with ≤3 papers
    - **Always re-stat files in the orchestrator after subagents finish** — subagent self-reports are not trustworthy for file existence (they may claim "all done" while some files are missing)
    - **Verify on disk before claiming batch complete**: glob the target dir after each batch, check `os.path.getsize(p) > 5_000` per file, only then dispatch the next batch
12. **Progress file mutation timing**: Subagents must `write_file` each translated note first, then `stat` verify, and only after ALL papers in their batch are confirmed on disk, append to `_translation_progress.md` once at the end. Per-paper progress-line edits invite race conditions when multiple subagents share the same progress file.
13. **`_translation_progress.md` is NOT a reliable source of truth for current progress**. Its header counts ("已完成 (N 篇)", "待翻译 M 篇") and `[x] @citekey` markers lag reality by hundreds of papers because (a) subagents may write the .md but fail to append the progress line, (b) human manual edits to Obsidian skip the progress file entirely, (c) earlier sessions left stale section headers. Real progress is **derived**, not read. The canonical formula:
    - **Total corpus** = unique citekeys in `My Library.bib` (`grep -E '^@\w+\{' ... | sed -E 's/^@\w+\{//; s/,$//'`)
    - **Actually translated** = `@citekey.md` files present in Obsidian notes dir (`ls @*.md`)
    - **Genuinely remaining** = `comm -23 <bib_keys> <obsidian_keys>` — typically 0-10 citekeys once a corpus is "done"
    - **Orphan notes** = `comm -13 <obsidian_keys> <bib_keys>` — citekey was renamed (a→b suffix), deleted, or never existed; flag for cleanup, don't translate
    - The script [scripts/translation-status.sh](scripts/translation-status.sh) computes all three numbers in one shot. Run it before answering any "what's the translation progress?" question.

## Verification Contract (Orchestrator-Side)

After each batch of subagents reports completion, the orchestrator MUST verify on disk before claiming success to the user:

```python
import os
notes_dir = '/home/luosg/Work/luosg/work/笔记/Wiki/文献阅读笔记/文献/'
for ck in batch:
    p = os.path.join(notes_dir, f'@{ck}.md')
    assert os.path.exists(p), f'missing: {ck}'
    assert os.path.getsize(p) > 5000, f'too small ({os.path.getsize(p)} B): {ck}'
    with open(p) as f:
        head = f.read(200)
    assert head.startswith('---'), f'no frontmatter: {ck}'
    assert '### 摘要' in head, f'no summary heading: {ck}'
```

If verification fails for any paper, redispatch that specific citekey as a single-paper task (not a batch) — do not retry the whole batch.

## Templates

For the working PDF-lookup SQL and the progress-file schema, see [references/zotero-pdf-lookup.md](references/zotero-pdf-lookup.md).
