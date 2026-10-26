# Recurring LLM Cell-Type Confusion Patterns

Empirical patterns observed when auditing `mode_auto` outputs (macaque uterus +
ovary, 4 h5ads, 2026-09-19). Each pattern is a **specific** cluster-vs-annotation
mismatch the LLM confidently produces from marker evidence that is technically
present but misread. These are NOT "missing types hidden by generic DEGs" — the
DEGs are tissue-specific, but the LLM chooses the wrong tissue. This file is
the audit companion to `data-driven-deg-detection.md`.

## Why this file

`data-driven-deg-detection.md` catches the case where LLM ignores tissue markers
because generic DEGs dominate. This file catches the case where tissue markers
ARE present and the LLM still picks the wrong label — because two cell types
share markers and the LLM defaults to the more "textbook" one.

## The seven recurring patterns

### 1. NK ↔ Cytotoxic T cell

**Markers the LLM sees** (CD3D, CD3E, TRAC, CD3G, PTPRC, NKG7, GZMB, GNLY,
CCL5) → all very high. NKG7+GZMB+GNLY+CCL5 are cytotoxic-program markers shared
by NK and CD8+ T cells. LLM defaults to "NK_Cell" because the prompt asks for
innate immune cells first.

**Decision rule**: if CD3D/E/G/TRAC ≥ 1.5 (log-normalized mean) → Cytotoxic_T
or NK_T, NOT NK. NK cells should be CD3-complex-negative.

**Diagnostic script**:
```python
T_markers = ["CD3D", "CD3E", "CD3G", "TRAC", "CD2"]
NK_only_markers = ["KLRD1", "KLRB1", "NCR1", "NCR3", "FCGR3A"]  # not always in HVG
t_score = sum(adata.obs[adata.obs.leiden == cl][m].mean() for m in T_markers if m in adata.var_names)
n_score = sum(adata.obs[adata.obs.leiden == cl][m].mean() for m in NK_only_markers if m in adata.var_names)
# If t_score > 5 and n_score < 1, this is T cell, not NK
```

**Observed**: 4 h5ads, NK_Cell clusters had CD3D mean = 3.0–5.6, TRAC = 1.7–5.1.
All were T cells mislabeled.

### 2. M1 ↔ M2 Macrophage (and tissue-resident vs inflammatory)

**Markers the LLM sees**: CD74, CD163, CD68, CD86, LYZ, CTSS, TYROBP, AIF1,
C1QA, C1QB, IL1B. CD163 (M2) and CD86 (M1) often BOTH high in uterine
decidual macrophages — this is the canonical tissue-resident phenotype, not
either pole of the M1/M2 axis.

**Decision rule**: if CD163 > 1.0 AND CD86 > 1.0 AND IL1B < 0.5 → tissue-resident
or M2-leaning, NOT M1. If IL1B high AND CD163 low → genuine M1.

**Observed**: Uterus_cellranger cluster 7 "M1_Macrophage" (940 cells):
CD74=2.09, CD163=**2.44**, CD86=4.15, C1QA=2.81, LYZ=3.11, IL1B=−0.11.
LLM pattern: pick CD86 as M1 evidence, ignore CD163.

**Diagnostic**: report `CD163`/`IL1B` ratio. Ratio > 3 with CD163 high → call it
Tissue_Resident_Macrophage / Decidual_Macrophage. Many uterine/ovarian
macrophages are decidual/tissue-resident and don't fit M1/M2.

### 3. Mesenchymal Stem Cell ↔ Vascular Endothelial Cell (CXCL12)

**Markers the LLM sees**: CXCL12, PECAM1, CDH5, CD34, EMCN, ADGRL4, ESAM.
CXCL12 is the canonical MSC marker AND a major EC chemokine (especially in
endometrial vascular endothelium). LLM pattern: pick MSC because CXCL12 is
listed first in `key_markers`.

**Decision rule**: if PECAM1+CDH5+ESAM+EMCN all > 1.0 → EC, NOT MSC. MSC
should have CDH5−/PECAM1−.

**Observed**: Uterus_scTE cluster 1 "Mesenchymal_Stem_Cell" — top DEGs actually
were EC housekeeping (PECAM1=0.88, CDH5=0.63, ESAM=0.41, EMCN=0.75). The
references.tsv cited CXCL12/MSC papers but ignored the EC housekeeping.

**Diagnostic**: when MSC is suspected, check PECAM1+CDH5 together. If both
> 0.5, this is EC.

### 4. Mural Granulosa ↔ Mural Stromal (the "missing ITGA6" problem)

**Markers the LLM sees**: CYP19A1, AMH, INHBA, FOXL2, FST, HSD17B1. The LLM
correctly identifies "granulosa", then splits pre-ovulatory/cumulus/mural, and
the "mural" cluster ends up with stromal DEGs (GPC5, RBFOX1, PCDH11X, HOMER1)
because mural granulosa cells physically sit on the basement membrane and share
some ECM/neuronal transcripts with surrounding theca stroma.

