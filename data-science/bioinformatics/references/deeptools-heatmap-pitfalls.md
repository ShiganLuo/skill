# deeptools Heatmap Pitfalls

## plotHeatmap --whatToShow valid choices

Must be exactly one of:
- `plot, heatmap and colorbar`
- `plot and heatmap`
- `heatmap only`
- `heatmap and colorbar`

NOT `heatmap, colorbar, metagene` or any other combination.

## Values with spaces must be quoted in bash scripts

`--whatToShow 'heatmap and colorbar'` and `--plotTitle 'Pop5IP Peak Enrichment Heatmap'`
both contain spaces. When writing to .sh scripts via `" ".join(cmd)`, use `shlex.quote()`:

```python
f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")
```

## IP vs Input comparison heatmap

A single-sample heatmap (own peaks + own bigwig) is circular reasoning — signal is always
enriched at peaks defined BY that signal. Instead:

- Pass both IP bigwig and Input bigwig as `-S` files to `computeMatrix`
- `plotHeatmap` shows them side-by-side for comparison
- IP column shows enrichment, Input column shows background

## Region selection

- `regions="tss"` (default): TSS ± flanking, meaningful for any ChIP target
- `regions="peaks"`: top N peaks by score, useful for strongest binding sites
- `regions="/path/to/file.bed"`: custom regions with name column (col4), each unique name → separate heatmap
