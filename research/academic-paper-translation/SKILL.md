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
