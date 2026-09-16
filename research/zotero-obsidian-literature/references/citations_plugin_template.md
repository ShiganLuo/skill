# obsidian-citation-plugin template reference

The plugin's template lives at:
`~/.obsidian/plugins/obsidian-citation-plugin/data.json`

Field: `literatureNoteContentTemplate` (Handlebars syntax).

## Available variables

| Variable | Source | Notes |
|---|---|---|
| `{{citekey}}` | Better BibTeX key | e.g. `adamsGeneticDeterminantsMicronucleus2024` |
| `{{title}}` | bib title | Often capitalized by Better BibTeX (e.g. "Genetic Determinants..."). Original case is lost. |
| `{{titleShort}}` | title truncated | Stops at first `: ? . !`, max ~50 chars. Often ends with a trailing space. |
| `{{year}}` | bib year | Bare number, no braces |
| `{{containerTitle}}` | journal/booktitle/publisher | First non-empty |
| `{{DOI}}` | bib doi | Without `https://doi.org/` prefix |
| `{{URL}}` | bib url | May be empty even when DOI exists |
| `{{abstract}}` | bib abstract | Often empty for older items |
| `{{zoteroSelectURI}}` | built-in helper | Returns `zotero://select/items/@<citekey>` |
| `{{#each entry.author}}...{{/each}}` | author array | Sub-fields: `{{given}}`, `{{family}}` |
| `{{#if X}}...{{/if}}` | conditional | |

## Default template (verbatim from user's data.json)

```handlebars
---
alias: {{titleShort}}
tags: 
- research
- review
year: {{year}}
title: "{{title}}"
container: "{{containerTitle}}"
url: {{#if URL}}{{URL}}{{else}}{{#if DOI}}https://doi.org/{{DOI}}{{/if}}{{/if}}
zotero: {{zoteroSelectURI}}
authors: [{{#each entry.author}} "[[{{given}} {{family}}]]",{{/each}}]
---
- [ ] 《{{title}}》[🆉]({{zoteroSelectURI}}) ^read

related:: 
affiliation:: 

---

- abbr.

#### comment

## 主要内容
```

## Known template bugs / divergences from existing notes

1. **`tags: review` is hardcoded** — applied to every entry even if it's an article. Should be conditional on entry type.
2. **`title` capitalization** — Better BibTeX capitalizes; existing notes preserve original. Not a bug per se but a divergence.
3. **`url` fallback** — `{{#if URL}}...{{else}}{{#if DOI}}...{{/if}}{{/if}}` works correctly. When both empty, the field becomes blank.
4. **`authors` array form** — template uses `[ "..." ]` (single line). Existing 243 notes use multi-line `- "[[...]]"`. To match existing: change `authors: [...]` to:
   ```
   authors:
   {{#each entry.author}}  - "[[{{given}} {{family}}]]"
   {{/each}}
   ```
5. **Author `{...}` wrappers not stripped** — names with curly-bracket-protected casing (e.g. `{van der Weyden}`) end up as `[[L. {van der Weyden}]]`. To fix: pre-clean in bib parser, or use a custom Handlebars helper.
6. **LaTeX accents not decoded** — `Olvera-Le{\\'o}n` -> `[[R. {Olvera-Le{\\&#x27;o}n}]]`. Should decode before wikilink.
7. **`titleShort` ends with space when title is long and stop-char found** — minor cosmetic.

## Suggested improved template

```handlebars
---
{{#if abstract}}abstract: "{{abstract}}"{{/if}}
alias: {{titleShort}}
tags:
  - {{entrytype}}
  - {{#if (eq entrytype "review")}}review{{/if}}
year: {{year}}
title: "{{title}}"
container: "{{containerTitle}}"
url: {{#if URL}}{{URL}}{{else}}{{#if DOI}}https://doi.org/{{DOI}}{{/if}}{{/if}}
zotero: {{zoteroSelectURI}}
authors:
{{#each entry.author}}  - "[[{{given}} {{family}}]]"
{{/each}}
---
- [ ] 《{{title}}》[🆉]({{zoteroSelectURI}}) ^read

related:: 
affiliation:: 

---

- abbr.

#### comment

## 主要内容
```

Note: `(eq ...)` and `{{#if (eq ...)}}` are NOT built-in Handlebars. The Citations plugin doesn't ship a comparison helper, so this improvement requires either a custom plugin or a different solution.

## Verification

Before changing the template, render it in node (see `scripts/render_citation_template.js`) and diff against an existing `@citekey.md` to confirm only intended changes.
