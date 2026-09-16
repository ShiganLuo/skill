# R Script Image Format Support (--format flag)

## Pattern
Add `--format` CLI arg to R scripts that generate plots, defaulting to the original format.

## ggsave-based plots (volcano, MA, PCA, bar plots)
`ggsave()` auto-detects format from file extension. Just change the extension:

```r
# CLI arg
parser$add_argument("--format", type = "character", default = "png",
                    choices = c("png", "pdf"), help = "Output image format")

# In function, replace hardcoded extension
outfile = file.path(outdir, paste0(prefix, "_volcano.", format))
ggsave(outfile, plot = p, width = 8, height = 6, dpi = 300)
```

## Explicit device calls (pheatmap, base R plots)
For functions that need explicit `png()`/`pdf()` device calls:

```r
updown_heatmap <- function(res_df, outfile, format = "png") {
  fmt <- match.arg(format, choices = c("png", "pdf"))
  if (fmt == "png") {
    png(filename = outfile, width = 2000, height = 1500, res = 200)
  } else {
    pdf(file = outfile, width = 10, height = 7.5)
  }
  pheatmap::pheatmap(heatmat, ...)
  dev.off()
}
```

## Passing format through function chains
When format needs to flow through nested function calls:
- Add `format = "jpeg"` param with appropriate default to each function
- Pass `format = args$format` in the main call chain
- Use dynamic extension in all `file.path()` / `paste0()` calls

## Choice conventions
- Gene expression plots (DESeq2): `png` / `pdf`, default `png`
- GSEA plots: `jpeg` / `png` / `pdf`, default `jpeg` (original behavior)