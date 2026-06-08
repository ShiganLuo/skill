---
name: statistical-comparison
description: Compare two groups for statistically significant differences with automatic test selection and visualization. Covers data loading, filtering, normality checks, and publication-quality plots.
triggers:
  - "compare two groups"
  - "significant difference"
  - "统计检验"
  - "显著性差异"
  - "t-test"
  - "Mann-Whitney"
  - "boxplot comparison"
  - "violin plot"
  - "mapping rate"
  - "compare samples"
---

# Statistical Comparison of Two Groups

Automated workflow for comparing two groups with appropriate statistical tests and visualization.

## Workflow Pattern

1. **Load data** → pandas DataFrame from TSV/CSV
2. **Filter** → subset by criteria (project, sample type, etc.)
3. **Check assumptions** → normality (Shapiro-Wilk), equal variance (Levene)
4. **Select test** → automatic based on assumption checks
5. **Visualize** → boxplot, violin, bar chart with significance annotations

## File Structure

```
project/
├── statistical_test.py   # Core comparison functions
├── plot_comparison.py    # Visualization functions
└── prepare_data.py       # Data loading + integration
```

## Key Functions

### compare_groups(group1, group2, paired=False, alpha=0.05, verbose=True)
Returns dict with: test_name, statistic, p_value, significant, effect_size, interpretation.

Automatic test selection logic:
- Both normal + equal variance → independent t-test
- Both normal + unequal variance → Welch's t-test
- Not normal → Mann-Whitney U test
- Paired + normal → paired t-test
- Paired + not normal → Wilcoxon signed-rank test

### plot_comparison(result, title, save_path, ...)
Three plot types:
- `plot_comparison()` — boxplot + jittered points + significance bracket
- `plot_comparison_with_violin()` — violin + embedded box
- `plot_mean_comparison()` — bar chart with error bars

### prepare_data(file_path, project_keyword, sample_types, ...)
Integrates everything: load → filter → compare → plot. Parameters:
- `plot=True/False` — whether to generate figures
- `plot_types=("box", "violin", "bar")` — which plots
- `save_dir` — output directory
- Returns dict with `figures` and `figure_paths` keys

## Significance Annotation Convention

```
p < 0.001 → "***"
p < 0.01  → "**"
p < 0.05  → "*"
p >= 0.05 → "ns"
```

## Effect Size Interpretation (Cohen's d)

| |d| | Interpretation |
|------|----------------|
| < 0.2 | negligible |
| 0.2-0.5 | small |
| 0.5-0.8 | medium |
| >= 0.8 | large |

## Pitfalls

- **Sample size**: Each group needs >= 2 samples. For n < 20, normality tests have low power — consider non-parametric by default.
- **Missing data**: Always convert to numeric with `errors='coerce'` then dropna. TSV files often have empty strings, not NaN.
- **Encoding**: Chinese data files may be GBK-encoded. Try UTF-8 first, fallback to GBK.
- **matplotlib backend**: Use `matplotlib.use('Agg')` for non-interactive saving. Don't call `plt.show()` in library code.
- **seaborn import**: Import seaborn before setting style. `sns.set_style("whitegrid")` must come before figure creation.
- **Chinese font with seaborn** (CRITICAL): `sns.set_style("whitegrid")` **resets** matplotlib's `rcParams`, including font settings. Setting `plt.rcParams["font.sans-serif"]` before `sns.set_style()` has NO effect. Solution: (1) use `configure_chinese_font()` first, (2) call `sns.set_style()`, (3) call `apply_font_after_style(selected_font)` to re-apply, (4) use `FontProperties(family=selected_font)` explicitly on each text element (`set_xticklabels`, `set_xlabel`, `set_ylabel`, `set_title`, `ax.text`). See `templates/plot_comparison.py` for the full pattern.
- **Violin plot KDE collapse**: `ax.violinplot()` can produce collapsed/truncated KDE when data has few points or narrow range. Use `sns.violinplot()` instead with `cut=0` (don't extend beyond data range) and `bw_adjust=0.8` (smoother KDE). Seaborn uses 0-based x positions, so all annotations must match (bracket coords, scatter positions, text positions).
- **Annotation consistency across chart types**: ALL chart types (boxplot, violin, bar) must display the same statistical info: p-value, effect size, and test name. Missing annotations in some charts is a bug. Always add `effect_text` and `test_text` to every chart.
- **Text positioning with axes transform**: Use `transform=ax.transAxes` with normalized coordinates (0-1) for metadata text to avoid overlap with data-space elements. Convention: effect_text at `(0.98, 0.98)` (top-right), test_text at `(0.02, 0.02)` (bottom-left). This prevents text from being hidden behind data points or error bars.

## Dependencies

```bash
pip install numpy scipy matplotlib seaborn pandas
```

## Typical Usage (Bioinformatics QC)

```python
from prepare_data import prepare_data

result = prepare_data(
    "RNAseq.tsv",
    project_keyword="立康",
    sample_types=("组织", "石蜡包埋组织"),
    plot=True,
    save_dir="./output"
)

# Access results
print(result['comparison']['p_value'])
print(result['comparison']['interpretation'])
print(result['figure_paths'])
```