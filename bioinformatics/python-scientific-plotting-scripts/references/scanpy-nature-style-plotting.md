# Nature-Style Scanpy Plotting Defaults

Publication-quality matplotlib defaults for single-cell UMAP, dotplot, violin, and bar charts.

## Multi-Panel Figure 1 Layout (GridSpec)

For a publication Figure 1 with (a) UMAP cell type, (b) UMAP sample, (c) dotplot, (d) bar chart:

```python
import matplotlib.pyplot as plt
import scanpy as sc

# Nature multi-panel rcParams (smaller than single-panel)
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.linewidth": 0.5,
    "axes.labelsize": 8,
    "axes.titlesize": 9,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2,
    "ytick.major.size": 2,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6.5,
    "legend.frameon": False,
    "legend.handletextpad": 0.3,
    "legend.columnspacing": 0.5,
    "lines.linewidth": 0.5,
})

fig = plt.figure(figsize=(7.2, 6.8), dpi=300)
gs = fig.add_gridspec(
    2, 2,
    width_ratios=[1, 1],
    height_ratios=[1, 0.85],
    hspace=0.35, wspace=0.30,
    left=0.08, right=0.95, top=0.93, bottom=0.06,
)

# Panel label helper
def panel_label(ax, label, x=-0.08, y=1.08):
    ax.text(x, y, label, transform=ax.transAxes,
            fontsize=10, fontweight="bold", va="top", ha="left")

# (a) UMAP cell type — small dots, legend inside
ax_a = fig.add_subplot(gs[0, 0])
sc.pl.umap(adata, color="cell_type", ax=ax_a, show=False,
           palette=ct_colors_all, frameon=True, linewidth=0.4,
           title="", size=3, alpha=0.7)
ax_a.tick_params(axis="both", which="both", length=0, labelbottom=False, labelleft=False)
leg = ax_a.legend(loc="lower left", bbox_to_anchor=(0.0, 0.0),
                  fontsize=5.5, ncol=2, frameon=True, framealpha=0.9,
                  edgecolor="none", markerscale=1.5)
leg.get_frame().set_facecolor("white")
panel_label(ax_a, "a")

# (b) UMAP sample
ax_b = fig.add_subplot(gs[0, 1])
sc.pl.umap(adata, color="sample_id", ax=ax_b, show=False,
           frameon=True, linewidth=0.4, title="", size=3, alpha=0.7)
# ... same styling as (a)
panel_label(ax_b, "b")

# (c) Dotplot — groupby cell_type, not cluster number
ax_c = fig.add_subplot(gs[1, 0])
adata_dot = adata.copy()
adata_dot.obs["cell_type"] = adata_dot.obs["cell_type"].cat.remove_unused_categories()
sc.pl.dotplot(adata_dot, var_names=marker_genes, groupby="cell_type",
              use_raw=True, show=False, color_map="RdBu_r",
              expression_cutoff=0.5, title="", ax=ax_c)
panel_label(ax_c, "c")

# (d) Cell type proportions
ax_d = fig.add_subplot(gs[1, 1])
# ... horizontal bar chart
panel_label(ax_d, "d")

fig.suptitle("Single-cell transcriptomic profiling of macaque ovary (Cell Ranger)",
             fontsize=9, fontweight="bold", y=0.98)
fig.savefig("figure1_main.png", dpi=300, bbox_inches="tight")
```

## Critical Pitfall: scanpy Palette with 0-Cell Categories

When cell types have 0 cells (e.g., B_cell, Oocyte), scanpy's palette mapping
requires ALL categories to have colors, even empty ones. But dotplot/violin
fail if unused categories are present.

```python
# CORRECT: two separate palettes
all_categories = list(adata.obs["cell_type"].cat.categories)  # includes 0-cell
ct_colors_all = {ct: PALETTE[i % len(PALETTE)] for i, ct in enumerate(all_categories)}

ct_categories = [ct for ct in all_categories if (adata.obs["cell_type"] == ct).any()]
ct_colors = {ct: ct_colors_all[ct] for ct in ct_categories}

# UMAP: use ct_colors_all (needs all categories for palette mapping)
sc.pl.umap(adata, color="cell_type", palette=ct_colors_all, ...)

# Dotplot: use adata with unused categories removed
adata_dot = adata.copy()
adata_dot.obs["cell_type"] = adata_dot.obs["cell_type"].cat.remove_unused_categories()
sc.pl.dotplot(adata_dot, groupby="cell_type", ...)

# Violin: use ct_colors_all (needs all categories)
sc.pl.violin(adata, keys="n_genes_by_counts", groupby="cell_type",
             palette=ct_colors_all, ...)

# Bar chart: filter to >0 only
ct_counts = adata.obs["cell_type"].value_counts()
ct_counts = ct_counts[ct_counts > 0]
```

