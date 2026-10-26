# Ovarian Cell Type Markers for annotate_all.py

## Newly Identified Cell Types

### Cumulus Cells (卵丘细胞)
- Specialized granulosa cells surrounding the oocyte
- Key markers: FST, NR5A2, PPARG, CRHBP, GRB14, HAS2, PTX3
- FST (Follistatin) and NR5A2 are the most specific
- Often misannotated as "Unknown" without specific markers

### Luteal Cells (黄体细胞)
- Corpus luteum cells, steroidogenic function
- Key markers: STAR, CYP11A1, HSD3B1, PTCH2, GPC5
- STAR and CYP11A1 are involved in steroidogenesis
- GPC5 may also appear in Smooth_muscle clusters (check context)

### Mesothelial Cells (间皮细胞)
- Ovarian surface epithelium (OSE) is mesothelial in origin
- Key markers: MSLN, ITLN1, WT1, UPK3B
- MSLN and ITLN1 are the most specific
- **DO NOT use PKHD1L1** — also expressed in Endothelial cells (false positive)
- Literature: Nature 2022, Cell transcriptomic atlas of Macaca fascicularis

### Myofibroblast (肌成纤维细胞)
- Cells expressing BOTH smooth muscle and stromal markers
- Key markers: ACTA2, MYH11, TAGLN, POSTN, IGFBP5, SFRP1
- **Distinction from Smooth_muscle:**
  - Myofibroblast: DCN+, SFRP1+, IGFBP5+ (stromal features)
  - Smooth_muscle: DCN-, SFRP1- (pure SM)
- **PCA/UMAP distance:** Closer to Stromal than Smooth_muscle
- **Doublet score:** Low (<0.05) — NOT doublets
- Literature: PMC 2024, mouse ovary mesenchymal cell subtypes
- **Problem:** Automatic annotation often fails due to marker overlap with Smooth_muscle
- **Solution:** Use `--manual-annotation` to override

### Lymphatic Endothelial (淋巴内皮细胞)
- Lymphatic vessel endothelial cells, distinct from blood endothelial
- Key markers: MMRN1, CCL21, PROX1, LYVE1, PDPN, CAVIN2, FLT4
- **Distinction from Blood Endothelial:**
  - Lymphatic: MMRN1+, CCL21+, PROX1+, LYVE1+, PDPN+
  - Blood: VWF+, ERG+, KDR+, FLT1+, EMCN+
- Literature: Wigle & Oliver (1999) Cell PMID:10499794
- **Always separated in UMAP** — biologically meaningful, not technical artifact
- **annotate_all.py markers:** `"Lymphatic_endo": ["MMRN1","CCL21","PROX1","LYVE1","PDPN","CAVIN2","FLT4"]`

### Higher Resolution for TE-Dominated Clusters
When ERVK_high is >20% of total cells, use higher resolution (1.5 instead of 0.8) to split it into subclusters. This may reveal hidden cell types (e.g., Cumulus, Pericyte, T_cell that got grouped with TE-high cells).

## Marker Overlap Warnings

| Marker | Cell Type 1 | Cell Type 2 | Issue |
|--------|-------------|-------------|-------|
| PKHD1L1 | Mesothelial | Endothelial | False positive — remove from Mesothelial |
| GPC5 | Luteal | Smooth_muscle | Context-dependent — check other markers |
| DCN | Stromal | Smooth_muscle (Cluster 2) | Co-expression suggests transitional state |
| ACTA2, MYH11, TAGLN | Smooth_muscle | Myofibroblast | Shared markers — use manual override |

## TE-Dominated Clusters (scTE-specific)

### ERVK_high
- Top markers are ERVK transposable elements (MacERVK2, MacNERVK2)
- Gene count and UMI are NORMAL (not low quality)
- Does NOT match any known cell type (not Granulosa, not Luteal)
- May be biased towards specific samples
- Keep as ERVK_high — do NOT assign cell type names

### Alu_high
- Top markers are Alu transposable elements
- May have lower gene count (sometimes <1000)
- Often biased towards specific samples
- Keep as Alu_high — do NOT assign cell type names

### Sample Distribution Check
For TE-dominated clusters, always check sample distribution:
```python
for ct in ['ERVK_high', 'Alu_high']:
    mask = adata.obs['cell_type'] == ct
    print(adata.obs[mask]['sample_id'].value_counts())
```
If heavily biased (>70% from one sample), may indicate sample-specific technical issues.

## Macaque Ovary Literature

- Nature 2022: Cell transcriptomic atlas of Macaca fascicularis — mesothelial cells in ovary
- Wang et al. 2020: Single-cell transcriptomic atlas of primate ovarian aging
- Zhao et al. 2026: Cell Discov. PMID:42552301 — ovarian cell types
- Wigle & Oliver 1999: Cell PMID:10499794 — lymphatic endothelial markers
- PMC 2024: Mouse ovary mesenchymal cell subtypes — myofibroblast identification