**Decision rule**: if the cluster has > 30% of its DEGs from
generic_stromal/neuronal (PCDH, HOMER, RBFOX, NEK) AND the canonical mural
markers (ITGA6, AMHR2, TAC3, INHBE, LRRC17) are missing → re-label as
Granulosa_Stromal_Mixed or merge into the main Granulosa cluster.

**Observed**: ovaries_cellranger cluster 7 "Mural_Granulosa_Cell" — CYP19A1=1.13
(only moderate), FSHR=0.14 (low!), AMH=0.93. No references for "mural" found.

**Diagnostic**: check FSHR in the candidate cluster. If FSHR < 0.5, it is NOT
mural granulosa (which should be the FSHR-high granulosa subtype).

### 5. OSE/mesothelial ↔ tubal epithelium (PAX8+FOXJ1 test)

**Markers the LLM sees**: EPCAM, KRT19, KRT18, CLDN4, CLDN3, MSLN, WFDC2,
PTGDS, ALDH1A1, ITLN1. Both OSE (ovarian surface epithelium) and tubal
epithelium share this core. LLM pattern: pick "Mesothelial_Cell" or generic
"Surface_Epithelium" because the markers are dominated by mesothelial markers
(MSLN/PTGDS/ITLN1), missing the tubal-specific PAX8/FOXJ1/OVGP1 signal.

**Decision rule**:
- If PAX8 > 0.5 AND FOXJ1 > 0.5 AND OVGP1 > 0.5 → tubal epithelium.
- If MSLN > 3 AND ITLN1 > 1 AND PTGDS > 2 AND PAX8 < 0.3 → OSE / mesothelial.
- If MSLN/ITLN1/PTGDS are all moderate (1-2) → ambiguous, may need additional
  markers (KRT17, LHX2, WNT4 for OSE; FOXJ1, TUBB4B for tubal).

**Observed**: ovaries_cellranger cluster 16 "Mesothelial_Cell" had no references
and only 1 ITLN1 ref. Cluster 7 in ovaries_scTE was named "Surface_Epithelium"
(ambiguous) but markers were MSLN=5.45 + PTGDS=3.74 + ITLN1=2.78 → clearly OSE.

**Diagnostic**: ALWAYS require PAX8 + FOXJ1 for tubal; OSE is the default
when those are absent.

### 6. Theca externa ↔ Perivascular SMC (LHCGR absence)

**Markers the LLM sees**: ACTA2, MYH11, TAGLN, CALD1, ACTG2, DES, CNN1, TPM2.
These are ALL smooth muscle markers. The LLM pattern: "theca externa is the
outer layer of the follicle, similar to smooth muscle" → labels as Theca_Externa.

**Decision rule**: Theca_Externa should have LHCGR (low), CYP17A1 (absent/very
low), and COL1A1 (collagen-rich). Pure SMC has MYH11+ACTA2+DES+CNN1 all > 1
and COL1A1 < 0.3.

**Observed**: ovaries_scTE cluster 2 "Theca_Externa_Cell" — ACTA2=0.46,
MYH11=0.82, DES=0.80, MYLK=1.26, CNN1=0.63. Zero theca-specific references.
This was Perivascular_SMC, not theca.

**Diagnostic**: if all SMC markers are simultaneously high (>0.4) AND no
LHCGR/CYP17A1/STAR → it's SMC, not theca.

### 7. Stalk EC ↔ generic vascular EC (no real stalk marker exists in many tissues)

**Markers the LLM sees**: EFNB2, CXCL12, CDH5, PECAM1, EMCN, ERG, FLT1, CD34,
JAM2, ADGRL4. The "tip-stalk" dichotomy is from angiogenesis literature
(sprouting assays), but in steady-state tissue data it's rarely cleanly visible.
LLM pattern: see EFNB2 + CXCL12 → label as "Stalk_Endothelial_Cell".

**Decision rule**: real stalk markers in tissue data are STAB1, STAB2, NRP1
(shared with tip), ESM1, LAMA4. If cluster has ONLY generic EC markers
(PECAM1/VWF/CDH5/ERG) and none of STAB1/STAB2/ESM1 → it's just vascular EC.
Consider relabeling Arterial_EC (if EFNB2 high + CXCL12 high) or Venous_EC
(if NR2F2/NRP2 high).

**Observed**: Uterus_cellranger cluster 12 "Stalk_Endothelial_Cell" — top DEGs
were ARL15, PECAM1, TCF4, PTPRM (all generic EC). references.tsv empty (0
supporting refs).

**Diagnostic**: refuse to use the "tip/stalk" label unless STAB1, STAB2, ESM1,
or LAMA4 are in the cluster's top DEGs.

## Diagnostic checklist — what to look at per cluster

When auditing `annotation_report.tsv`, compute these 5 numbers for each cluster
and check against the patterns:

