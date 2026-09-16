---
name: zotero-obsidian-literature
description: "Zotero-Obsidian lit notes & Citations plugin."
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Zotero, Obsidian, Citations, Better-BibTeX, BibTeX, citekey, Literature-Review, Bibliography]
    related_skills: [academic-paper-translation, bioinformatics-wiki, obsidian]
---

# Zotero <-> Obsidian Literature Notes

Workflows for managing academic literature notes that integrate Zotero (reference manager) with an Obsidian vault (knowledge base). The user has a specific setup; this skill documents the moving parts so future sessions can reason about it.

## User's Setup (verified)

| Component | Location |
|---|---|
| Zotero data dir | `~/Work/luosg/Zotero/` |
| Better BibTeX export | `~/Work/luosg/Zotero/My Library.bib` (also `我的文库.bib`) |
| Zotero item storage (PDFs) | `~/Work/luosg/Zotero/storage/<8-char-key>/` |
| Obsidian vault | `~/Work/luosg/work/笔记/` |
| Vault .obsidian dir | `~/Work/luosg/work/笔记/.obsidian/` |
| Citations plugin data | `~/Work/luosg/work/笔记/.obsidian/plugins/obsidian-citation-plugin/data.json` |
| Literature notes dir | `~/Work/luosg/work/笔记/Wiki/文献阅读笔记/文献/` |
| Wiki note filename | `@{citekey}.md` (Better BibTeX citekey, prefixed with `@`) |

The naming convention `@citekey.md` is the bridge between Zotero and Obsidian: citekey is what Better BibTeX generates, and the `@` prefix lets you glob easily (`@*.md`).

## Core Workflows

### 1. Map citekey <-> Wiki file <-> Zotero item

Three-way mapping is the foundation for any bulk operation:

```
Wiki filename (@adamsGeneticDeterminantsMicronucleus2024.md)
       |
       v
Better BibTeX citekey (adamsGeneticDeterminantsMicronucleus2024)
       |
       v
Zotero item (in zotero.sqlite, itemID)
       |
       v
.bib entry (@article{...}) with fields {title, author, year, journal, doi, url, abstract, ...}
```

**Pitfall - Zotero DB is locked while running**: `zotero.sqlite` is held by the running Zotero process. Use the auto-backup `zotero.sqlite.bak` or `.1.bak` for reads, OR copy the live DB to a temp file. Don't try to write to the live DB.

**Pitfall - Better BibTeX tables don't exist**: Newer Better BibTeX versions do NOT create `betterbibtex_citekeys` tables. citekeys live in `.bib` exports. Always parse `My Library.bib`, not `zotero.sqlite`.

**Pitfall - Author field encoding**: Better BibTeX encodes some names with `{...}` brackets (e.g., `{van der Weyden}`, `Olvera-Le{\\'o}n`). When emitting wikilinks `[[name]]`, strip the `{...}` wrappers and decode LaTeX escapes (`\\'o` -> `ó`). See scripts/parse_bib.py for the full logic.

### 2. Parse `My Library.bib` (don't use regex on raw bibtex)

The naive regex `field = {value}` fails on three things: (a) `{` inside `{value}` (curly-balanced bibtex), (b) bare values like `year = 2024` without braces, (c) `author = {Name1 and Name2 and Name3}` which must be split on ` and `.

The script `scripts/parse_bib.py` handles all three with a brace-stack parser and returns:
```python
entries[citekey] = {
    'entrytype': 'article' | 'book' | ...,
    'title': '...', 'year': '...', 'journal': '...',
    'doi': '...', 'url': '...', 'abstract': '...',
    'author': [{'family': 'Adams', 'given': 'D. J.'}, ...],
}
```

Run via `execute_code` (each call is fresh process, import the script each time).

### 3. Test Citations plugin template without GUI

The Citations plugin is `isDesktopOnly: true` - Hermes can't trigger it directly. To test what it WOULD render:

1. Read the actual template from `data.json` field `literatureNoteContentTemplate`
2. Install handlebars locally: `cd /tmp && mkdir cite-test && cd cite-test && npm init -y && npm install handlebars`
3. Write a node script that registers the `zoteroSelectURI` helper (the only custom helper the plugin ships), builds a context dict from a parsed bib entry, and renders
4. Compare output to an existing `@citekey.md` to validate

See `scripts/render_citation_template.js` for the working implementation. Pitfalls:

- **`entry.author` not `authors`**: The template uses `{{#each entry.author}}` - context key is nested under `entry`
- **`{{zoteroSelectURI}}` is a registered helper**, not a field - must register in node to replicate
- **Title capitalization changes**: BibTeX exporters capitalize titles (`Genetic Determinants...`). Real existing notes preserve original casing. This is a known divergence.
- **Author LaTeX escapes**: `\\'o` in bib becomes `ó` in Wiki. Template doesn't decode it; you must pre-clean the bib parse

### 4. Bulk frontmatter calibration

To align N existing `@citekey.md` notes to a new template format:

1. Build `citekey -> entry` map from `My Library.bib`
2. For each `@citekey.md` in `文献阅读笔记/文献/`:
   - Parse existing YAML frontmatter
   - Decide which fields to overwrite (year, title, url, doi) vs preserve (custom user content like `related::`, `affiliation::`)
   - Write back with `write_file` (full overwrite is cleaner than patch for frontmatter)
3. **Always read before write** - `write_file` overwrites silently

### 5. The 5 known template-vs-existing divergences

| Field | Existing convention | Citations template output |
|---|---|---|
| `tags:` | `- research` (1 item) | `- research\n- review` (hardcoded, both) |
| `title:` | raw title (no quotes) | `"Title"` (quoted, possibly capitalized) |
| `url:` | URL if available, DOI fallback | `URL if else DOI` (works correctly) |
| `authors:` | multi-line `  - "[[X Y]]"` | single-line `[ "..." ]` (template uses array form) |
| Special chars | decoded (e.g. `ó`) | raw LaTeX (`\\'o`, `&#x27;`) |

Before doing bulk recalibration, decide which side to align to. Default: align template to existing notes (since 243 notes already use the multi-line author format).

## Templates

See `templates/literature_note_frontmatter.yaml` for a clean YAML frontmatter spec the user prefers.

## References

- `references/bibtex_field_handling.md` - full list of fields Better BibTeX emits, common encodings, decoding recipes
- `references/citations_plugin_template.md` - the actual data.json template, with each Handlebars variable explained and a checklist of what's missing
- `references/zotero_sqlite_schema.md` - table layout (since you can't rely on `betterbibtex_citekeys` table existing)

## Pitfalls Summary

1. **Live Zotero DB is locked** - use `.bak` or copy to temp
2. **Better BibTeX may not have its own table** - parse `.bib`, not sqlite
3. **Author `{...}` wrappers and LaTeX escapes** - strip on parse
4. **Citations plugin needs GUI** - Hermes must render via handlebars in node
5. **Template format != existing notes format** - decide alignment direction before bulk ops
6. **Bare bibtex values** (year = 2024 without braces) - regex must handle
7. **Nested braces** (e.g. journal = {{Nat.}{Cell}{}}) - brace-stack parser, not regex
8. **`{{zoteroSelectURI}}` is a Handlebars helper**, not a field - register in node
