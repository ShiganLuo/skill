# Pseudobulk DEG & Volcano Plot Patterns

## Pseudobulk DEG with PyDESeq2 (no-replicate design)

When comparing 2 samples per condition with no biological replicates, PyDESeq2 fails with:
```
ValueError: The number of samples and the number of design variables are equal
```

**Solution**: split each sample's cells into N pseudo-replicates before aggregation:

```python
def pseudobulk_with_replicates(adata_ct, sample_key="sample_id", n_splits=2):
    counts = adata_ct.layers["counts"]
    if hasattr(counts, "toarray"):
        counts = counts.toarray()

    all_rows, meta_rows = [], []
    for sample in sorted(set(adata_ct.obs[sample_key])):
        mask = adata_ct.obs[sample_key].values == sample
        idx = np.where(mask)[0]
        np.random.shuffle(idx)
        splits = np.array_split(idx, n_splits)
        for i, split_idx in enumerate(splits):
            row_sum = np.asarray(counts[split_idx].sum(axis=0)).flatten()
            all_rows.append(row_sum)
            meta_rows.append({"sample": f"{sample}_rep{i}", "condition": sample, "replicate": f"rep{i}"})

    counts_df = pd.DataFrame(all_rows, columns=adata_ct.var_names)
    counts_df.index = [m["sample"] for m in meta_rows]
    meta_df = pd.DataFrame(meta_rows).set_index("sample")
    return counts_df, meta_df
```

Then run PyDESeq2 with `design="~condition"` where condition = original sample_id.

**Environment note**: scanpy sif (`/home/luosg/Database/env/scanpy/scanpy.sif`) has pydeseq2 0.5.4 but NOT rpy2/edgeR.

## Volcano Plot with adjustText Auto-Repulsion

Use `adjustText` library (available in scanpy sif) to avoid overlapping gene labels:

```python
from adjustText import adjust_text

def plot_volcano(df, title, out_png, top_n=5):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    df = df.copy()
    df["neg_log10p"] = -np.log10(df["padj"].clip(lower=1e-300))

    sig_up = (df["padj"] < 0.05) & (df["log2FoldChange"] > 1)
    sig_down = (df["padj"] < 0.05) & (df["log2FoldChange"] < -1)
    ns = ~(sig_up | sig_down)

    # NS points (gray, small, rasterized for speed)
    ax.scatter(df.loc[ns, "log2FoldChange"], df.loc[ns, "neg_log10p"],
               c="#CCCCCC", s=6, alpha=0.4, linewidths=0, rasterized=True)
    # Up (red)
    ax.scatter(df.loc[sig_up, "log2FoldChange"], df.loc[sig_up, "neg_log10p"],
               c="#D62728", s=10, alpha=0.6, linewidths=0, rasterized=True)
    # Down (blue)
    ax.scatter(df.loc[sig_down, "log2FoldChange"], df.loc[sig_down, "neg_log10p"],
               c="#1F77B4", s=10, alpha=0.6, linewidths=0, rasterized=True)

    # Reference lines
    ax.axhline(-np.log10(0.05), ls="--", c="#888888", lw=0.6, zorder=0)
    ax.axvline(-1, ls="--", c="#888888", lw=0.6, zorder=0)
    ax.axvline(1, ls="--", c="#888888", lw=0.6, zorder=0)

    # Collect labels for adjustText
    texts = []
    if sig_up.any():
        for _, row in df.loc[sig_up].nlargest(top_n, "neg_log10p").iterrows():
            texts.append(ax.text(row["log2FoldChange"], row["neg_log10p"], row["gene"],
                                 fontsize=6, fontstyle="italic", color="#D62728", ha="center", va="center"))
    if sig_down.any():
        for _, row in df.loc[sig_down].nlargest(top_n, "neg_log10p").iterrows():
            texts.append(ax.text(row["log2FoldChange"], row["neg_log10p"], row["gene"],
                                 fontsize=6, fontstyle="italic", color="#1F77B4", ha="center", va="center"))

    if texts:
        adjust_text(texts, ax=ax,
                    arrowprops=dict(arrowstyle="-", color="#888888", lw=0.4),
                    force_text=(0.8, 0.8), force_points=(0.5, 0.5),
                    expand=(1.2, 1.4), max_move=None)

    # Legend with counts
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#D62728", markersize=6, label=f"Up ({sig_up.sum()})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#1F77B4", markersize=6, label=f"Down ({sig_down.sum()})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#CCCCCC", markersize=6, label=f"NS ({ns.sum()})"),
    ]
    ax.legend(handles=handles, fontsize=7, loc="upper right", frameon=True, framealpha=0.8, edgecolor="#CCCCCC")

    ax.set_xlabel("log$_2$ Fold Change", fontsize=9)
    ax.set_ylabel("-log$_{10}$(padj)", fontsize=9)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    fig.savefig(str(out_png), dpi=300, bbox_inches="tight")
    plt.close(fig)
```

