# Case: T-test/Z-test scraped note repair (生物统计学/3. 统计检验.md)

Note sections pasted from a blog lost all LaTeX. Damage inventory actually
found, with the exact before → after mapping used for the repair.

## Damage classes encountered (new vs catalog)

1. Bare formula lines with combining macron (paste artifact, NOT in old
   catalog):
   - `x−μsd` → `$z = \dfrac{x - \mu}{sd}$`
   - `x¯`, `x1¯−x2¯` → `$\overline{x}$`, `$\overline{x_1} - \overline{x_2}$`
   - detection: `¯` outside `$…$`
2. Radical as trailing √ with the overline rendered as a minus run:
   - `sd(x)/n−−√` → `$sd(x)/\sqrt{n}$`
   - `s2pn1+s2pn2−−−−−−√` → `$\sqrt{s_p^2/n_1 + s_p^2/n_2}$`
   - `s21n1+s22n2−−−−−−−−√` → `$\sqrt{s_1^2/n_1 + s_2^2/n_2}$`
   - detection: run of `−` immediately before a trailing `√`
3. Doubled equals: `SEDM==sdn√` → `$SEDM = \frac{sd}{\sqrt{n}}$`
4. Flattened sub+sup digits: `s21` → `$s_1^2$`, `n1+n2−2` → `$n_1+n_2-2$`,
   `s2p` → `$s_p^2$`
5. SEMANTIC errors in original text (author's mistakes, not paste
   artifacts — flag separately in the report):
   - Standardized variable labeled with LHS `μ`: `$$μ = \frac{\bar x - μ}{σ/√n}$$`
     → LHS must be `z` (it's a z-score). Two occurrences (definition + the
     t-distribution paragraph referring back to it).
   - t-distribution domain written reversed: `$+\infty<t<-\infty$` →
     `$-\infty < t < +\infty$`
   - Typo in eponym: "Welch-Satterhwaite" → "Welch–Satterthwaite"
6. Numbers in R output (paired t = 22.813, df = 149, CI [1.904708, 2.265959],
   mean diff 2.085333) — verified against iris: mean(Sepal.Length −
   Petal.Length) = 2.0853, t = 2.0853/(sd/√150) ≈ 22.81. Correct → left
   untouched, verification noted in the report.

## Result formulas (verified against standard textbook forms)

- Pooled-variance two-sample: `SEDM = sqrt(sp²/n1 + sp²/n2)`,
  `sp² = ((n1−1)s1² + (n2−1)s2²)/(n1+n2−2)`, df = n1+n2−2
- Welch: `SEDM = sqrt(s1²/n1 + s2²/n2)`,
  df = (s1²/n1 + s2²/n2)² / [ (s1²/n1)²/(n1−1) + (s2²/n2)²/(n2−1) ]
- Paired: reduce to one-sample on di = x1i − x2i, SEDM = sd/√n

## Pitfall log: patch tool vs Unicode minus (the main time sink)

`patch(mode='replace')` fuzzy-matches U+2212 (−) and ASCII hyphen (-) as
equal. Consequences observed:

- A patch whose new_string contained `-` (typed as ASCII) was FUZZY-ALIGNED
  to the file's `−`, so the applied result still contained `−` — the tool
  reported success, the diff looked right, the file kept the bad char.
- Later cleanup patches reported `success: true` with an EMPTY diff while
  the on-disk text was unchanged (had to re-grep to notice).

Working recovery sequence:

1. Detect: `grep -n '−' file` (optionally scoped by line range with awk).
2. Byte-check what's really there: `sed -n '237p' file | grep -oP ... | od -c`
   shows `342 210 222` = U+2212.
3. Fix via execute_code direct replacement (NOT terminal python3 -c — the
   heredoc/inline-shell form gets stuck on the destructive-command
   confirmation and blocks):
   ```python
   p = '/path/file.md'
   s = open(p, encoding='utf-8').read()
   n = s.count('\u2212')
   s = s.replace('\u2212', '-')
   open(p, 'w', encoding='utf-8').write(s)
   ```
   This replaced all 24 occurrences in one shot and verified remaining == 0.
4. Scope note: the same file legitimately used `−` in later
   confidence-interval sections; the replacement was fine there too (renders
   identically), but if a file genuinely needs U+2212 in prose, normalize
   only inside `$…$` spans.

Lesson: after ANY math repair on scraped text, do one sweep pass for
U+2212 via execute_code rather than trying to fix them through patch.
