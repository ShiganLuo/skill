# deeptools Heatmap Enrichment Module

## Purpose
Compute signal matrix around genomic regions and plot enrichment heatmaps for ChIP-seq data.

## Pipeline Position
```
... → MACS3 (narrowPeak) + bamCoverage (BigWig) → deeptools_heatmap → ...
```

## Module Structure
```
modules/deeptools_heatmap/
├── deeptools_heatmap.smk      # 4 rules: generate_tss_bed, computeMatrix, plotHeatmap, deeptools_heatmap_result
├── deeptools_heatmap.json     # Config template
├── deeptools_heatmap.yaml     # deeptools=3.5.1, matplotlib=3.7
└── bin/
    └── generate_tss_bed.py    # GTF → TSS BED (argparse CLI, reusable)
```

## Three Region Modes (via `Params.computeMatrix.regions`)

| Value | Mode | referencePoint | Description |
|---|---|---|---|
| `"peaks"` (default) | reference-point | center | Per-sample MACS3 narrowPeak |
| `"tss"` | reference-point | TSS | Auto-generated from GTF via `generate_tss_bed.py` |
| `/path/to/regions.bed` | auto | configurable | User-provided BED (gene bodies, custom loci) |

## Key Design Decisions

1. **All rules unconditional** — `generate_tss_bed` is always defined (not wrapped in `if`). DAG skips it when regions != "tss". Input fallback: `gtf or "/dev/null"`.

2. **Input function resolves regions** — `get_regions(wildcards)` returns the correct BED based on config. This is the routing logic, NOT conditional rule definition.

3. **Mode auto-detection in run: block** — `computeMatrix`'s `run:` block selects `reference-point` vs `scale-regions` and the appropriate `referencePoint` based on `regions_cfg`. This is runtime logic, fine inside `run:`.

4. **TSS BED generation** — `bin/generate_tss_bed.py` parses GTF, extracts transcript TSS ± flank, deduplicates, outputs BED6. Reusable standalone.

## Config Params

```json
{
    "Params": {
        "computeMatrix": {
            "regions": "peaks",           // "peaks" | "tss" | "/path/to/bed"
            "mode": "reference-point",    // "reference-point" | "scale-regions"
            "referencePoint": "center",   // "center" | "TSS" | "TES"
            "before": 3000,               // reference-point: upstream distance
            "after": 3000,                // reference-point: downstream distance
            "upstream": 3000,             // scale-regions: upstream distance
            "downstream": 3000,           // scale-regions: downstream distance
            "bodyLength": 5000,           // scale-regions: gene body length
            "binSize": 10,
            "sortUsing": "mean",
            "missingDataAsZero": true,
            "tss_flank": 1000             // TSS mode: ±bp around TSS
        },
        "plotHeatmap": {
            "colorMap": "YlOrRd",
            "heatmapHeight": 15,
            "heatmapWidth": 8,
            "whatToShow": "heatmap, colorbar, metagene"
        }
    }
}
```

## Subworkflow Integration

```python
deeptools_heatmap_config = {
    "ROOT_DIR": ROOT_DIR,
    "env": config.get("env", {}),
    "indir": macs3_config["outdir"],       # peaks from MACS3
    "outdir": f"{outdir}/heatmap",
    "logdir": logdir,
    "bigwig_dir": igv_config["outdir"],    # BigWig from bamCoverage
    "samples": ip_samples,
    "Procedure": {
        "computeMatrix": ...,
        "plotHeatmap": ...,
    },
    "Params": {
        "computeMatrix": config.get("Params", {}).get("computeMatrix", {}),
        "plotHeatmap": config.get("Params", {}).get("plotHeatmap", {}),
    },
    "genome": {
        "gtf": config.get("genome", {}).get("gtf"),  # needed for TSS mode
    },
}
```

## CLI Override Examples

```bash
# TSS-centered heatmap
--Params.computeMatrix.regions=tss --Params.computeMatrix.before=5000 --Params.computeMatrix.after=5000

# Custom BED file
--Params.computeMatrix.regions=/path/to/gene_bodies.bed --Params.computeMatrix.mode=scale-regions

# Change colormap
--Params.plotHeatmap.colorMap=Blues
```
