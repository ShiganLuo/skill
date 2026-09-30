# Cluster-coloured UMAP subplots: drop-in helpers

When you build a "Cluster ref" subplot by hand (e.g. inside a multi-panel
marker-expression grid) instead of delegating to `sc.pl.umap`, two things
will go wrong if you forget them:

1. **`ax.scatter()` without `c=` silently uses matplotlib's default
   colour cycle** (C0 = `#1f77b4`). Every cluster ends up the same
   colour. With `s=5` and `alpha=0.7` over a grey base layer
   (`c="#e0e0e0"`), the dots visually merge into the background and
   the target cluster looks "missing".

2. **`adata.uns[f"{cluster_key}_colors"]` is the canonical palette**
   written by scanpy the first time `sc.pl.umap(color=cluster_key)`
   runs. Reusing it keeps the subplot consistent with the main UMAP
   figure.

The helpers below are battle-tested on a 16-cluster macaque ovary h5ad
with `adata.uns["leiden_colors"]` populated.

## Helpers

```python
from typing import Dict
import matplotlib.pyplot as plt

_tab_palette = tuple(plt.get_cmap("tab20")(i) for i in range(20))


def _to_hex(col) -> str:
    """Coerce a matplotlib colour (str or RGBA tuple) to a hex string."""
    if isinstance(col, str):
        return col
    try:
        return "#" + "".join(
            f"{int(round(c * 255)):02x}" for c in col[:3]
        )
    except (TypeError, ValueError):
        return "#1f77b4"


def _resolve_cluster_colors(adata, key: str) -> Dict[str, str]:
    """Return {category_value: hex_color} for an adata.obs categorical.

    Reuses ``adata.uns[f"{key}_colors"]`` when present and long enough;
    otherwise falls back to matplotlib tab20 indexed by sorted cluster id.
    """
    obs_col = adata.obs[key]
    cats = (
        list(obs_col.cat.categories)
        if hasattr(obs_col, "cat")
        else sorted(obs_col.astype(str).unique())
    )
    stored = adata.uns.get(f"{key}_colors")
    if stored is None or len(stored) < len(cats):
        stored = [_tab_palette[i % len(_tab_palette)] for i in range(len(cats))]
    return {cat: _to_hex(stored[i]) for i, cat in enumerate(cats)}


def _default_cluster_color(cid: str) -> str:
    """Tab-palette fallback when ``cid`` is not in the resolved map."""
    try:
        idx = int(cid)
    except (TypeError, ValueError):
        idx = 0
    return _to_hex(_tab_palette[idx % len(_tab_palette)])
```

## Reference subplot pattern

```python
import numpy as np

umap = adata.obsm["X_umap"]
cluster_ids = ["9"]  # the clusters for this cell type
cluster_color_map = _resolve_cluster_colors(adata, "leiden")

ax_ref.scatter(umap[:, 0], umap[:, 1], c="#e0e0e0",
               s=2, alpha=0.3, edgecolors="none")
for cid in cluster_ids:
    mask = adata.obs["leiden"] == cid
    if mask.sum() == 0:
        continue
    ax_ref.scatter(
        umap[mask.values, 0], umap[mask.values, 1],
        c=cluster_color_map.get(cid, _default_cluster_color(cid)),
        s=12, alpha=0.85, edgecolors="none", linewidths=0,
        label=f"C{cid}",
    )

# Force black legend text — otherwise it inherits the last scatter's colour
ax_ref.legend(loc="best", fontsize=7, framealpha=0.8, labelcolor="black")
```

## Why each parameter matters

| Param | Value | Why |
|---|---|---|
| `c=cluster_color_map[cid]` | required | Without it: matplotlib default cycle = same colour for every cluster |
| `s=12` | not `s=5` | Tiny dots blend into the grey base layer |
| `alpha=0.85` | not `0.7` | Slightly stronger so the colour reads against grey |
| `mask.values` | required | pandas Categorical boolean masks don't index numpy arrays directly |
| `mask.sum() == 0` early-exit | required | Empty scatter warns; skip silently |
| `legend(labelcolor="black")` | required | Otherwise the legend swatch text inherits the last scatter's colour and looks like "coloured text" |

## Diagnosing "cluster colour vanished"

If your Cluster ref subplot shows only grey points:

1. Open the h5ad and check `adata.uns["leiden_colors"]` exists and has the
   expected length:
   ```python
   import scanpy as sc
   a = sc.read_h5ad("path/to/auto.h5ad")
   print(a.uns.get("leiden_colors"))  # list of hex strings
   ```
2. If it's missing, run any `sc.pl.umap(adata, color="leiden")` call once
   first — scanpy populates the palette lazily.
3. Confirm the scatter call has `c=`. matplotlib's default colour cycle
   is the most common cause: `c="b"` or `c=cluster_color_map[cid]` —
   either way, **always pass it explicitly**.
