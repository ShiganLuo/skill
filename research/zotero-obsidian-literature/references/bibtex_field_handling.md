# BibTeX field handling (Better BibTeX export)

Reference for what each Better BibTeX field looks like and how to handle it.

## Field-by-field

| Field | Type | Encoding | Notes |
|---|---|---|---|
| `title` | string | `{Title here}` | Often capitalized by exporter |
| `author` | string list | `{Family, Given and Family2, Given2 and ...}` | Bracket-wrapped surnames preserve casing |
| `year` | int | `2024` or `{2024}` | Bare or braced |
| `month` | string | `mar` or `{mar}` | Three-letter abbreviation |
| `journal` | string | `{Nature}` | Brace-wrapped |
| `volume` | int | `{627}` | |
| `number` | string | `{8002}` | May be int |
| `pages` | string | `{130--136}` | en-dash for ranges |
| `publisher` | string | `{Nature Publishing Group}` | |
| `issn` | string | `{1476-4687}` | |
| `isbn` | string | `{...}` | Books |
| `doi` | string | `{10.1038/...}` | No URL prefix |
| `url` | string | `{https://...}` | Often absent even when DOI exists |
| `urldate` | date | `{2025-09-22}` | ISO |
| `abstract` | string | `{...}` | Often empty for older imports |
| `keywords` | string list | `{word1; word2; word3}` | Semicolon-separated |
| `file` | string | `{:home/luosg/Zotero/storage/.../Adams - 2024 - Genetic determinants.pdf:application/pdf}` | Long path to attached PDF |
| `langid` | string | `{english}` | |
| `copyright` | string | `{...}` | |

## Special encoding cases

### Brace-protected casing in author names

Better BibTeX wraps surnames that should preserve their casing in `{...}`:

```
{van der Weyden}      -> surname: "van der Weyden" (casing preserved)
{de Lange}            -> surname: "de Lange"
{Olvera-León}         -> surname: "Olvera-León"
{Robles-Espinoza}     -> surname: "Robles-Espinoza"
```

When emitting wikilinks `[[name]]`, strip the `{...}` wrappers. Otherwise you get `[[L. {van der Weyden}]]` which Obsidian can't link.

### LaTeX accent escapes in names

```
Olvera-Le{\\'o}n      -> "Olvera-León"
M{\"u}ller            -> "Müller"
{Olvera-Le{\\'o}n}    -> surname "Olvera-León" after both unwrappings
```

The decoder in `scripts/parse_bib.py` handles the common ones (`\\'o` -> `ó`, `\\"u` -> `ü`, etc.). For full coverage, use a library like `pybtex` or `bibtexparser`.

### Author "and" separator

Author lists use ` and ` (lowercase, space-padded) between names:

```
{Adams, D. J. and Barlas, B. and McIntyre, R. E. and ...}
```

Split on ` and `, then on the FIRST `,` to get `family, given`. Some authors have multiple given names:
```
{Kentistou, K. A.}    -> given "K. A."
{Coelho, P. A.}       -> given "P. A."
```

Do not split on all commas — only the first.

### `file` field

The `file` field is one big string with a colon-prefixed path:

```
:home/luosg/Zotero/storage/24CK4HFV/Adams et al. - 2024 - Genetic determinants of micronucleus formation in vivo.pdf:application/pdf
```

Extract the path between the leading `:` and `:application/`:

```python
m = re.match(r':(.*?):application/', entry.get('file', ''))
if m:
    pdf_path = '/' + m.group(1)  # prepend / since the bib path is relative
```

The leading slash is missing from the bib export — Zotero uses `~/Zotero/storage/...` but Better BibTeX drops the leading slash.

### Multi-line bibtex

Some bibtex exporters wrap long author lists across lines:

```
author = {Adams, D. J. and
          Barlas, B. and
          McIntyre, R. E. and ...}
```

The brace-stack parser in `scripts/parse_bib.py` handles this correctly because it tracks `{}` depth, not lines.

## Common pitfalls

1. **Naive regex `= {([^}]*)}`** — fails on nested braces
2. **Splitting authors on every `,`** — wrong for given names with `K. A.` style
3. **Treating `file` as multiple files** — it's a single colon-encoded string
4. **Forgetting that `year` may not have braces** — `year = 2024` is valid bibtex
5. **HTML entity decoding** — `&#x27;` may appear in some bibtex exporters; treat as apostrophe
