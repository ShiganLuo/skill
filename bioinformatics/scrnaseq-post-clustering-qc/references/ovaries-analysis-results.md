# Ovaries scTE Analysis Results (2026-09-07)

## Summary

Analyzed ovaries scTE data with post-clustering QC filtering. Key findings:

1. **Filtered 4,873 cells (24.6%)** using cell-level QC (min_genes=800, min_counts=3000)
2. **Higher resolution clustering** (1.5 vs 0.8) split ERVK_high into sub-clusters
3. **Discovered 5 new cell types**: Myofibroblast, Lymphatic_endo, Mesothelial, Cumulus, Luteal
4. **Cluster 2 (Myofibroblast)** has SM+Stromal co-expression (22.8%) but low doublet score (0.05) — NOT doublets

## Final Cell Type Proportions (14,943 cells)

| Cell Type | Count | % |
|-----------|-------|---|
| ERVK_high | 3373 | 22.6% |
| Stromal | 3229 | 21.6% |
| Endothelial | 2659 | 17.8% |
| Smooth_muscle | 1534 | 10.3% |
| Pericyte | 828 | 5.5% |
| Cumulus | 669 | 4.5% |
| Alu_high | 481 | 3.2% |
| Myofibroblast | 392 | 2.6% |
| Macrophage | 363 | 2.4% |
| Proliferating | 302 | 2.0% |
| Luteal | 292 | 2.0% |
| Mesothelial | 252 | 1.7% |
| Lymphatic_endo | 222 | 1.5% |
| Epithelial | 198 | 1.3% |
| T_cell | 149 | 1.0% |

## Differential Abundance Analysis (luanchao-21310 vs luanchao-11238)

Chi-square: p = 0.00 (extremely significant)

| Cell Type | FC | log2FC | p-value | Direction |
|-----------|-----|--------|---------|-----------|
| ERVK_high | 3.19 | 1.67 | 3.49e-262 | ↑ in 21310 |
| Cumulus | 2.91 | 1.54 | 7.50e-39 | ↑ in 21310 |
| Alu_high | 1.92 | 0.94 | 2.33e-12 | ↑ in 21310 |
| Epithelial | 0.01 | -6.41 | 5.84e-60 | ↓ in 21310 |
| Mesothelial | 0.11 | -3.21 | 4.32e-45 | ↓ in 21310 |
| Smooth_muscle | 0.29 | -1.80 | 1.25e-125 | ↓ in 21310 |

## Key Observations

1. **ERVK_high is NOT a doublet artifact** — quality metrics are normal (genes=2523-2625)
2. **ERVK_high biased toward sample 21310** (77.5%) — may indicate sample-specific TE expression
3. **Alu_high Cluster 8 was low quality** (genes=648, rRNA markers) — filtered out
4. **Myofibroblast (Cluster 2)** has SM+Stromal co-expression but low doublet score — likely a real transitional population, not doublets
5. **Lymphatic Endothelial** separated from blood Endothelial — biologically meaningful distinction

## Files

- Annotated: `hystera_scTE_v2_annotated.h5ad`
- Markers: `hystera_scTE_v2_markers.tsv`
- Plots: `plots/scTE/cluster_annotate/`
