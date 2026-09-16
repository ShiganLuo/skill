# R Script `--format` Flag Pattern

## For ggplot2-based scripts (ggsave)

`ggsave()` auto-detects format from file extension. Just pass the extension dynamically:

```r
parser$add_argument("--format", type = "character", default = "png",
                    choices = c("png", "pdf"), help = "Output image format (default: png)")
args <- parser$parse_args()
fmt <- args$format

# In function calls:
outfile = file.path(outdir, paste0(prefix, "_volcano.", fmt))
ggsave(outfile, plot = p, width = 8, height = 6, dpi = 300)
```

## For base R device scripts (png/pdf)

When using explicit device calls (e.g., `pheatmap` needs a device open):

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

## Propagation pattern

```
CLI --format arg → fmt variable → passed to all plot functions → file extension / device switch
```

Every function that saves a plot needs a `format` parameter. The caller passes `fmt` through.

## Pitfalls

- **`ggsave` handles format automatically** — no device switching needed for ggplot2 plots. Only `pheatmap`/base R plots need explicit `png()`/`pdf()` device calls.
- **Default must match original** — if the script originally used `.png`, default to `"png"`. If `.jpeg`, default to `"jpeg"`. Never change the default without user request.
- **Choices must include the original format** — e.g., if script used `.jpeg`, choices should be `c("jpeg", "png", "pdf")`.
- **`match.arg` for device functions** — use `match.arg(format, choices = c("png", "pdf"))` to validate before opening the device.
- **PDF dimensions** — `png()` uses pixels + res; `pdf()` uses inches. Convert: `width_inches = width_px / res`. E.g., `png(width=2000, res=200)` → `pdf(width=10)`.