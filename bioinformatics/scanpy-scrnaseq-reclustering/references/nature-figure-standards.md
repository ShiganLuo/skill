# Nature Publication Standards for scRNA-seq Figures

## Matplotlib Global Config

Set these BEFORE any plot call for Nature-quality output:
```python
matplotlib.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.title_fontsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "pdf.fonttype": 42,       # editable text in PDF
    "ps.fonttype": 42,
})
```

## Figure Sizes

Nature single-column: 3.5 inches wide. Double-column: 7 inches.
- UMAP: 3.5 × 3 inches
- Dotplot: width scales with gene count (0.18 in/gene), height with cell types (0.35 in/type)
- Multi-panel marker UMAPs: ncols × 2 inches wide, nrows × 1.8 inches tall

## Output Formats

Always save BOTH PNG and PDF:
```python
def save_fig(fig, path, dpi=300, formats=None):
    if formats is None:
        formats = ["png", "pdf"]
    base = os.path.splitext(path)[0]
    for fmt in formats:
        fig.savefig(f"{base}.{fmt}", dpi=dpi, bbox_inches="tight")
    plt.close("all")
```

## Colorblind-Friendly Palette

Use Okabe-Ito extended. Assign colors to cell types in consistent order:
```python
CB_PALETTE = [
    "#0072B2",  # blue         (Endothelial)
    "#E69F00",  # orange       (Granulosa)
    "#009E73",  # green        (Macrophage)
    "#CC79A7",  # pink         (OSE)
    "#56B4E9",  # light blue   (Pericyte)
    "#D55E00",  # vermillion   (Smooth_muscle)
    "#999999",  # grey         (Stromal)
    "#882255",  # dark purple  (Theca)
    "#44AA99",  # teal         (T_NK_cell)
    "#332288",  # indigo       (Proliferating)
    "#F0E442",  # yellow       (Epithelial)
]
```

CRITICAL: Avoid similar colors for adjacent clusters (e.g., grey Stromal next to vermillion Smooth_muscle is fine; two yellows is not).

## UMAP Style

- `legend_loc="on data"` with `legend_fontsize=5, legend_fontoutline=1.5` for cell type labels
- `frameon=True` for UMAP axes
- `size=3` for single UMAP, `size=1-2` for multi-panel
- `alpha=0.7` for single UMAP, `alpha=0.5-0.6` for multi-panel
- No title (or very concise, ≤3 words)
- Axis labels: "UMAP1", "UMAP2" at fontsize=7

## Marker Expression UMAPs

Multi-panel grid showing key marker genes:
- Remove tick marks: `ax.set_xticks([]); ax.set_yticks([])`
- Remove frame: `frameon=False`
- No colorbar: `colorbar_loc="none"`
- Gene name as title: fontsize=8, bold
- One marker per cell type to verify annotation

## Required Publication Figures

1. Cell type UMAP (on data labels, colorblind palette)
2. Sample UMAP (post-Harmony, prove batch correction)
3. Marker expression UMAPs (one per key cell type)
4. Marker dotplot (grouped by cell type)
5. DEG dotplot (top genes per cluster)
6. Cell type composition barplot (per sample)
7. QC summary table (n cells, median genes, UMI, MT%)
8. Annotation confidence UMAP
