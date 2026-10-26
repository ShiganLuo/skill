# Resume CSS Techniques

## Label Justify in Tables

Short labels (2-4 chars) look uneven left-aligned. Force justify:

```css
.skills-table .label {
  width: 60px;
  font-weight: 700;
  white-space: nowrap;
  padding-right: 6px;
  text-align: justify;
  text-align-last: justify;
}
.skills-table .label::after {
  content: "";
  display: inline-block;
  width: 100%;
}
.skills-table .label span::after {
  content: ":";
  margin-left: 1px;
}
```

HTML: `<td class="label"><span>Data Analysis</span></td>`

Pitfall: without `<span>`, the `::after` colon breaks the justify trick.

## Font Scale System

| Tier | CN | EN | Usage |
|------|-----|-----|-------|
| Title | 10pt | 9.5pt | Section headers |
| Subtitle | 9pt | 8.5pt | Company, project, role |
| Body | 8pt | 7.5pt | Descriptions, bullets |
| Emphasis | 8.5pt | 8pt | Summary only |

English needs ~0.5pt smaller than Chinese (Latin text runs wider).

Inherit from `body { font-size }` — only declare explicit sizes on
elements that differ. Removes 20+ redundant declarations.

## Line Height

Use ONE value on body (`line-height: 1.4`). Remove ALL per-element
overrides. Exception: summary can use 1.45 if needed.

## Print Media Pitfall

Chrome headless **applies** `@media print`. If you shrink fonts there,
the PDF renders at the smaller size — different from browser preview.

```css
@media print {
  .header-photo { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
/* Do NOT override font-size or line-height in print media */
```

## Spacing Balance

Resumes with dense front + light back look unbalanced with equal margins.
Use inline `style="margin-top:Npx"` on section titles:

- Front (dense): `margin-top: 3px`
- Back (sparse): `margin-top: 8px`
