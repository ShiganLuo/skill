# Apptainer Container Isolation

## Problem

Host R library paths leak into container via `$HOME` mount, causing version conflicts (e.g. GOSemSim 2.20.0 from host vs 2.27.1 required by container's clusterProfiler).

## Solution

Use `--cleanenv --no-home` to isolate container from host environment:

```bash
apptainer exec --cleanenv --no-home \
  -B "$(pwd):$(pwd)" \
  /path/to/container.sif Rscript script.r -i input.csv -o output_dir
```

- `--cleanenv`: clears host environment variables
- `--no-home`: prevents mounting `$HOME` (avoids `~/R/library/` leaking)
- `-B $(pwd):$(pwd)`: bind-mount current directory so container can access files

## Verification

```bash
# Check container R lib paths (should only show container paths)
apptainer exec --cleanenv --no-home container.sif Rscript -e '.libPaths()'
# Expected: only /opt/conda/envs/.../lib/R/library

# Without --no-home (shows host leak):
apptainer exec container.sif Rscript -e '.libPaths()'
# Shows: /home/user/R/library  ← THIS IS THE PROBLEM
```

## go-kegg.r Specific Notes

- Uses `data.table::fread()` for auto-detect CSV/TSV separator (replaces `read.csv(sep="\t")`)
- `bitr()` wrapped in `tryCatch` — returns empty data.frame when no valid SYMBOL keys:
  ```r
  gene_df <- tryCatch(
    bitr(genes, fromType="SYMBOL", toType="ENTREZID", OrgDb=OrgDb, drop=TRUE),
    error = function(e) data.frame(SYMBOL=character(0), ENTREZID=character(0))
  )
  ```
- Early return in `run_pipeline` when 0 up+down genes (prevents plot_back_to_back crash)
- In `plot_back_to_back`, check `nrow(up_df)==0 && nrow(down_df)==0` BEFORE dplyr operations — empty data.frames with no columns crash `arrange()` and `mutate()`
- Directory naming: use `go_kegg` not `go_macaque` — no species info in directory names
