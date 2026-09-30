---
name: html-resume
description: "Build HTML resumes exported to PDF via Chrome headless."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [resume, cv, html, css, pdf, chrome-headless, layout, typography]
---

# HTML Resume

Use when: building or editing HTML resumes/CVs, fixing resume typography,
syncing bilingual resumes, or adjusting resume spacing and font consistency.

Build A4 one-page resumes in HTML+CSS, exported to PDF via Chrome headless.

## References

- `references/css-techniques.md` — label justify, font scale, print media, spacing
- `references/content-patterns.md` — skills vs experience, summary, interests, education

## Quick CSS Checklist

1. Font scale: 3 tiers (10pt title / 9pt subtitle / 8pt body) + 8.5pt emphasis
2. Single `line-height` on body — no per-element overrides
3. No font-size changes in `@media print` (Chrome headless applies them)
4. Label justify: `text-align: justify` + `text-align-last: justify` + `::after` phantom line
5. English resumes: ~0.5pt smaller than Chinese equivalents

## Quick Content Checklist

1. Skills = capabilities, not project experiences
2. Summary = narrative arc (identity → competency chain → differentiator)
3. Interests = bare noun list, not sentences
4. Education = "Program Name（Degree Type）" format
