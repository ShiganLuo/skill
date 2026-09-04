# deeptools plotHeatmap --whatToShow parameter

## Valid choices (exact strings)

```
"plot, heatmap and colorbar"
"plot and heatmap"
"heatmap only"
"heatmap and colorbar"
```

No other values are accepted. Notably `"heatmap, colorbar, metagene"` is NOT valid.

## Common pitfall: space-splitting in bash scripts

The value `"heatmap and colorbar"` contains spaces. When the `run:` block writes the cmd list to a bash script via `" ".join(cmd)`, bash word-splits it:

```bash
# What gets written:
plotHeatmap --whatToShow heatmap and colorbar --plotTitle ...

# What plotHeatmap sees: --whatToShow heatmap (then 'and' and 'colorbar' are orphan args)
```

**Fix**: wrap the value in single quotes when building the cmd list:

```python
cmd = [
    "plotHeatmap",
    "--whatToShow", f"'{params.whatToShow}'",  # quotes protect spaces
    "--plotTitle", plot_title,
]
```

## Config files to update when changing whatToShow

All three must agree:
1. `modules/deeptools_heatmap/deeptools_heatmap.smk` — the `or "..."` default
2. `modules/deeptools_heatmap/deeptools_heatmap.json` — module config template
3. `config/<workflow>.json` — user's workflow config (e.g. PeakCalling.json)

## Plot style reference

`plotHeatmap` generates heatmaps from `computeMatrix` output. For a combination plot (line plot + grouped box plot), do NOT use plotHeatmap — use custom matplotlib code instead. See the TE overlap chart pattern in `peak_te_overlap/bin/plot_te_overlap.py` for an example of a two-panel figure with shared x-axis.
