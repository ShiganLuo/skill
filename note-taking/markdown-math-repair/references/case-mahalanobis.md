# Case: 马氏距离 section repair (2026-10-25)

File: `Wiki/ScienceEngineering/DataScience/MachineLearning/数学基础/相似度计算.md`,
section `### 马氏距离` (lines ~224–399). Trigger: user asked to "修复马氏距离
小节的各种符号和公式，数字".

## Defects found (all classes fired at once — good regression fixture)

1. **15× `\sum` where `\Sigma` meant** — covariance matrix rendered as giant
   summation signs in every formula: 2 definition formulas, the Σ_F derivation
   chain (4), the big align derivation (4+), 2 final formulas, plus 1 Unicode
   `ΣF` in prose.
2. **Missing `^2` on first term** of the standardization sum:
   `(\frac{f_1-\mu F_1}{\sqrt \lambda_1})+…^2+…^2` — only the first term.
3. **`\sum^{-1}{X}`** — invalid grouping, X escapes the superscript.
4. **Coordinate-space mismatch**: "如果x是列向量" block had LHS `d_m²(f,μ_F)`
   but RHS in x-space.
5. **Typo `x=(x1,x2,…,x3)`** — last index should be `x_m`.
6. **Flattened numbers** (NOT wrong numbers): `√52+102=√125`,
   `√102+12=√101`, `√502+102=√2600`, `√1002+12=√10001` →
   `\sqrt{5^2+10^2}` etc. Arithmetic verified: 125 ✓, 101 ✓, 2600 ✓,
   10001 ✓, and the narrative (AB>CD then CD>AB) holds. Only notation fixed.
7. **`σ21` / `σ22`** → `\sigma_1^2` / `\sigma_2^2`.
8. **Blockquote fractions collapsed**: `E(x∗)=E[x−E(x)√D(x)]=1√D(x)E[…]`
   → `\dfrac` forms.
9. **Concept-in-wording**: "协方差矩阵是单位向量…各维度独立同分布" →
   "单位矩阵 $\boldsymbol{I}$（互不相关且方差相同）".
10. Minor: `如x所示`→`如下图所示`, `？，` double punctuation,
    "缩放特征值倍" → "除以 $\sqrt{\lambda_i}$ 缩放" (original contradicted
    the derivation that follows).

## Execution notes

- First full-file `read_file` dropped a blank line → every line number below
  it was off by one → first 24-hunk patch failed atomically at hunk 3
  (blank line between `$$…$$` and 其中). Nothing was modified (atomic
  rollback). Targeted `read_file(offset, limit)` re-reads of all three
  regions → one clean retry.
- The patch failure's "Did you mean" excerpt showed NEW text from hunks
  1–2 (in-memory post-hunk state), which confirmed atomic semantics.
- Final verification: 75 math spans, 0 unbalanced braces; environments
  (bmatrix/align/pmatrix ×6) all paired; 0 leftover `\sum`/Unicode Σ/√
  in section; 15 correct `\Sigma` in section.
