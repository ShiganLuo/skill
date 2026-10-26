---
name: thesis-chapter-review
description: Use when critiquing thesis chapters in 1.docx outlines.
---

# Reviewing thesis chapter drafts (1.docx)

User's thesis docx files (e.g. data/1.docx) carry section headings WITHOUT numeric numbers. To locate a section like "3.2.2.1", use the 引言 paragraphs' self-references (e.g. "先…看程序层面（3.2.2）") to map numbers onto titles, and confirm the mapping to the user before critiquing.

Read the docx with read_file (auto-extracts text); critique from the extracted text.

## Review checklist (report problems grouped, root cause first)

1. Inference validity: does conclusion strength match evidence? Flag conclusions drawn without statistical tests (n, test, effect size), claims where high pathway activity is read as "more stable" (could be compensatory response = higher demand), and "cross-species conservation" claimed from separate labs/batches (batch confound not decoupled).
2. GSVA/score comparability: cross-dataset score comparison needs within-dataset normalization; flag if unstated.
3. Sample exclusion: post-hoc QC exclusions (low score found first, justification searched after) need a pre-declared rule; flag self-contradictory wording ("判定…可能"); long QC defense belongs in appendix, one sentence + pointer in text.
4. Tables: broken/incomplete entries (unclosed parentheses, missing full names), unit plausibility (inhibitor doses are µM/nM, not mM), inconsistent granularity across rows, missing control columns.
5. Text hygiene: draft leftovers ("图X：A或B" undecided alternatives), missing punctuation between clauses, doubled spaces, lowercase tool names (reactome -> Reactome).
6. Citations: check the cited paper actually supports the claim (e.g. a Hallmark-collection paper cited for custom curated gene sets — cite the MSigDB main reference instead); per-model claims need per-model citation numbers.
7. Structure: result sections that reference a layer of evidence with no preceding section establishing it (e.g. "transcriptional effects of variants" without a variant-characterization section before it).

## Output style

Chinese, numbered problems grouped by 类别 (推断逻辑 / 表格 / 文字与引用 / 结构), each with line-level evidence. State the section-number mapping assumption explicitly at the top. Do not rewrite the text unless asked.
