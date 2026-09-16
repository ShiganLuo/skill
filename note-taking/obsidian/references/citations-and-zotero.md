# Citations plugin and Zotero integration

## obsidian-citation-plugin

The Citations plugin reads a `.bib` file and generates literature notes from a Handlebars template.

### Plugin config location

`.obsidian/plugins/obsidian-citation-plugin/data.json`. Key fields:
- `citationExportPath` — path to the `.bib` file (e.g. `Zotero/My Library.bib`)
- `literatureNoteTitleTemplate` — e.g. `@{{citekey}}`
- `literatureNoteContentTemplate` — Handlebars template for the note body
- `markdownCitationTemplate` — citation format in markdown

### Triggering literature note creation

The plugin is `isDesktopOnly: true` — it requires the Obsidian GUI (`Cmd+P` → "Citations: Open literature note"). Hermes cannot invoke this directly. There is no CLI / URI-scheme entry point.

To preview what the plugin would generate without launching Obsidian, render the Handlebars template with Node:

```bash
cd /tmp && npm install handlebars
```

```javascript
const Handlebars = require("handlebars");
const fs = require("fs");
const data = JSON.parse(fs.readFileSync("data.json","utf8"));
Handlebars.registerHelper("zoteroSelectURI", function() {
  return `zotero://select/items/@${this.citekey}`;
});
const tpl = Handlebars.compile(data.literatureNoteContentTemplate);
console.log(tpl(ctx));  // ctx = {citekey, title, year, DOI, URL, abstract, entry:{author:[...]}}
```

### Template variable pitfalls

The plugin uses Handlebars but a naive Python reimplementation will diverge on nested `{{#if X}}{{else}}{{#if Y}}...{{/if}}{{/if}}` constructs. When rendering for preview, prefer Node + real Handlebars over a hand-rolled Python renderer. If you must hand-render, write the output to disk and inspect for stray `{{...}}` artifacts before declaring done.

## Zotero database schema

Zotero stores everything in `zotero.sqlite` (locked while Zotero runs — use `.bak` or `.1.bak` for read access).

### Useful queries

```sql
-- itemID → citekey (Better BibTeX writes to fieldID=64)
SELECT itemData.itemID, itemDataValues.value
FROM itemData
JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
WHERE itemData.fieldID = 64

-- parentItemID → PDF storage path
SELECT parentItemID, path FROM itemAttachments WHERE path LIKE '%.pdf'
-- path format: "storage:filename.pdf" — basename matches a file under Zotero/storage/<hash>/
```

The `<hash>` subdirectory name is internal to Zotero (not the citekey). To find a PDF on disk:

```python
for subdir in os.listdir(ZSTOR):
    cand = f"{ZSTOR}/{subdir}/{basename}"
    if os.path.exists(cand):
        return cand
```

### Schema traps

- `items` table has no `extra` or `citationKey` column — Better BibTeX stores citekey in `itemData` keyed by `fieldID=64`
- `itemData` stores `valueID`, not `value` directly — must join `itemDataValues`
- Better BibTeX tables (`betterbibtex_citekeys` etc.) do NOT exist in default Zotero schema — citekey lives in the regular `itemData` table
- `My Library.bib` (Better BibTeX export) IS the practical way to read citekey + metadata; the database is the source of truth for PDF locations

## Existing literature note format

The vault `Wiki/文献阅读笔记/文献/` has 244 notes. Two coexisting formats:

**A format** (95 notes, ~39%): multi-line authors, multi-line tags
```yaml
---
alias: <short title>
tags:
  - research
year: <year>
title: "<original title>"
container: "<journal>"
url: <DOI URL>
zotero: zotero://select/items/@<citekey>
authors:
  - "[[<Name>]]"
  - "[[<Name>]]"
---
```

**B format** (149 notes, ~61%): single-line authors `[ ... ]`, multi-line tags
```yaml
---
alias: <short title>
tags:
- research
year: <year>
title: "<original title>"
container: "<journal>"
url: <DOI URL>
zotero: zotero://select/items/@<citekey>
authors: [ "[[<Name>]]", "[[<Name>]]", ]
---
```

The Citations plugin's default template produces B format. New notes created via the plugin will be B format regardless of the user's historical mix.

## User literature-note translation rules

When translating English papers into Chinese literature notes for this user:

1. **Translate fully**: abstract, introduction, results, discussion, methods
2. **Preserve figure refs**: keep `Fig. 1`, `Fig. 2A`, `Table 1`, etc. with original numbering — translate captions but not the identifiers
3. **Don't translate abbreviations**: DDR, ROS, TDIS, hTERT, TERT, TERC, etc. stay in English
4. **Formulas**: inline `$...$`, block `$$...$$`, no stray `$`
5. **Markdown heading level**: highest heading is `###` — never use `#` or `##`
6. **One blank line between paragraphs** for breathing room
7. **No extra wikilinks** — don't add `[[...]]` that the user didn't write
8. **Preserve cross-references** with original `(Author et al., YEAR)` format

**Tag rule**:
- Review / 综述 paper → `tags: review`
- Research paper → `tags: research`

**Filename**: `@{citekey}.md`

**For truncated PDFs**: PDF text extraction via `read_file` truncates at ~100K chars. Long papers need multiple reads with `offset`. If content gets cut, append `……` (Chinese ellipsis) to mark the gap rather than fabricating.

**For methods sections missing**: Reviews often have no Methods section — don't fabricate one.

## Batch translation workflow

For batches of literature notes (50+ papers):

1. **Build the citekey → PDF path map first** (see schema above)
2. **Sort by PDF size ascending** — small PDFs are quick wins, fill the session with high-value completed work before hitting context limits
3. **Create a progress file** at `Wiki/文献阅读笔记/_translation_progress.md` with checkboxes so a future session can resume
4. **Stop at the first quality cliff** — context pressure causes translation drift (missed paragraphs, garbled references, hallucinated content). Better to write 5 perfect notes than 15 broken ones.
5. **Don't ask the user to manage context** — they shouldn't have to tell you to create a progress file or stop. Do it proactively.
