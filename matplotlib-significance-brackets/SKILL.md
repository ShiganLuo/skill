---
name: matplotlib-significance-brackets
description: Draw statistical significance brackets on matplotlib bar charts — multi-group support, pairwise chi2 testing, 宝盖头 style annotations with outward diagonal ticks.
tags: [matplotlib, plotting, statistics, visualization]
triggers:
  - significance bracket on bar chart
  - pairwise comparison annotation
  - 宝盖头 bracket style
  - chi2 contingency test on grouped bars
---

# Matplotlib Significance Brackets

Draw pairwise significance annotations on grouped bar charts. Supports N groups, broken axis, and the 宝盖头 (roof radical) bracket style.

## Core Pattern: Multi-Group Bar Width

```python
n_groups = len(group_order)
total_width = 0.8
bar_width = total_width / n_groups
offsets = [bar_width * (i - (n_groups - 1) / 2) for i in range(n_groups)]

for i, g in enumerate(group_order):
    ax.bar(x + offsets[i], pivot[g], bar_width, color=colors[g])
```

## Pairwise Chi2 with Degenerate Table Guard

```python
all_pairs: Dict[str, List[tuple]] = {}
for sv in pivot.index:
    pairs = []
    for i, g1 in enumerate(group_order):
        for g2 in group_order[i + 1:]:
            idx1 = list(group_order).index(g1)
            idx2 = list(group_order).index(g2)
            table = np.array([
                [pivot.loc[sv, g1], pivot[g1].sum() - pivot.loc[sv, g1]],
                [pivot.loc[sv, g2], pivot[g2].sum() - pivot.loc[sv, g2]],
            ])
            if table.min() < 0 or table.sum() == 0 \
               or (table.sum(axis=0) == 0).any() \
               or (table.sum(axis=1) == 0).any():
                continue
            try:
                _, p, _, _ = chi2_contingency(table)
            except ValueError:
                continue
            pairs.append((idx1, idx2, p_to_star(p)))
    all_pairs[sv] = pairs
```

## Auto-Detect Broken Axis

Don't always use broken axis. Only enable when the tallest bar is significantly higher than the rest:

```python
global_max = pivot.values.max()
sig_sv_list = [sv for sv, pairs in all_pairs.items()
               if any(s != "ns" for _, _, s in pairs)]
sig_max = pivot.loc[sig_sv_list].values.max() if sig_sv_list else np.median(pivot.values)

need_broken = use_broken_axis and (global_max > sig_max * 2.0)
```

When `need_broken=False`, fall back to a single axes — avoids bracket clipping issues.

## 宝盖头 Bracket Style (CORRECT)

User preference: horizontal line from bar1 center to bar2 center, with OUTWARD diagonal ticks `\` and `/` pointing at bar centers. NO vertical lines crossing through bars. ns labels SAME color (black) as stars, distinguished by font size/weight only.

```python
LEG_PT = 8    # initial gap from bar top to first bracket (display points)
TEXT_PT = 3   # text offset above bracket line (display points)

for i_sv, sv in enumerate(pivot.index):
    pairs = all_pairs.get(sv, [])
    if not pairs:
        continue
    y_base = max(pivot.loc[sv, g] for g in group_order)
    bracket_offset = 0.0

    for idx1, idx2, star in pairs:
        ax = ax_bottom if (need_broken and y_base <= low_max) else ax_top

        trans = ax.transData
        inv = ax.transData.inverted()

        _, y_disp = trans.transform((0, y_base))
        y_hat_disp = y_disp + LEG_PT + bracket_offset
        y_text_disp = y_hat_disp + TEXT_PT
        _, y_hat = inv.transform((0, y_hat_disp))
        _, y_text = inv.transform((0, y_text_disp))

        x1 = x[i_sv] + offsets[idx1]
        x2 = x[i_sv] + offsets[idx2]

        is_sig = star != "ns"
        fs = 12 if is_sig else 9
        fw = "bold" if is_sig else "normal"

        # 宝盖头 bracket as SINGLE POLYLINE (avoids line-cap overlap at junctions)
        tick_x = bar_width * 0.25
        _, y_tick = inv.transform((0, y_hat_disp - tick_depth))

        ax.plot(
            [x1 - tick_x, x1, x2, x2 + tick_x],
            [y_tick, y_hat, y_hat, y_tick],
            lw=bracket_lw, c="black",
        )

        ax.text((x1 + x2) / 2, y_text, star,
                ha="center", va="bottom",
                fontsize=fs, fontweight=fw, color="black")

        # Stack brackets within same SV type
        bracket_offset += tick_depth + TEXT_PT + bracket_gap
```

## Visual Result

```
   \──────────/     \──────/
     ****              ns
  [bar1] [bar2]   [bar3] [bar4]
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bracket_gap` | 10.0 | Vertical gap (display pts) between stacked bracket units |
| `tick_depth` | 6.0 | Depth of diagonal ticks (display pts). Larger = steeper angle |
| `bracket_lw` | 0.8 | Line width for bracket lines and ticks |
| `use_broken_axis` | True | Enable broken axis; auto-disabled if data doesn't need it |
| `test_method` | "chi2" | Statistical test: `"chi2"` or `"fisher"` (for small samples) |

## Pitfalls

- **ns color MUST be same as stars (black)** — user explicitly rejected gray. Distinguish by fontsize (12 vs 9) and weight (bold vs normal) only.
- **Diagonal ticks must be OUTWARD** — `\` goes down-LEFT from bar1, `/` goes down-RIGHT from bar2. NOT inward toward each other.
- **Horizontal line goes from bar center to bar center** — NOT from extended bracket ends. The ticks extend outward from the bar centers.
- **Reset `bracket_offset` per SV type** — NOT globally across all types. Each SV type's brackets start fresh from its own `y_base`.
- **`bracket_offset` increment** — use `tick_depth + TEXT_PT + bracket_gap`, NOT `LEG_PT + TEXT_PT + bracket_gap`. LEG_PT is only for the initial gap from bars.
- **Auto-detect broken axis** — when all bars are similar height, `need_broken=False` avoids bracket clipping by the broken axis junction.
- **chi2_contingency** raises ValueError on zero expected frequencies — always wrap in try/except with pre-check.
- **Store ALL pairs including ns** — so every comparison gets a bracket annotation, not just significant ones.
- **Draw bracket as SINGLE POLYLINE** — never 3 separate `ax.plot()` calls. Three separate lines cause line-cap overlap at junction points, creating visible protrusions. One `ax.plot()` with 4 x-points and 4 y-points draws the entire 宝盖头 cleanly.
- **`bracket_lw` default 0.8** — thicker lines (1.2+) look heavy. 0.8 is clean and publication-ready.
