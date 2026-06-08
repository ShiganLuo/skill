#!/usr/bin/env python3
"""
Visualization functions for statistical comparison results.
Provides boxplot, violin, and bar chart with significance annotations.

PITFALL: sns.set_style() resets rcParams font settings. Always:
1. Call configure_chinese_font() first
2. Call sns.set_style()
3. Call apply_font_after_style(selected_font) to re-apply
4. Use FontProperties explicitly on each text element
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
import seaborn as sns


def configure_chinese_font() -> str:
    """Configure a CJK-capable font for matplotlib and return selected font name."""
    candidates = [
        "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
        "Microsoft YaHei", "SimHei", "PingFang SC", "Heiti SC",
    ]
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    selected = ""
    for font_name in candidates:
        if font_name in available_fonts:
            selected = font_name
            break
    if selected:
        plt.rcParams["font.sans-serif"] = [selected, "DejaVu Sans", "Arial Unicode MS"]
    else:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.family"] = "sans-serif"
    return selected


def apply_font_after_style(selected_font: str) -> None:
    """Re-apply font settings after sns.set_style() which resets rcParams."""
    if selected_font:
        plt.rcParams["font.sans-serif"] = [selected_font, "DejaVu Sans", "Arial Unicode MS"]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["font.family"] = "sans-serif"


def _make_font_props(selected_font: str):
    """Create FontProperties for regular, bold, and title text."""
    if selected_font:
        font_prop = FontProperties(family=selected_font, size=12)
        font_prop_bold = FontProperties(family=selected_font, size=14, weight='bold')
        font_prop_title = FontProperties(family=selected_font, size=16, weight='bold')
    else:
        font_prop = FontProperties(size=12)
        font_prop_bold = FontProperties(size=14, weight='bold')
        font_prop_title = FontProperties(size=16, weight='bold')
    return font_prop, font_prop_bold, font_prop_title


def plot_comparison(
    result: Dict[str, Any],
    title: str = "Comparison",
    ylabel: str = "Value",
    figsize: Tuple[int, int] = (10, 7),
    palette: Tuple[str, str] = ("#3498db", "#e74c3c"),
    show_points: bool = True,
    show_stats: bool = True,
    save_path: Optional[str] = None,
    dpi: int = 300,
    verbose: bool = True
) -> plt.Figure:
    """Boxplot with jittered points and significance bracket."""
    # CRITICAL: configure font BEFORE sns.set_style() resets it
    selected_font = configure_chinese_font()

    group1_name = result['group1_name']
    group2_name = result['group2_name']
    group1_data = result['group1_data']
    group2_data = result['group2_data']
    comparison = result['comparison']

    # CRITICAL: re-apply font AFTER sns.set_style()
    sns.set_style("whitegrid")
    apply_font_after_style(selected_font)
    font_prop, font_prop_bold, font_prop_title = _make_font_props(selected_font)

    fig, ax = plt.subplots(figsize=figsize)

    # Box plot
    bp = ax.boxplot([group1_data, group2_data], positions=[1, 2], widths=0.6,
                    patch_artist=True, showmeans=True,
                    meanprops={"marker": "D", "markerfacecolor": "white", "markersize": 8},
                    medianprops={"color": "black", "linewidth": 2})

    for patch, color in zip(bp['boxes'], palette):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # Jittered points
    if show_points:
        for data, pos, color in zip([group1_data, group2_data], [1, 2], palette):
            jitter = np.random.uniform(-0.15, 0.15, size=len(data))
            ax.scatter(np.full_like(data, pos) + jitter, data, color=color,
                      alpha=0.6, s=50, edgecolors='black', linewidths=0.5, zorder=5)

    # CRITICAL: use fontproperties= for all text elements
    ax.set_xticks([1, 2])
    ax.set_xticklabels([f"{group1_name}\n(n={len(group1_data)})",
                        f"{group2_name}\n(n={len(group2_data)})"],
                       fontproperties=font_prop)
    ax.set_ylabel(ylabel, fontproperties=font_prop_bold)
    ax.set_title(title, fontproperties=font_prop_title, pad=20)

    # Significance annotation
    if show_stats:
        p_value = comparison['p_value']
        sig_stars = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
        effect_size = comparison['effect_size']
        effect_interp = comparison['effect_size_interpretation']
        y_max = max(max(group1_data), max(group2_data))
        y_min = min(min(group1_data), min(group2_data))
        y_range = y_max - y_min
        bracket_y = y_max + y_range * 0.15

        ax.plot([1, 1, 2, 2], [bracket_y, bracket_y + y_range*0.02, bracket_y + y_range*0.02, bracket_y],
                color='black', linewidth=1.5)
        ax.text(1.5, bracket_y + y_range*0.05, sig_stars, ha='center', fontsize=16, fontweight='bold')
        p_text = f"p = {p_value:.4f}" if p_value >= 0.001 else "p < 0.001"
        ax.text(1.5, bracket_y - y_range*0.03, p_text, ha='center', fontsize=11, style='italic')

        # Effect size + test name: use axes transform to avoid overlap with data
        effect_text = f"{comparison['effect_size_name']}: {effect_size:.2f} ({effect_interp})"
        ax.text(0.98, 0.98, effect_text, transform=ax.transAxes, fontsize=10,
                color='gray', ha='right', va='top', style='italic')
        test_text = f"Test: {comparison['test_name']}"
        ax.text(0.02, 0.02, test_text, transform=ax.transAxes, fontsize=9,
                color='gray', style='italic')

        ax.set_ylim(y_min - y_range*0.1, y_max + y_range*0.35)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight', facecolor='white')

    return fig


def plot_comparison_with_violin(
    result: Dict[str, Any],
    title: str = "Comparison",
    ylabel: str = "Value",
    figsize: Tuple[int, int] = (10, 7),
    palette: Tuple[str, str] = ("#3498db", "#e74c3c"),
    show_stats: bool = True,
    save_path: Optional[str] = None,
    dpi: int = 300,
    verbose: bool = True
) -> plt.Figure:
    """Violin plot with embedded box and significance bracket.

    PITFALL: ax.violinplot() collapses KDE with few points. Use sns.violinplot()
    with cut=0 and bw_adjust for better control.
    PITFALL: seaborn uses 0-based x positions, so all coordinates must match.
    """
    import pandas as pd

    selected_font = configure_chinese_font()

    group1_name = result['group1_name']
    group2_name = result['group2_name']
    group1_data = result['group1_data']
    group2_data = result['group2_data']
    comparison = result['comparison']

    sns.set_style("whitegrid")
    apply_font_after_style(selected_font)
    font_prop, font_prop_bold, font_prop_title = _make_font_props(selected_font)

    fig, ax = plt.subplots(figsize=figsize)

    # CRITICAL: sns.violinplot, not ax.violinplot (KDE collapse fix)
    df_plot = pd.DataFrame({
        'value': group1_data + group2_data,
        'group': [group1_name] * len(group1_data) + [group2_name] * len(group2_data)
    })
    sns.violinplot(data=df_plot, x='group', y='value', palette=palette,
                   cut=0, bw_adjust=0.8, inner='box', alpha=0.7, linewidth=1.5, ax=ax)

    # Seaborn uses 0-based positions for scatter
    for i, (data, pos, color) in enumerate(zip([group1_data, group2_data], [0, 1], palette)):
        jitter = np.random.uniform(-0.1, 0.1, size=len(data))
        ax.scatter(np.full_like(data, pos) + jitter, data, color=color,
                  alpha=0.6, s=40, edgecolors='black', linewidths=0.5, zorder=5)

    # Seaborn handles xticklabels automatically, but override with font
    ax.set_xticklabels([f"{group1_name}\n(n={len(group1_data)})",
                        f"{group2_name}\n(n={len(group2_data)})"],
                       fontproperties=font_prop)
    ax.set_xlabel("", fontproperties=font_prop_bold)
    ax.set_ylabel(ylabel, fontproperties=font_prop_bold)
    ax.set_title(title, fontproperties=font_prop_title, pad=20)

    # Significance annotation — 0-based positions for seaborn
    if show_stats:
        p_value = comparison['p_value']
        sig_stars = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
        effect_size = comparison['effect_size']
        effect_interp = comparison['effect_size_interpretation']
        y_max = max(max(group1_data), max(group2_data))
        y_min = min(min(group1_data), min(group2_data))
        y_range = y_max - y_min
        bracket_y = y_max + y_range * 0.15

        ax.plot([0, 0, 1, 1], [bracket_y, bracket_y + y_range*0.02, bracket_y + y_range*0.02, bracket_y],
                color='black', linewidth=1.5)
        ax.text(0.5, bracket_y + y_range*0.05, sig_stars, ha='center', fontsize=16, fontweight='bold')
        p_text = f"p = {p_value:.4f}" if p_value >= 0.001 else "p < 0.001"
        ax.text(0.5, bracket_y - y_range*0.03, p_text, ha='center', fontsize=11, style='italic')

        effect_text = f"{comparison['effect_size_name']}: {effect_size:.2f} ({effect_interp})"
        ax.text(0.98, 0.98, effect_text, transform=ax.transAxes, fontsize=10,
                color='gray', ha='right', va='top', style='italic')
        test_text = f"Test: {comparison['test_name']}"
        ax.text(0.02, 0.02, test_text, transform=ax.transAxes, fontsize=9,
                color='gray', style='italic')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight', facecolor='white')

    return fig
