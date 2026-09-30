---
name: scrnaseq-compositional-analysis
description: scRNA-seq DA via scCODA for cell-type proportions.
tags:
  - scrnaseq
  - sccoda
  - pertpy
triggers:
  - scCODA
  - cell-type proportion change
  - differential abundance scRNA-seq
---

# scRNA-seq Compositional / Differential Abundance Analysis

Single-cell cell-type proportions are **compositional**: increasing one cell type necessarily changes the relative abundances of all others. Naive per-cell-type tests (Fisher's exact, chi2 on each row independently) ignore this constraint and inflate false positives, especially in low-replicate studies. This skill picks the right method and uses it correctly.

## When to Use

Use when the user wants to know whether cell-type proportions differ between conditions (treatment vs control, aging vs young, tumor vs normal, etc.) in a single-cell experiment.

**Do NOT use for** differential gene expression (DEG) — that's pseudo-bulk DESeq2/edgeR on counts, a separate pipeline.

## Method Selection (sc-best-practices.org/conditions/compositional)

| Method | Model | When to use | Sample size |
|---|---|---|---|
| **scCODA** (Büttner 2021 Nat Comm) | Bayesian Dirichlet-Multinomial | Discrete cell-type proportion changes | n ≥ 2 per condition (recommended for small samples) |
| **tascCODA** | Bayesian tree-aggregated | Hierarchical / nested cell-type taxonomies | n ≥ 2 |
| **MILO** (Dann 2022) | KNN-based GLM | Continuous / transitional abundance changes; cell states between clusters | n ≥ 3 |
| **Fisher's exact + chi2** | Frequentist per-cell-type | Legacy / sanity check | n ≥ 5 (underpowered below) |

**scCODA is the default** for most experiments — it's the only method that jointly models the compositional constraint and is designed for low-replicate scRNA-seq.

## scCODA — Reference Implementation

### Environment setup (CRITICAL — version pin dance)

pertpy 1.3 + numpyro + jax have a fragile compatibility window. The error you get when versions are wrong is opaque. Pin exactly:

```bash
# Inside the project's .venv (do NOT use conda pip — wrong path)
.venv/bin/python -m pip install 'pertpy[jax]'   # installs jax, jaxlib, numpyro
.venv/bin/python -m pip install 'numpyro<0.20'  # 0.22 renamed concentrations→concentration
.venv/bin/python -m pip install 'jax<0.5' 'jaxlib<0.5'  # 0.6 dropped xla_pmap_p
```

If `pt.tl.Sccoda()` fails with `ImportError: ... 'jax' is not installed` even though jax is installed, the issue is that `pertpy.tools` is lazy-imported and the Sccoda loader never registered. Fix: add `import pertpy.tools  # noqa: F401` after `import pertpy as pt`.

### API pattern (pertpy 1.x — note the new shape)

```python
import warnings; warnings.filterwarnings("ignore")
import pertpy as pt
import pertpy.tools  # noqa: F401  -- force-load jax deps

# 1. Subset AnnData to the two conditions, build a 'condition' column
sub = adata[adata.obs["sample_id"].isin([ref, treat])].copy()
sub.obs["condition"] = sub.obs["sample_id"].astype("category")

sccoda = pt.tl.Sccoda()
# 2. Aggregate cell-level → sample-level (MuData with coda modality)
mdata = sccoda.load(
    sub,
    type="cell_level",
    generate_sample_level=True,
    cell_type_identifier="cell_type",
    sample_identifier="sample_id",
    covariate_obs=["condition"],
)
# 3. Prepare design matrix; reference_cell_type="automatic" picks the most stable
sccoda.prepare(mdata, formula="condition", reference_cell_type="automatic")
# 4. MCMC sampling (2000 samples + 500 warmup ≈ 20-40s per contrast)
sccoda.run_nuts(mdata, num_samples=2000, num_warmup=500, rng_key=0)
# 5. Extract credible effects
df = sccoda.get_effect_df(mdata)
```

### Reading the output

`get_effect_df` returns a multi-index DataFrame with columns:
`Covariate`, `Cell Type`, `Final Parameter`, `ETI 89% lower`, `ETI 89% upper`, `SD`, `Inclusion probability`, `Expected Sample`, `log2-fold change`.

- `Inclusion probability` = posterior probability that the cell-type effect is non-zero. Rename to `final_prob`.
- `log2-fold change` = log2(treat / ref). Rename to `log2FC`.
- **Credible effect**: `final_prob ≥ 0.90` AND `log2FC != 0`.
- Reference cell type chosen automatically is in `mdata["coda"].uns["scCODA_params"]["reference_cell_type"]` — log it; user will ask.

### Plotting (full snippet — copy-pasteable)

```python
import matplotlib.pyplot as plt

n_up = int(((df["log2-fold change"] > 0) & (df["Inclusion probability"] >= 0.90)).sum())
n_dn = int(((df["log2-fold change"] < 0) & (df["Inclusion probability"] >= 0.90)).sum())
ref_used = mdata["coda"].uns["scCODA_params"]["reference_cell_type"]

# Clean title: ONLY sample IDs, no "credible", no reference type
title = f"{tissue.upper()} DA: {treat} vs {ref}"

# Skip effects_barplot when zero credible effects (FacetGrid throws otherwise)
if n_up + n_dn > 0:
    fg = sccoda.plot_effects_barplot(
        mdata,
        covariates="condition",
        parameter="log2-fold change",
        plot_facets=True,                # False breaks seaborn hue
        plot_zero_covariate=False,
        plot_zero_cell_type=False,
        return_fig=True,
    )
    # FacetGrid ignores figsize when only one facet — force it
    fg.fig.set_size_inches(14, 6)
    fg.fig.suptitle(title, fontsize=12, y=0.97)
    for ax in fg.axes.flat:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.set_title("")  # hide the auto-added "condition[T.xxx]" inner title
    fg.fig.subplots_adjust(left=0.06, right=0.99, top=0.88, bottom=0.24)
    fg.fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fg.fig)

# Stacked barplot — feature_name="samples" NOT "rel_abundance"
fig = sccoda.plot_stacked_barplot(
    mdata, feature_name="samples", figsize=(14, 6), return_fig=True,
)
if fig is None:
    fig = plt.gcf()
fig.set_size_inches(14, 6)
fig.suptitle(title, fontsize=12, y=0.97)
fig.subplots_adjust(left=0.07, right=0.78, top=0.88, bottom=0.12)
fig.savefig(out_png, dpi=300, facecolor="white")
plt.close(fig)
```

### CLI integration (Omics repo pattern)

Mirror the project's CLI conventions: `--h5ad tissue=path` repeatable, `--compare tissue:ref:treat[=label]` repeatable, `--out-dir` required. Skip flags for prepare/deseq2/plot stages. Match existing pseudobulk CLI in `workflow/Omics/src/scRNAseq/scripts/python/utils/pseudobulk.py`.

## Common Pitfalls

1. **Memory blow-up from raw counts**: scCODA aggregates to sample-level internally, but if you accidentally pass full `.X` (e.g. 3000 HVG × N cells × per-cell DirichletMultinomial concentration tensor) you'll get OOM. The fix is just to NOT pass `.X` — `load()` handles aggregation. Symptom: `jax.errors.JaxRuntimeError: Out of memory allocating 5 TB`.
2. **"DirichletMultinomial got invalid total_count"**: numpyro ≥ 0.22 renamed `concentrations` → `concentration`. Pin numpyro < 0.20.
3. **"cannot import name 'xla_pmap_p' from jax.interpreters.pxla"**: jax ≥ 0.6 removed it. Pin jax < 0.5.
4. **`plot_effects_barplot` returns FacetGrid with hue error** when `plot_facets=False`. Always `plot_facets=True`.
5. **`plot_stacked_barplot(feature_name="rel_abundance")` KeyError**. Use `feature_name="samples"`.
6. **FacetGrid ignores `figsize`** when only one facet. Call `fig.set_size_inches(W, H)` after the plot call.
7. **Figure aspect ratio wrong**: 11+ x-tick labels at 30° rotation need `figsize=(14, 6)` + `subplots_adjust(top=0.88, bottom=0.24)`. 90° rotation makes the figure too tall; auto-aspect is too wide.
8. **`No objects to concatenate`** when 0 credible effects: gate `plot_effects_barplot` on `if n_total > 0`.
9. **Inner facet title shows `condition[T.xxx]`**: clear with `ax.set_title("")` on each axes after plot.
10. **scCODA does NOT need pseudo-replicates**: scCODA's Bayesian Dirichlet-Multinomial model handles single-sample-per-condition designs natively. Do NOT add a `--n-pseudo-reps` parameter to split samples into pseudo-replicates — this changes the MCMC posterior and produces different (worse) results. The `run_sccoda` function should accept raw `sample_id` directly.
11. **DA effects barplot for PPT embedding**: the default `figsize=(14, 6)` makes fonts too small when embedded at ~7 inches in a slide. For PPT-embedded plots, use `figsize=(10, 5.5)` with `subplots_adjust(left=0.25, right=0.98, top=0.88, bottom=0.10)` and `rotation=45, ha="right", fontsize=10` for x-tick labels. The `bottom=0.10` works because labels are horizontal (no rotation overflow). Alternatively, regenerate plots from existing CSV without re-running MCMC.
12. **MCMC is stochastic**: scCODA results vary between runs unless `rng_key` is fixed. When regenerating plots only (e.g. changing figsize, colors), load from the existing `_da.csv` and replot — don't re-run the full MCMC pipeline. See `plot_effects_from_csv()` in the script.
13. **Each cell type needs its own color**: user explicitly corrected "不能规定颜色几种,有几个细胞,颜色几种" — do NOT use a fixed 10-color palette. Generate N colors for N cell types dynamically using `plt.cm.get_cmap("tab20" if n <= 20 else "tab20b")` and index by `i / max(n-1, 1)`.
14. **Non-significant cell types must be gray, not individually colored**: user explicitly corrected "不显著不要染色". Only credible (significant) cell types get distinct colors from the dynamic palette. Non-credible cell types are always `#cccccc` gray with no edge. Implementation:
    ```python
    n_credible = int(df["is_credible"].sum())
    cmap = plt.cm.get_cmap("tab20" if n_credible <= 20 else "tab20b")
    cred_colors = [cmap(i / max(n_credible - 1, 1)) for i in range(n_credible)]
    ci = 0
    colors = []
    for _, row in df.iterrows():
        if row["is_credible"]:
            colors.append(cred_colors[ci]); ci += 1
        else:
            colors.append("#cccccc")
    ```
14. **plot_effects_from_csv — regenerate from CSV**: the script has `plot_effects_from_csv(csv_path, out_path, title)` that reads `*_da.csv` and generates a pertpy-style horizontal barplot with per-cell-type coloring and black edges on credible effects. Use this instead of re-running MCMC when only the plot style needs changing.
15. **Stacked barplot from h5ad**: when you need to regenerate stacked barplots (e.g. fixing x-axis label truncation) without re-running MCMC, create them directly from h5ad:
    ```python
    adata = sc.read_h5ad(h5ad_path)
    sub = adata[adata.obs["sample_id"].isin(samples)].copy()
    ct_counts = sub.obs.groupby(["sample_id", "cell_type"]).size().unstack(fill_value=0)
    ct_props = ct_counts.div(ct_counts.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(10, 5.0))
    ct_props.plot(kind="bar", stacked=True, ax=ax, width=0.8, edgecolor="none")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right", fontsize=10)
    fig.subplots_adjust(left=0.08, right=0.78, top=0.86, bottom=0.22)
    ```
    The `bottom=0.22` is critical for rotated x-axis labels with long sample IDs.
16. **scCODA stacked barplot x-axis labels truncated**: the pertpy `plot_stacked_barplot` default `figsize=(14, 6)` + `bottom=0.14` clips long sample ID labels. For PPT embedding, use `figsize=(10, 5.0)` + `subplots_adjust(bottom=0.22)` and `rotation=30, ha="right", fontsize=10`.
17. **scCODA does NOT need pseudo-replicates** (reinforcing pitfall 10): the `--n-pseudo-reps` parameter was removed from the script. scCODA handles n=1 per condition natively. If you see a `--n-pseudo-reps` parameter in any scCODA script, remove it — it was added by mistake and changes MCMC results.

## Pseudobulk DEG — Uses All Genes, Not HVGs

The pseudobulk DEG pipeline (`pseudobulk.py`) uses **ALL genes** from the raw count matrix (`.raw.var_names`), not just highly variable genes. This is the correct approach for pseudobulk DEG — HVG selection is for clustering/UMAP, not for differential expression.

## Cell Types with Too Few Cells — No DEG but DA May Be Significant

When a cell type has < `min_cells` (default 30) cells in one condition, the pseudobulk pipeline skips it (no DEG). But scCODA's DA analysis works at the cell level and can still detect significant abundance changes. Example: Myofibroblast had only 11 cells in POI group → no DEG, but DA showed log2FC=-5.72 (prob 99%).

## TE Analysis Connection to Scientific Questions

TE fraction analysis should be connected to DEG/DA findings for each scientific question. Key TE results from scTE data:
- Ovaries Granulosa: TE fraction ↑ (padj=9.5e-7) — aging granulosa cells show TE derepression
- Uterus Glandular_Epithelial: TE fraction ↑↑↑ (log2FC=0.49, padj=1.4e-6) — most dramatic TE increase after ovariectomy, correlates with BMP pathway inactivation
- Uterus Myometrial_Smooth_Muscle: TE fraction ↑ (padj=1.8e-38)

When building scientific narratives, always check if TE data supports or contradicts the DEG/DA findings.

## Glob Patterns for File Matching

When loading GO/DEG files with `Path.glob()`, the pattern `_vs_1411200` does NOT match filenames containing `_vs_zigong-1411200`. The `*` wildcard in `Path.glob` does NOT bridge across literal characters in the pattern.

**BAD**: `*11238*_vs_1411200*_Endometrial_Stromal_go_down.csv` → 0 matches
**GOOD**: `*11238*_vs_*1411200*_Endometrial_Stromal_go_down.csv` → 1 match

The fix is to add an extra `*` between `_vs_` and the sample ID prefix. The actual filenames have `_vs_zigong-1411200` but the glob pattern needs `_vs_*1411200` to match.

## DA Plot Custom Regeneration from CSV

When you need to regenerate DA effects barplots without re-running MCMC (e.g. changing colors, figsize, label style), use `plot_effects_from_csv()`:

```python
def plot_effects_from_csv(csv_path, out_path, title):
    df = pd.read_csv(csv_path)
    df = df.sort_values("log2FC").reset_index(drop=True)
    n = len(df)
    n_credible = int(df["is_credible"].sum())
    cmap = plt.cm.get_cmap("tab20" if n_credible <= 20 else "tab20b")
    cred_colors = [cmap(i / max(n_credible - 1, 1)) for i in range(n_credible)]
    ci = 0
    colors = []
    for _, row in df.iterrows():
        if row["is_credible"]:
            colors.append(cred_colors[ci]); ci += 1
        else:
            colors.append("#cccccc")
    fig, ax = plt.subplots(figsize=(10, max(4, n * 0.45 + 1.5)))
    for i, (_, row) in enumerate(df.iterrows()):
        edgecolor = "black" if row["is_credible"] else "none"
        lw = 0.8 if row["is_credible"] else 0
        ax.barh(i, row["log2FC"], color=colors[i], edgecolor=edgecolor,
                linewidth=lw, height=0.7, zorder=2)
    ax.set_yticks(range(n))
    ax.set_yticklabels(df["cell_type"], fontsize=10)
    fig.subplots_adjust(left=0.25, right=0.98, top=0.88, bottom=0.10)
    fig.savefig(out_path, dpi=300, facecolor="white")
    plt.close(fig)
```

Key: labels are **horizontal** (no rotation) for maximum readability. The `left=0.25` gives enough room for long cell type names.

## Verification

After running, sanity-check:
- `df["Inclusion probability"].between(0, 1).all()` — if not, sampling failed
- `np.isnan(df["log2-fold change"]).sum() < len(df)` — most cells should have an estimate
- Reference cell type appears with `Final Parameter=0, ETI=0, SD=0` (constraint by construction)
- Credible effects should cluster in biologically expected cell types (e.g. immune cell shifts in disease, stromal shifts in hormone perturbations)