## Colorblind-friendly palette (20 colors)

```python
PALETTE = [
    "#E64B35",  # red
    "#4DBBD5",  # cyan
    "#00A087",  # teal
    "#3C5488",  # dark blue
    "#F39B7F",  # salmon
    "#8491B4",  # steel blue
    "#91D1C2",  # mint
    "#DC0000",  # bright red
    "#7E6148",  # brown
    "#B09C85",  # taupe
    "#00468B",  # navy
    "#42B540",  # green
    "#0099B4",  # teal dark
    "#AD002A",  # crimson
    "#6A3D9A",  # purple
    "#1B9E77",  # dark teal
    "#D95F02",  # orange
    "#7570B3",  # violet
    "#E7298A",  # magenta
    "#66A61E",  # olive green
]
```

## UMAP template (single panel)

```python
fig, ax = plt.subplots(figsize=(5.2, 4.2))
sc.pl.umap(adata, color="cell_type", ax=ax, show=False,
           palette=ct_colors_all,
           frameon=True, linewidth=0.4, title="",
           size=3, alpha=0.7)
ax.set_xlabel("UMAP1", fontsize=7, labelpad=2)
ax.set_ylabel("UMAP2", fontsize=7, labelpad=2)
ax.tick_params(axis="both", which="both", length=0, labelbottom=False, labelleft=False)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
leg = ax.legend(loc="lower left", fontsize=5.5, ncol=2, frameon=True,
                framealpha=0.9, edgecolor="none", markerscale=1.5)
fig.savefig("umap.png", dpi=300, bbox_inches="tight")
```

## Horizontal bar chart (cell type proportions)

```python
ct_counts = adata.obs["cell_type"].value_counts()
ct_counts = ct_counts[ct_counts > 0]  # remove empty categories
ct_pct = 100 * ct_counts / ct_counts.sum()

fig, ax = plt.subplots(figsize=(4.5, 0.4 * len(ct_counts) + 1.0))
bar_colors = [ct_colors.get(ct, "#999999") for ct in ct_counts.index]
ax.barh(range(len(ct_counts)), ct_pct.values, color=bar_colors,
        edgecolor="white", linewidth=0.3, height=0.65)
ax.set_yticks(range(len(ct_counts)))
ax.set_yticklabels(ct_counts.index, fontsize=6)
ax.set_xlabel("Proportion (%)", fontsize=7, labelpad=2)
ax.invert_yaxis()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for i, (pct, cnt) in enumerate(zip(ct_pct.values, ct_counts.values)):
    ax.text(pct + 0.3, i, f"{pct:.1f}%", va="center", fontsize=5.5, color="#333333")
ax.set_xlim(0, max(ct_pct) * 1.30)
```

## Key rules

- Always dpi=300 for publication
- Remove top/right spines (`ax.spines["top/right"].set_visible(False)`)
- Use `frameon=True, linewidth=0.4` for UMAP (not frameon=False)
- **size=3, alpha=0.7** for UMAP scatter — default size makes blobs, not dots
- Suptitle instead of ax.set_title for cleaner layout
- Horizontal bars with percentage labels for proportions
- **Dotplot: groupby cell_type, NOT cluster number** — readers need biological names
- **Dotplot: remove_unused_categories()** before calling — 0-cell types cause KeyError
- Use `cat.categories` not `.unique()` for palette mapping (includes 0-count types)
- **Two palette dicts needed**: ct_colors_all (for UMAP/violin) and ct_colors (for bar chart)
- Panel labels: bold "a", "b", "c", "d" at (-0.08, 1.08) in axes coords
- Figure size: 7.2x6.8 inches for 2x2 multi-panel (Nature column width ~3.5in per panel)
