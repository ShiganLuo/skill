---
name: markdown-math-repair
description: Use when repairing mangled LaTeX math in markdown notes.
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [latex, markdown, obsidian, mathjax, repair, notes]
    related_skills: [obsidian, safe-file-editing, visual-render-verification]
---

# Markdown Math Formula Repair

Notes copied from web pages, forums (知乎/CSDN/blog), or old exporters routinely
arrive with LaTeX that renders wrong or not at all. This skill is the damage
catalog + repair workflow. Companion to the `obsidian` skill (vault mechanics)
and `safe-file-editing` (patch mechanics).

## When to Use

- User asks to "修复公式 / 修复符号 / fix the math" in a vault note, wiki page,
  or any markdown with `$…$` / `$$…$$` blocks
- Formulas display but look wrong: giant summation signs where a matrix
  should be, digits where exponents should be

## Damage-pattern catalog

| Symptom in note | Intended meaning | Detection |
|---|---|---|
| `\sum^{-1}`, `\sum_X`, `\sum_F` in matrix/covariance context | `\Sigma^{-1}`, `\Sigma_X`, `\Sigma_F` | `\sum` adjacent to `^{-1}` or `_[A-Z]` where a matrix is meant |
| Unicode Σ/μ/σ/λ glued to indices: `ΣX=(μX1,…)` | `$\Sigma_X=(\mu_{X_1},…)$` | `Σ[A-Z]`, `μ[FX]\d` |
| Flattened superscripts: `√52+102=√125`, `σ21` | $\sqrt{5^2+10^2}$, $\sigma_1^2$ | `√\d+\+\d+`, `σ\d\d` |
| Flattened fractions: `E[x−E(x)√D(x)]=1√D(x)E[…]` | `\dfrac{x-E(x)}{\sqrt{D(x)}}` | `√D(` in prose/blockquote |
| Broken LaTeX grouping: `\sum^{-1}{X}` | `\Sigma_X^{-1}` | `^{-1}{` |
| First term of a sum missing `^2` while siblings have it | all terms squared | compare term patterns inside one align block |
| LHS/RHS coordinate-space mismatch (`d²(f,μ_F)` = x-space formula) | same space on both sides | eyeball derivation chains |
| Bare HTML-scraped formula lines: combining macron `x¯`, `x1¯−x2¯` | `$\overline{x}$`, `$\overline{x_1}-\overline{x_2}$` | `¯` (U+0304/FEFF¯) outside `$…$` |
| Radical flattened to trailing √ with overline as minus run: `sd(x)/n−−√`, `s2pn1+s2pn2−−−−−−√` | `$sd(x)/\sqrt{n}$`, `$\sqrt{s_p^2/n_1+s_p^2/n_2}$` | a run of `−` immediately before a trailing `√` |
| Doubled equals in prose math: `SEDM==sdn√` | `SEDM = \frac{sd}{\sqrt{n}}` | `==` inside scraped text |
| Flattened sub+sup digits: `s21`, `n1+n2−2` | `$s_1^2$`, `$n_1+n_2-2$` | digit-digit adjacency in prose |
| Wrong LHS symbol: standardized variable labeled `μ = (x̄−μ)/(σ/√n)` | `$z = \frac{\bar x - \mu}{\sigma/\sqrt n}$` | read the sentence — the quantity being defined is a z-score, not μ |
| Reversed domain: `+∞<t<−∞` | `$-\infty < t < +\infty$` | eyeball every `<`-chain domain |
| Wording that misstates the formula's condition (e.g. "协方差矩阵是单位向量" for the identity-matrix condition) | 单位矩阵 $\boldsymbol{I}$ | read the claim against the formula |

Rule of thumb: math that "renders but looks wrong" is usually a copy-paste
artifact — flattened super/subscripts are the #1 class. The NUMBERS are
usually right (the author computed them); verify the arithmetic
(5²+10²=125 ✓) and fix notation only, unless verification actually fails.
Do not "helpfully" recompute and change numbers that check out.

Numeric-output discipline (stats notes especially): R/Python output blocks
(t=22.813, df=149, CI bounds) are real computed results — before "fixing"
them, recompute once via terminal (`python3`/`Rscript`); if they check out,
leave them untouched and say so in the report. Only symbol/notation gets
repaired, never verified numbers.

Unicode minus (−, U+2212) vs ASCII hyphen: see safe-file-editing — the
patch tool fuzzy-matches them as equal, so a patch whose new_string
introduces `-` may silently write `−` into the file (and vice versa).
After any math-repair pass, sweep the touched section with
`grep -n '−' file` (scoped to the section if U+2212 is legitimate
elsewhere) and normalize inside `$…$` spans.

## Workflow

1. Read the target section with targeted `read_file(offset, limit)` — do NOT
   trust an earlier whole-file read for exact line content (a single dropped
   blank line breaks a dense patch; see safe-file-editing's multi-hunk
   discipline).
2. Enumerate EVERY defect class first and list them, so the fix pass is
   complete in one go.
3. Fix everything in ONE V4A `patch(mode='patch')` call — dozens of separate
   `replace` calls risk anchor collisions and half-applied state.
4. Verify programmatically (below), then re-read the hot spots.
5. Keep prose fixes minimal and report wording/concept fixes separately from
   symbol fixes.

## Verification script

```python
import re
lines = open(path, encoding='utf-8').read().split('\n')
sec = lines[sec_start:sec_end]               # section only
text = '\n'.join(sec)
spans = re.findall(r'\$\$(.+?)\$\$', text, re.S) + \
        re.findall(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', text, re.S)
bad = [s for s in spans if s.count('{') != s.count('}')]
envs = re.findall(r'\\begin\{(\w+)\}', text)
envbad = [e for e in envs
          if text.count(f'\\begin{{{e}}}') != text.count(f'\\end{{{e}}}')]
leftover = [(i, l) for i, l in enumerate(sec)
            if '\\sum' in l or 'Σ' in l or '√' in l
            or '¯' in l or '−' in l or '==' in l]
```

Expect zero unbalanced braces, zero unmatched environments, zero leftovers.
`\sum` is LEGITIMATE in correlation/distance-sum formulas elsewhere in the
same file — scope every scan to the repaired section, then grep the whole
file once more for accidental over-reach.

## Obsidian rendering note

MathJax handles `$$…$$`, `\begin{align}`, `pmatrix`, `cases`, `\boldsymbol`,
`\dfrac`, `\left(\right)` fine. Inside `>` blockquote lines prefer inline
`$…$` over `$$…$$` display blocks when in doubt.

## Reference

Session case log with a full worked example: `references/case-mahalanobis.md`.

Scraped-stats-note case (T-test/Z-test sections: bare HTML formulas,
μ-as-LHS error, reversed t-domain, and the patch-vs-Unicode-minus false
success loop): `references/case-ttest-ztest-scrape.md`.
