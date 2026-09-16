# Post-run validation: how good was the annotation?

Pattern for verifying that a `mode_auto` run produced high-quality cell type
labels, after `AUTO MODE COMPLETE`. Built from the v13 review cycle on macaque
ovary. Three checks, in order of speed → depth.

## Check 1 — Unknown count and cluster distribution

Fast. Confirms the iteration loop filtered properly and nothing was orphaned.

```python
import scanpy as sc
import pandas as pd

adata = sc.read_h5ad("<out_dir>/ovaries_auto_annotated_vN.h5ad")

# Total cells retained + Unknown ratio
print(f"retained: {adata.n_obs}, clusters: {adata.obs['leiden'].nunique()}")
print(f"unknown: {(adata.obs['cell_type']=='Unknown').sum()}")

# Cluster x cell_type cross-tab — should be 1:1 or 1:few (sub-clustering)
print(pd.crosstab(adata.obs['leiden'], adata.obs['cell_type']))
```

A healthy run has each leiden cluster mapping to a single cell type (one
column per row). Multiple cell types per leiden cluster, or one cell type
spreading across many clusters, are both red flags. A few clusters sharing
one cell type is normal (Granulosa splits into Cumulus + Mural + Pre variants).

## Check 2 — Canonical-marker dotplot per cell type

The strongest signal of annotation quality. Use the *canonical* markers from
`tissue_cell_types` (the Step 0 query result, NOT the cluster's top DEG) — if
the LLM correctly identified the cell type, those markers should be
specifically expressed in the matching cluster and silent elsewhere.

```python
import scanpy as sc
import matplotlib.pyplot as plt

adata = sc.read_h5ad("<out_dir>/ovaries_auto_annotated_vN.h5ad")

# tissue_cell_types comes from Step 0 query result in run.log:
#   grep "  [A-Z].*:" run.log
# Pull 4-5 canonical markers per cell type.
tissue_cell_types = {
    "Granulosa_Cell":   ["FOXL2", "CYP19A1", "AMH", "FSHR", "INHA"],
    "Endothelial_Cell_Blood":    ["PECAM1", "CDH5", "VWF", "CD34", "EMCN"],
    "Endothelial_Cell_Lymphatic": ["PROX1", "LYVE1", "CCL21", "MMRN1", "NRP2"],
    "Smooth_Muscle_Cell":         ["ACTA2", "MYH11", "TAGLN", "MYL9", "CNN1"],
    "Macrophage":    ["CD68", "CD163", "CSF1R", "MRC1", "LYZ"],
    "NK_Cell":       ["NKG7", "GZMB", "GNLY", "KLRD1", "PRF1"],
    "Stromal_Cell":  ["DCN", "COL1A1", "COL1A2", "PDGFRB", "LUM"],
    "Epithelial_Cell_Oviductal_Fallopian": ["KRT19", "KRT18", "EPCAM", "PAX8", "MSLN"],
}

# Filter out markers that didn't make it into adata.raw.var (post-HVG filter)
canonical = {ct: [g for g in genes if g in adata.raw.var.index]
             for ct, genes in tissue_cell_types.items()}

sc.settings.set_figure_params(dpi=150, frameon=False)
sc.pl.dotplot(
    adata,
    var_names=canonical,
    groupby="cell_type",
    cmap="Reds",
    standard_scale="var",
    show=False,
    dendrogram=False,
)
plt.savefig("<out_dir>/plots/canonical_marker_dotplot.png", dpi=150, bbox_inches="tight")
plt.close("all")
```

A cell type whose canonical markers do NOT show in its own column is a wrong
annotation. Example v13 finding: `Granulosa_Cell` had strong AMH but its other
markers (FOXL2/CYP19A1/FSHR) showed up under `Epithelial_Cell_Oviductal_Fallopian`
— signal that the two cell type boundaries are blurred in the data and may
need re-clustering or manual review.

## Check 3 — Leiden-cluster x canonical-marker heatmap

Strongest signal for cluster purity. The vertical axis is `leiden` cluster;
rows are colored by the cluster's `cell_type`. If a single cell type spreads
across multiple leiden clusters, this heatmap shows whether both clusters
share the same marker pattern (one real subtype, two leiden artifacts) or
have divergent patterns (two genuinely different populations sharing one
label).

```python
import scanpy as sc
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

adata = sc.read_h5ad("<out_dir>/ovaries_auto_annotated_vN.h5ad")

key_markers = ["FOXL2", "CYP19A1", "AMH", "KRT19", "EPCAM",
               "PECAM1", "CD34", "CCL21", "MMRN1"]
key_markers = [g for g in key_markers if g in adata.raw.var.index]

rows = []
for cl in sorted(adata.obs["leiden"].unique(), key=lambda x: int(x)):
    sub = adata[adata.obs["leiden"] == cl]
    row = {"cluster": cl, "cell_type": sub.obs["cell_type"].iloc[0], "n": sub.n_obs}
    for g in key_markers:
        row[g] = float(sub.raw[:, g].X.mean())
    rows.append(row)
df = pd.DataFrame(rows).melt(id_vars=["cluster", "cell_type", "n"],
                              value_vars=key_markers,
                              var_name="marker", value_name="mean_expr")
pivot = np.log1p(df.pivot(index="cluster", columns="marker", values="mean_expr"))

fig, ax = plt.subplots(figsize=(14, 8))
sns.heatmap(pivot, cmap="Reds", ax=ax, cbar_kws={"label": "log1p(mean expr)"},
            linewidths=0.5, linecolor="lightgray")
ax.set_title("Cluster x marker heatmap")
ax.set_yticklabels([f"cl {cl} (n={int(df[df.cluster==cl]['n'].iloc[0])})"
                     for cl in pivot.index])
plt.tight_layout()
plt.savefig("<out_dir>/plots/cluster_marker_heatmap.png", dpi=150, bbox_inches="tight")
```

## Check 4 — Cross-version comparison

Only needed when comparing two annotation runs (e.g. v12 vs v13 on the same
input). The cleaner run has fewer cell types with ambiguous cross-tab rows
and fewer cells in `Unknown`. Pattern:

```python
old = sc.read_h5ad("v12.h5ad")
new = sc.read_h5ad("v13.h5ad")
ref = sc.read_h5ad("v7.h5ad")  # baseline truth (mimo)

# new.obs.index is a subset of ref.obs.index
ref_subset = ref[new.obs.index.tolist()]
mapping = pd.DataFrame({
    "new": new.obs["cell_type"].values,
    "ref": ref_subset.obs["cell_type"].values,
})
with pd.option_context("display.max_columns", None, "display.width", 300):
    print(pd.crosstab(mapping["new"], mapping["ref"]))
```

A diagonal-heavy cross-tab means new run agrees with the baseline. Off-diagonal
mass suggests systematic confusions (e.g. mimo's `Granulosa_cells` and
`Theca_cells` become M3's `Granulosa_Cell` — biologically defensible because
the markers overlap).

## Success criteria summary

| Metric | Healthy run |
|--------|-------------|
| `outcome=clean` in run.log | required |
| `Unknown` cells | < 1% of total |
| Leiden clusters | 8-15 (varies by tissue, but generally few) |
| Cell types per cluster | ≤ 2 (1:1 is best) |
| Clusters per cell type | 1-4 (subtype splitting is fine, but not 8+) |
| Canonical-marker dotplot | ≥ 80% of cell types have marker specificity on diagonal |
| Cross-version agreement | ≥ 70% of cells in diagonal when compared to mimo baseline |
