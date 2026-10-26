# Ovary: Granulosa_Cell vs Luteal Cell Disambiguation

Concrete diagnostic pattern for when `_audit_annotations` sees a cluster labelled
`Granulosa_Cell` but the cluster is actually **luteinized granulosa / luteal
cell** — a functional state where the canonical proliferative/follicular
granulosa markers are SILENCED and steroidogenic / LH-responsive markers are ON.

This is an **intra-lineage naming bias**: the audit panel for Granulosa_Cell
is dominated by *pre-ovulatory* granulosa markers (FSHR, AMH, CYP19A1), so
the audit can pass a luteal cluster as "KEEP Granulosa_Cell" because the
*steroidogenic* markers that distinguish luteal cells (LHCGR, MGARP) are not
in the panel. Same pattern as the documented Stalk_Endothelial limitation.

## Diagnostic Recipe (3-marker signature)

For any cluster labelled `Granulosa_Cell` (or `Granulosa`), check these
three markers. If the pattern matches, the cluster is luteal/luteinized:

| Gene | Pre-ovulatory Granulosa | Luteinized Granulosa / Luteal Cell |
|------|-------------------------|------------------------------------|
| **FSHR** | HIGH (>40% cells) | **LOW / NF** (lost upon LH surge) |
| **LHCGR** | LOW | **HIGH** (>50% cells; logfc > 5) |
| **CYP19A1** (aromatase) | HIGH | **LOW** (down-regulated post-LH) |

Plus the luteal-specific marker quartet:
- **STAR** (steroidogenic acute regulator) — HIGH in luteal, variable in granulosa
- **CYP11A1** — HIGH in luteal (also in theca, but combined with LHCGR = luteal)
- **INHA** (inhibin α) — HIGH in luteal (vs INHBB in pre-ovulatory granulosa)
- **MGARP** (also called C6orf218 / OVCH1-AS1-adjacent) — HIGHEST specificity
  for luteal cell; low in pre-ovulatory granulosa

If the cluster shows the right column for ≥3 of these 7 markers, the correct
label is `Luteal Cell` or `Luteinized Granulosa Cell` — NOT `Granulosa_Cell`.

## Worked Example: cluster 15 in luancao ovaries (scTE advanced)

303 cells, n_genes median=2921, mt% median=0.23% (NOT low quality).

| Marker | cluster 15 pct | other clusters | Verdict |
|--------|-------|----------------|---------|
| STAR | **98%** (mean 3.80) | 23.8% background | Luteal ✓ |
| CYP11A1 | **77%** (mean 4.98) | 2.8% | Luteal ✓ |
| LHCGR | **67%** (mean 4.90) | 1.5% | Luteal ✓ |
| INHA | **78%** (mean 2.02) | 18.1% | Luteal ✓ |
| MGARP | **72%** (mean 3.24) | 2-11% | Luteal ✓ |
| CYB5A | **92%** (mean 2.34) | 45.9% | Luteal ✓ |
| RBP1 | **84%** (mean 1.60) | — | Luteal ✓ |
| HSD3B2 | 33% (mean 1.53) | — | Luteal ✓ |
| CYP17A1 | **61%** (mean 4.30) | 1-2% | Theca-like, but luteal can express |
| --- | --- | --- | --- |
| FSHR | NF | — | Luteal ✗ (absent) |
| FOXL2 | NF | — | Luteal ✗ |
| AMH | 2% (mean -0.41) | 65% in cluster 3 | Luteal ✗ |
| CYP19A1 | 11% (mean 0.01) | 13% in cluster 3 | Luteal ✗ |
| INHBB | 2% (mean -0.21) | — | Luteal ✗ |

Compare with cluster 3 (canonical granulosa):
- AMH 65%, INHA 54%, CYP19A1 13%, STAR 22% — pre-ovulatory granulosa profile

Auto-annotation said "Granulosa" — wrong but not random. The LLM grabbed the
top DEGs (STAR, CYP11A1, LHCGR) which are all luteal markers but the LLM
doesn't have "Luteal Cell" as an option in its panel. So it falls back to
the closest parent label (`Granulosa_Cell`).

Correct annotation: **Luteal Cell** (or `Luteinized Granulosa Cell`).

## How to Update `_LINEAGE_MARKER_PANELS`

Add `Luteal_Cell` panel:

```python
"Luteal_Cell": ["STAR", "CYP11A1", "LHCGR", "INHA", "MGARP", "CYB5A", "HSD3B2", "RBP1"],
"Luteinized_Granulosa_Cell": ["STAR", "CYP11A1", "LHCGR", "INHA", "MGARP"],
```

Add a **dual-positive Granulosa_Cell check**: a cluster passing the
Granulosa_Cell panel (FSHR+/AMH+/CYP19A1+) should NOT also have
LHCGR-mean > 2x background — if it does, it's luteal. Without this, a
luteal cluster will pass Granulosa_Cell audit via the shared markers
(STAR, FDX1 are in the granulosa panel too) and the audit will say KEEP.

## Sample-Specific Origin Signal

Luteal clusters often come from a single sample (the one harvested at
post-ovulation / luteal phase). Worth checking `adata.obs[c15, 'sample']`
when a Granulosa-labelled cluster has all-1-sample composition —

```python
c15 = adata.obs['leiden'] == '15'
sample_comp = adata.obs.loc[c15, 'sample'].value_counts()
if len(sample_comp) == 1:
    print("Single-sample cluster — check sample harvest stage in metadata")
```

This is a soft signal, not a verdict — but combined with the marker
pattern it strengthens the case for "luteal cell from a luteal-phase
animal" rather than "weird granulosa".

## When NOT to Apply

- Cluster labelled `Theca_Cell` with STAR+/CYP11A1+/CYP17A1+ but LHCGR-/INHA-
  → it's theca, not luteal. Theca does NOT gain LHCGR (theca responds to LH
  but doesn't express high LHCGR; granulosa-derived luteal cells do).
- Cluster labelled `Stromal_Fibroblast` with STAR+/CYP11A1+ but no INHA/MGARP
  → it's likely contamination or the wrong lineage entirely.
- Cluster with high STAR but no LHCGR/CYP11A1/MGARP → check adrenal / Leydig
  contamination if non-gonadal tissue.

## Cross-Species Note

The marker panel works for **mammalian ovary** (human, mouse, rat, macaque,
cow, sheep, pig). For non-mammalian species (avian, fish), the panel
needs species-specific validation — avian granulosa cells have a different
luteinization programme; in fish, "luteal" cells are not a standard
category (most teleost fish don't form a corpus luteum).

## Why This Matters

The audit skill's "Limitations — Does NOT Catch" section already lists
intra-lineage naming bias as a known gap. This file documents the most
common instance: Granulosa_Cell vs Luteal Cell. Add similar files for
other common confusions:

- T_Cell vs NK_Cell (CD3D-high vs CD3D-low) — different mechanism
- M1 vs M2 macrophage — different mechanism
- AT1 vs AT2 epithelial — different mechanism

The Granulosa → Luteal case is the prototypical **activation-state
mislabeling**, where the LLM sees the cell-type signature is "steroidogenic
granulosa-ish" but doesn't know the cell has transitioned to luteal.