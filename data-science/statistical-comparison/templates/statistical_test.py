#!/usr/bin/env python3
"""
Statistical significance test for comparing two groups of data.

Features:
- Automatic normality test (Shapiro-Wilk)
- Automatic homogeneity of variance test (Levene)
- Automatic selection of appropriate statistical test
- Support for both paired and independent samples
"""

from __future__ import annotations
from typing import List, Tuple, Dict, Any
import numpy as np
from scipy import stats


def check_normality(data: List[float], alpha: float = 0.05) -> Tuple[bool, float, str]:
    """Check if data follows a normal distribution using Shapiro-Wilk test."""
    if len(data) < 3:
        return False, 0.0, "Sample size too small (n < 3)"
    stat, p_value = stats.shapiro(data)
    is_normal = p_value > alpha
    msg = f"{'Normal' if is_normal else 'Not normal'} (Shapiro-Wilk p={p_value:.4f})"
    return is_normal, p_value, msg


def check_equal_variance(group1: List[float], group2: List[float], alpha: float = 0.05) -> Tuple[bool, float, str]:
    """Check if two groups have equal variances using Levene's test."""
    stat, p_value = stats.levene(group1, group2)
    equal = p_value > alpha
    msg = f"{'Equal' if equal else 'Unequal'} variances (Levene p={p_value:.4f})"
    return equal, p_value, msg


def compare_groups(
    group1: List[float],
    group2: List[float],
    paired: bool = False,
    alpha: float = 0.05,
    verbose: bool = True
) -> Dict[str, Any]:
    """Compare two groups with automatic test selection."""
    if len(group1) < 2 or len(group2) < 2:
        raise ValueError("Each group must have at least 2 data points")

    g1, g2 = np.array(group1, dtype=float), np.array(group2, dtype=float)
    g1_mean, g1_std = np.mean(g1), np.std(g1, ddof=1)
    g2_mean, g2_std = np.mean(g2), np.std(g2, ddof=1)

    # Assumption checks
    g1_normal, _, _ = check_normality(g1, alpha)
    g2_normal, _, _ = check_normality(g2, alpha)
    both_normal = g1_normal and g2_normal

    if both_normal:
        equal_var, _, _ = check_equal_variance(g1, g2, alpha)
    else:
        equal_var = False

    # Test selection
    if paired:
        if both_normal:
            test_name = "Paired t-test"
            statistic, p_value = stats.ttest_rel(g1, g2)
            effect_size = np.mean(g1 - g2) / np.std(g1 - g2, ddof=1)
        else:
            test_name = "Wilcoxon signed-rank test"
            statistic, p_value = stats.wilcoxon(g1, g2)
            effect_size = statistic / (len(g1) * (len(g1) + 1) / 2)
    else:
        if both_normal:
            if equal_var:
                test_name = "Independent t-test"
                statistic, p_value = stats.ttest_ind(g1, g2, equal_var=True)
            else:
                test_name = "Welch's t-test"
                statistic, p_value = stats.ttest_ind(g1, g2, equal_var=False)
            pooled_std = np.sqrt(((len(g1)-1)*g1_std**2 + (len(g2)-1)*g2_std**2) / (len(g1)+len(g2)-2))
            effect_size = (g1_mean - g2_mean) / pooled_std
        else:
            test_name = "Mann-Whitney U test"
            statistic, p_value = stats.mannwhitneyu(g1, g2, alternative='two-sided')
            u1 = statistic
            u2 = len(g1) * len(g2) - u1
            effect_size = 1 - (2 * max(u1, u2)) / (len(g1) * len(g2))

    abs_eff = abs(effect_size)
    effect_interp = "negligible" if abs_eff < 0.2 else "small" if abs_eff < 0.5 else "medium" if abs_eff < 0.8 else "large"
    significant = p_value <= alpha

    result = {
        'test_name': test_name,
        'statistic': float(statistic),
        'p_value': float(p_value),
        'significant': significant,
        'alpha': alpha,
        'group1_mean': float(g1_mean), 'group2_mean': float(g2_mean),
        'group1_std': float(g1_std), 'group2_std': float(g2_std),
        'effect_size': float(effect_size),
        'effect_size_interpretation': effect_interp,
        'interpretation': f"{'IS' if significant else 'is NO'} significant difference (p={p_value:.4f})"
    }

    return result
