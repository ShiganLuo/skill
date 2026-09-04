## Peak-TE overlap analysis module pattern

Visualizes overlap between ChIP-seq peaks and Transposable Element (TE) annotations.
Compares IP vs Input samples across TE families (SINE, LINE, LTR, DNA, etc.).

**DAG position:** After MACS3 (peaks), alongside HOMER and deeptools heatmap — all consume peaks independently.

```
Step 7: MACS3 → narrowPeak ────┬→ Step 11: peak-TE overlap (per-sample + chart)
                                ├→ Step 10: HOMER annotation
                                └→ Step 9: deeptools heatmap
```

**Module structure:** `modules/peak_te_overlap/` with 3 files + `bin/intersect_te.py` + `bin/plot_te_overlap.py`.

**Rules:** `peak_te_overlap` (per-sample), `peak_te_overlap_chart` (cross-sample aggregation), `peak_te_overlap_result` (sentinel)

### Analysis pipeline

1. **Per-sample rule (`peak_te_overlap`):**
   - `bedtools intersect -a <narrowPeak> -b <TE_gtf> -wa -wb`
   - Parse GTF attributes for TE class (`class_id` > `family_id` > `gene_id`)
   - Count unique peaks overlapping each TE class
   - Output: overlap BED + per-sample overlap count TSV

2. **Aggregation rule (`peak_te_overlap_chart`):**
   - Load all per-sample TSVs → combined DataFrame
   - Grouped bar chart: X=TE families, Y=overlap ratio, grouped by IP vs Input
   - Output: PNG chart + combined TSV

### Config dict in subworkflow

```python
peak_te_overlap_config = {
    "ROOT_DIR": ROOT_DIR,
    "env": config.get("env", {}),
    "outdir": f"{outdir}/te_overlap",
    "logdir": logdir,
    "peaks_indir": macs3_config["outdir"],       # peaks
    "samples": ip_samples + input_samples,         # ALL samples
    "sample_ip_input_map": sample_ip_input_map,    # IP→Input pairs
    "Procedure": {
        "bedtools": config.get("Procedure", {}).get("bedtools") or "bedtools",
    },
    "genome": {
        "te_gtf": genome_ref.get("te_gtf"),        # TE annotation GTF
    },
}
```

### TE GTF format

GENCODE rmsk TE GTF attributes contain `gene_id`, `family_id`, `class_id`.
`class_id` is the high-level TE class (SINE, LINE, LTR, DNA, etc.).
The intersect script tries `class_id` first, falls back to `family_id`, then `gene_id`.

TE GTF path is declared in genome references:
```json
"GRCm39": {
    "te_gtf": "/path/to/GRCm39_GENCODE_rmsk_TE.gtf"
}
```

### Chart design

- **X-axis:** TE families sorted by mean overlap ratio (top 15)
- **Y-axis:** Overlap ratio (peaks overlapping TE / total peaks, 0-1)
- **Bars:** Grouped by protein — IP (solid) vs Input (hatched) for each
- **Color:** `Set2` colormap, one color per protein group
- **Output:** `{outdir}/te_family_overlap.png` + `.tsv`

### Node.py outfiles

```python
# Per-sample
outfiles.append(f"{outdir}/te_overlap/{ip_sample}/{ip_sample}_te_overlap_counts.tsv")
# Cross-sample
outfiles.append(f"{outdir}/te_overlap/te_family_overlap.png")
outfiles.append(f"{outdir}/te_overlap/te_family_overlap.tsv")
```

### Conda env

`bedtools>=2.30`, `matplotlib>=3.7`, `pandas>=2.0`, `numpy>=1.24`. Channel order: conda-forge before bioconda.
