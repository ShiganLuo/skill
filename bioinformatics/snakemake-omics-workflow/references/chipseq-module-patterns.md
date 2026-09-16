## deeptools enrichment heatmap module pattern

Two-step deeptools pipeline for ChIP-seq/ATAC-seq enrichment visualization.
Supports **three loci modes** — peaks (default), TSS (auto-generated from GTF), or custom BED.

**DAG position:** After MACS3 (peaks) and igv/bamCoverage (BigWig), alongside HOMER — both consume peaks independently.

```
Step 6: bamCoverage → BigWig ──┐
Step 7: MACS3 → narrowPeak ────┼→ Step 9: deeptools heatmap
                                └→ Step 10: HOMER annotation
```

**Module structure:** `modules/deeptools_heatmap/` with 3 files + `bin/generate_tss_bed.py`.

**Rules (all unconditional):** `generate_tss_bed`, `computeMatrix`, `plotHeatmap`, `deeptools_heatmap_result` (sentinel)
`generate_tss_bed` is defined unconditionally (no `if` wrapper). DAG skips it when `regions != "tss"` since nothing depends on it. Uses `gtf or "/dev/null"` as safe fallback input. See pitfall #52.

### Multi-mode loci support

The `Params.computeMatrix.regions` key controls which BED regions to analyze:

| Value | Mode | referencePoint | Description |
|-------|------|----------------|-------------|
| `"peaks"` (default) | reference-point | center | Per-sample MACS3 narrowPeak |
| `"tss"` | reference-point | TSS | Auto-generated from GTF via `bin/generate_tss_bed.py` |
| `/path/to/regions.bed` | auto | configurable | User-provided BED (TSS, gene body, custom loci) |

When `regions == "tss"`, the DAG triggers `generate_tss_bed` (defined unconditionally, see pitfall #52) which:
1. Reads `genome.gtf` from config
2. Runs `bin/generate_tss_bed.py --gtf <gtf> --output <bed> --flank <tss_flank>`
3. Produces a shared BED file at `{outdir}/_tss_regions.bed`

For custom BED files, users can switch to `scale-regions` mode via `Params.computeMatrix.mode`:
```json
{
    "regions": "/path/to/genes.bed",
    "mode": "scale-regions",
    "upstream": 3000,
    "downstream": 3000,
    "bodyLength": 5000
}
```

### Config dict in subworkflow

```python
deeptools_heatmap_config = {
    "ROOT_DIR": ROOT_DIR,
    "env": config.get("env", {}),
    "indir": macs3_config["outdir"],         # peaks
    "outdir": f"{outdir}/heatmap",
    "logdir": logdir,
    "bigwig_dir": igv_config["outdir"],      # BigWig tracks
    "samples": ip_samples,
    "Procedure": {
        "computeMatrix": config.get("Procedure", {}).get("computeMatrix") or "computeMatrix",
        "plotHeatmap": config.get("Procedure", {}).get("plotHeatmap") or "plotHeatmap",
    },
    "Params": {
        "computeMatrix": config.get("Params", {}).get("computeMatrix", {}),
        "plotHeatmap": config.get("Params", {}).get("plotHeatmap", {}),
    },
    "genome": {
        "gtf": config.get("genome", {}).get("gtf"),   # needed for TSS mode
    },
}
```

### Key Params

**computeMatrix:**
- `regions`: `"peaks"`, `"tss"`, or path to BED file (default `"peaks"`)
- `mode`: `"reference-point"` or `"scale-regions"` (auto-selected based on `regions`)
- `referencePoint`: `"center"`, `"TSS"`, `"TES"` (auto-selected for peaks/tss)
- `before`/`after`: bp flanking for reference-point mode (default 3000 each)
- `upstream`/`downstream`: bp flanking for scale-regions mode (default 3000 each)
- `bodyLength`: gene body length for scale-regions (default 5000)
- `binSize`: resolution in bp (default 10)
- `sortUsing`: sort order for heatmap rows (default "mean")
- `missingDataAsZero`: treat NaN as 0 (default true)
- `tss_flank`: flank around TSS for BED generation (default 1000)

**plotHeatmap:**
- `colorMap`: matplotlib colormap (default "YlOrRd")
- `heatmapHeight`/`heatmapWidth`: output dimensions (default 15/8)
- `whatToShow`: display elements (default "heatmap, colorbar, metagene")

### Mode-dependent command construction

```python
# In the computeMatrix run: block, select mode based on regions source:
if regions_cfg == "peaks":
    mode = "reference-point"; ref_point = "center"
elif regions_cfg == "tss":
    mode = "reference-point"; ref_point = "TSS"
else:
    mode = params.mode; ref_point = params.referencePoint

cmd = [params.computeMatrix, mode, ...]
if mode == "reference-point":
    cmd += ["--referencePoint", ref_point, "--beforeRegionStartLength", str(before), ...]
elif mode == "scale-regions":
    cmd += ["--regionBodyLength", str(bodyLength), "--upstream", str(upstream), ...]
```

### Conda env

`deeptools=3.5.1`, `matplotlib=3.7`, `numpy>=1.24`. Channel order: conda-forge before bioconda.

### Full PeakCalling config JSON additions

```json
{
    "Procedure": { "computeMatrix": null, "plotHeatmap": null },
    "Params": {
        "computeMatrix": {
            "regions": "peaks", "mode": "reference-point", "referencePoint": "center",
            "before": 3000, "after": 3000, "upstream": 3000, "downstream": 3000,
            "bodyLength": 5000, "binSize": 10, "sortUsing": "mean",
            "missingDataAsZero": true, "tss_flank": 1000
        },
        "plotHeatmap": {"colorMap": "YlOrRd", "heatmapHeight": 15, "heatmapWidth": 8, "whatToShow": "heatmap, colorbar, metagene"}
    },
    "genome": { "gtf": null }
}
```
