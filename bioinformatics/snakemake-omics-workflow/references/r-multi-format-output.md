# R Script Multi-Format Output Pattern

When adding PNG/PDF (or other format) support to R bin scripts in the Omics project.

## CLI Argument

```r
parser$add_argument('--format', type = 'character', default = "png",
                    choices = c("png", "pdf"), help = 'output image format (default: png)')
args <- parser$parse_args()
fmt <- args$format
```

## Device-Switching Function Pattern

R device functions have **different parameter signatures** — you cannot just swap the device name:

```r
# png: pixels + resolution
png(filename = outfile, width = 2000, height = 1500, res = 200)

# pdf: inches (no res parameter)
pdf(file = outfile, width = 10, height = 7.5)
```

Wrap in a function with format parameter:

```r
updown_heatmap <- function(res_df, outfile, ..., format = "png") {
  # ... setup ...
  fmt <- match.arg(format, choices = c("png", "pdf"))
  if (fmt == "png") {
    png(filename = outfile, width = 2000, height = 1500, res = 200)
  } else {
    pdf(file = outfile, width = 10, height = 7.5)
  }
  # ... plotting ...
  dev.off()
}
```

## ggplot2 ggsave

`ggsave()` infers format from file extension automatically — no device switching needed:

```r
ggsave(outfile, plot = p, width = 8, height = 6, dpi = 300)
# Pass "volcano.pdf" → outputs PDF, "volcano.png" → outputs PNG
```

## Refactoring Checklist

When retrofitting multi-format support into an existing R script:

1. Add `--format` CLI arg (default "png", choices c("png","pdf"))
2. Store `fmt <- args$format` early in main body
3. For base R device calls (`png()`, `pdf()`, `svg()`): add format parameter to the function, switch device with if/else
4. For `ggsave()` calls: just change the file extension in the path
5. Replace ALL hardcoded `.png` in `paste0()` / `file.path()` calls with dynamic `fmt`
6. Search for remaining `.png` in the file — only roxygen comment examples should remain
7. Pass `format = fmt` to all device-switching function calls

## Pitfalls

- **png() vs pdf() parameter mismatch**: `png()` uses `width`/`height` in pixels + `res`; `pdf()` uses `width`/`height` in inches and has NO `res` parameter. Using `res` with `pdf()` silently fails or errors.
- **Missing dev.off()**: every device open must have a matching `dev.off()`. If the original code had `dev.off()` after `png()`, it works for `pdf()` too — but verify.
- **ggsave dpi with PDF**: `ggsave(..., dpi=300)` with a `.pdf` output ignores dpi (vector format). This is fine — no code change needed, but don't report dpi as "working" for PDF output.
- **Search for ALL `.png` references**: grep the entire file, not just the function you changed. Main body often has 15+ hardcoded `.png` paths across different modes (TEcount, TElocal, Count) and figure types (heatmap, volcano, MA, PCA).
