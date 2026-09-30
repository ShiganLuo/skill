# Case study: Zotero-Jsa `Bibliography Entry` style interference

Concrete worked example showing the full debugging path. Read this alongside SKILL.md for the generic workflow.

## Reported symptom

> "WPS 的 zotero 插件刷新老是干扰文档的样式"

User followed up: "刷新后段落间距/标题样式变了".

## Debugging path

1. **Locate the add-in install.** `~/.local/share/Kingsoft/wps/jsaddons/Zotero-Jsa_1.0.0/`. The plugin is `Zotero-Jsa.dotm` (44 KB) plus a `js/` directory of helper scripts.

2. **Unpack the dotm and confirm JDEData.bin is text.** `file` reports it as "XML document" — verify by `head -c 500`.

3. **Decode all `<codetext>` blocks.** There are 4 of them (sizes 1186 / 16750 / 77671 / 13875 bytes encoded). Concatenate the decoded forms before searching.

4. **First grep — find obvious targets.** Searched for `Bibliography Entry` and `pStyle`. Got 4 hits across `zc_insertBibEntries` and `zc_setBibStyle`.

5. **First hypothesis (WRONG).** "The plugin forces paragraph style `Bibliography Entry` on every refresh via `ftl.Style = geBibsy`". Patched that single line to a conditional:
   ```js
   if (ftl.Style.NameLocal !== styleName) ftl.Style = geBibsy;
   ```
   Tested → user reported **无效**.

6. **Second grep — find style-definition writes.** Searching `paraFormat.FirstLineIndent` etc. revealed `zc_setBibStyle` was **rewriting the paragraph style definition itself** on every refresh (`style.ParagraphFormat.FirstLineIndent = ...`, `LeftIndent = ...`, `LineSpacing = ...`, `SpaceAfter = ...`). Not just the paragraph's `pStyle` reference — the actual style object.

7. **Correct fix.** No-op `zc_setBibStyle` entirely:
   ```js
   async function zc_setBibStyle(bibStyle) {
       // DISABLED: leave style untouched
       return true;
   }
   ```
   Plus disable the post-`try` block in `zc_insertBibEntries` that synced Normal-style font + alignment into the bibliography paragraphs (`ftl.Font.NameFarEast = normalFont.NameFarEast`, `ftl.ParagraphFormat.Alignment = ...`).

## The lesson

> When the user says "X gets overwritten on refresh", trace the entire refresh code path. The obvious write site (paragraph property assignment) is often **not** the culprit — there's another function that mutates the *style definition itself*, and `ftl.Style = myStyle` then propagates to every paragraph using that style.

Three distinct write sites in this add-in:

| Site | Trigger | What it writes |
|------|---------|----------------|
| `zc_insertBibEntries` try-block | insert bibliography | `ftl.Style = geBibsy` + `fmt.TabStops.ClearAll/Add` |
| `zc_insertBibEntries` catch-block (fallback) | same, if try fails | direct paragraph format: `fmt.FirstLineIndent`, `LeftIndent`, `LineSpacing`, `SpaceAfter` |
| `zc_insertBibEntries` post-try block | same | font sync: `ftl.Font.NameFarEast/NameAscii/NameOther/Name`; `ftl.ParagraphFormat.Alignment` |
| `zc_setBibStyle` | refresh | **rewrites the `Bibliography Entry` style definition**: `style.ParagraphFormat.FirstLineIndent/LeftIndent/LineSpacing/SpaceAfter/TabStops` |

The fourth row was the actual culprit. The first row's forced assignment only mattered if the user renamed the style to something else (then the patch was a no-op).

## Why "disable zc_setBibStyle" was safe

`zc_insertBibEntries` also runs on insert (not just refresh). It contains the `createAndInsertHtml(xmlStrs, range)` call that actually populates the bibliography field — that part must stay. Only the **post-HTML** style/font/alignment assignments need disabling. So the patch was:

```js
// keep createAndInsertHtml, then bail
return xmlStr.length;
```

instead of fully deleting the function.

## Backup discipline

Each iteration got a versioned backup:
- `~/Backups/zotero-jsa-20260916/Zotero-Jsa.dotm.orig` — pristine original
- `~/Backups/zotero-jsa-20260916-v2/Zotero-Jsa.dotm.before-zc_insertBibEntries` — after first patch
- `~/Backups/zotero-jsa-20260916-v3/Zotero-Jsa.dotm.before-finer-patch` — after disabling zc_setBibStyle

Each backup is independent and the deployment is overwritten; **do not trust a single backup dir** when iterating.

## Files modified

- `/home/<USER>/.local/share/Kingsoft/wps/jsaddons/Zotero-Jsa_1.0.0/Zotero-Jsa.dotm`

Backups: `/home/<USER>/Work/<USER>/Backups/zotero-jsa-<date>{,-v2,-v3}/`

Restore:
```bash
cp /home/<USER>/Work/<USER>/Backups/zotero-jsa-20260916/Zotero-Jsa.dotm.orig \
   /home/<USER>/.local/share/Kingsoft/wps/jsaddons/Zotero-Jsa_1.0.0/Zotero-Jsa.dotm
```

WPS restart required to pick up the change.