```python
import scanpy as sc, numpy as np, pandas as pd

adata = sc.read_h5ad("path/to/auto.h5ad")
cl_arr = adata.obs["leiden"].astype(str).values
X = adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X

def cluster_mean(g):
    if g not in adata.var_names: return np.nan
    return float(X[:, adata.var_names.get_loc(g)].mean())

# Per cluster, check the key signatures
markers = {
    "T_cell_signature": ["CD3D","CD3E","CD3G","TRAC"],
    "NK_signature":     ["KLRD1","KLRB1","NCR1","FCGR3A"],
    "EC_housekeeping":  ["PECAM1","CDH5","ESAM","EMCN"],
    "MSC_CXCL12":       ["CXCL12"],
    "Macrophage_M1":    ["IL1B","TNF"],
    "Macrophage_M2":    ["CD163","MRC1","ARG1"],
    "Granulosa_classic":["CYP19A1","AMH","FSHR","FOXL2"],
    "Tubal_specific":   ["PAX8","FOXJ1","OVGP1"],
    "OSE_mesothelial":  ["MSLN","PTGDS","ITLN1","ALDH1A1"],
    "Stalk_EC":         ["STAB1","STAB2","ESM1","LAMA4"],
    "SMC_pure":         ["ACTA2","MYH11","DES","CNN1"],
    "Theca_classic":    ["LHCGR","CYP17A1","STAR"],
}
for cl in sorted(adata.obs["leiden"].unique()):
    print(f"cluster {cl}: {adata.obs[adata.obs.leiden == cl]['cell_type'].iloc[0]}")
    for k, gs in markers.items():
        vals = [cluster_mean(g) for g in gs]
        print(f"  {k:20s}: {np.nanmean(vals):+.2f}")
```

## Cross-cluster confusion matrix

When the LLM has to choose between two similar types, it picks the type whose
name appears earlier in `tissue_cell_types` (Step 0 query) OR the one whose
top marker is most associated with the disease context (PCOS, endometriosis).
The default fallbacks:

| LLM default | Loses to | Trigger if also present |
|-------------|----------|--------------------------|
| NK_Cell | Cytotoxic_T_Cell | CD3D > 2 |
| M1_Macrophage | Tissue_Resident | CD163 > 2 + IL1B < 0.5 |
| Mesenchymal_Stem_Cell | Endothelial_Cell | PECAM1+CDH5 > 1.5 |
| Mural_Granulosa_Cell | Stromal_Cell | FSHR < 0.5 + generic stromal DEGs |
| Mesothelial_Cell | Ovarian_Surface_Epithelium | always (OSE ⊂ mesothelial) |
| Theca_Externa_Cell | Perivascular_SMC | SMC markers all > 0.5, LHCGR < 0.3 |
| Stalk_Endothelial_Cell | Vascular_EC (arterial) | no STAB/ESM/LAMA markers |
| Schwann_Cell | Neuronal_Mixed | GRIK2/NRXN1/SYT1 high (neuronal) |

## How to add a new pattern

When the audit reveals a new recurring confusion:

1. Find at least 2 independent runs/clusters where the LLM made the same mistake.
2. Identify a "trapped marker" — one that the LLM overweights and that points
   to the wrong type. The marker must be plausibly associated with the correct
   type (that's why the LLM picks it).
3. Identify a "decisive marker" — a marker that ONLY appears in the correct
   type and is absent in the wrong type. This is the rule the LLM should have
   used but didn't.
4. Add a row to the cross-cluster confusion matrix.
5. Document the diagnosis in this file with at least one concrete observation.

## Why this is an audit file and not a pipeline fix

These patterns require **biological judgment** to override the LLM. The
`specificity-missed` check in `cluster-marker-specificity-scoring` only fires
when the LLM picks a type with 0 specific markers; here the LLM picks a type
WITH specific markers (just the wrong ones). Auto-correcting in the pipeline
would require hardcoding the trapped-vs-decisive marker pairs, which violates
the "no tissue-specific hardcoding" rule of the annotation pipeline.

The right place for these rules is:
- **Tier 1** (auto): the trapped markers should be DOWN-weighted in the
  specificity table when paired with the decisive marker. E.g. if CD3D > 2
  and NK_only markers all < 1, the prompt should explicitly instruct "this
  cluster has CD3D high + NK_only markers low → Cytotoxic_T_Cell, not NK_Cell".
  This is a generic logic, not tissue-specific.
- **Tier 2** (manual review): when the LLM annotation triggers a known
  confusion pattern, flag for human review in `decision_log.md`.

## References found in this audit (2026-09-19)

4 h5ads audited:
- Uterus_cellranger_auto.h5ad: 15 clusters, 7 suspicious, 4 confirmed errors
- Uterus_scTE_auto.h5ad: 19 clusters, 6 suspicious, 4 confirmed errors
- ovaries_cellranger_auto.h5ad: 19 clusters, 8 suspicious, 5 confirmed errors
- ovaries_scTE_auto.h5ad: 16 clusters, 6 suspicious, 4 confirmed errors

All confirmed errors were one of the 7 patterns above. references.tsv was
empty (0 refs) for 9 of the confirmed-error clusters — when the LLM can't
find supporting literature, that's a strong signal of a forced/extrapolated
annotation.