### Key design choices
- **`rasterized=True`** on scatter points — prevents huge SVG/PDF when thousands of points
- **`adjust_text`** with `force_text`, `force_points`, `expand` — auto-repulsion prevents label overlap
- **Legend shows counts** — `Up (261)`, `Down (270)`, `NS (2306)`
- **No TE special marking** — user explicitly requested removing TE gene highlighting from volcano plots
- **`--top-n` CLI arg** — configurable number of labeled genes per direction (default 5)
- **Gene names in italic** — `fontstyle="italic"` matches convention for gene symbols

## TE Gene Identification (scTE data)

scTE quantifies transposable elements alongside genes. TE names follow repeat element naming conventions:

```python
def is_te(name):
    te_prefixes = (
        "Alu", "HERV", "HERVE", "HERVI", "HERVL", "HERVFH", "HERVH",
        "HERVK", "HERVS", "LTR", "L1M", "L1P", "L1PA", "L1PB",
        "L2a", "L2c", "MER", "MLT", "ERVL", "MacERV", "MacERVK",
        "MacNERVK", "hAT", "Tigger", "Charlie", "EuthAT",
    )
    te_exact = {"MIR", "MIR1306", "MIR1307", "MIR142", "MIR15A", "MIR26B",
                "MIR32", "MIR335", "MIR4785", "MIR5004", "MIR5047", "MIR1-2", "MIRLET7A1"}
    if name in te_exact:
        return True
    return any(name.startswith(p) for p in te_prefixes) or "-int" in name
```

**Pitfall**: Naive regex like `r'(ERV|Alu|LINE|SINE|LTR)'` matches normal genes (CYSLTR1, IL1R2, etc.). Always use prefix-based matching with explicit TE naming conventions.

Typical counts: ~44 TE genes in Uterus scTE HVG set, ~83 in Ovaries scTE HVG set (out of 3000 total).

## Milo DA Analysis: Limitations with No-Replicate Designs

Milo (R package for neighborhood-level differential abundance) requires **≥3 biological replicates per condition** to estimate dispersion. With 1-vs-1 comparisons (no replicates), edgeR throws:
```
Error in glmFit.default: NA dispersions not allowed
```

**Workarounds**:
1. **Re-group samples** — combine into 2+ groups with ≥3 samples per group (requires biological justification)
2. **Fixed dispersion** — set dispersion=0.1 in edgeR (reduces statistical power)
3. **Use simpler methods** — chi-square + Fisher's exact test on cell type proportions (no neighborhood resolution, but works with any sample size)

**Milo R environment**: miloR 1.2.0 installed in system R (`/usr/bin/R`). Dependencies: BiocNeighbors, ggraph, edgeR, SingleCellExperiment. Install chain: `RcppHNSW` → `BiocNeighbors` → `tweenr` → `ggforce` → `ggraph` → `miloR`.

**Data conversion**: No zellkonverter/anndata2ri in system R. Export from Python as MTX + TSV:
- `scipy.io.mmwrite()` for sparse counts (genes × cells)
- `adata.obs.to_csv()` for metadata
- `adata.var.to_csv()` for gene info
- R reads with `readMM()` + `read.delim()`
- Must add `logcounts` assay: `edgeR::cpm()` + `log1p()` before building Milo object
