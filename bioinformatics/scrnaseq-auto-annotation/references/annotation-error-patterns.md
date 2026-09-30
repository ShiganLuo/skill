# Annotation Error Patterns — LLM Mislabel Catalog

Catalogue of recurring annotation errors observed in `mode_auto` runs on
macaque (Mmul_10) ovary and uterus data (2026-09). Use this as a
checklist when auditing any auto-mode output. Each entry: pattern
description, signature in expression table, diagnostic, and correction.

Most LLM mislabels fall into 4 root causes:

1. **Shared markers between related types** — gene is in both cell
   types' panels. LLM picks the "more famous" cell type (e.g.
   CXCL12 → MSC instead of capillary EC, CD163 → M1 instead of M2).
2. **Program/score confidence too low for ambiguous clusters** —
   score < 1.5 sends cluster to LLM free annotation; LLM reaches for
   well-known types rather than tissue-specific ones.
3. **Cross-tissue marker contamination** — markers that are specific
   in one tissue appear in the wrong context in another (e.g.
   mesothelial markers in ovary labelled generically as
   Mesothelial_Cell when they should be OSE-specific).
4. **Confusion between identity markers and state markers** —
   apoptosis (CYCS/CASP3), proliferation (MKI67/TOP2A), or activation
   (IL1B/TNF) markers picked up as the cluster's identity label.

---

## Pattern 1: NK_Cell → Cytotoxic_T_Cell / NK_T_Cell

**Signature**: cluster labelled `NK_Cell` with NKG7/GZMB/GNLY/CCL5 high
(cytotoxic program, shared between NK and CD8+ T) **AND** CD3D/CD3E/TRAC
> 1.5 in mean expression.

**Diagnostic**:
```
NK_Cell annotation + CD3D > 1.5 + CD3E > 1.5 + TRAC > 1.5
→ high probability Cytotoxic_T_Cell (or NK_T_Cell if mixed)
```

**Root cause**: NKG7/GZMB/GNLY are cytotoxic program markers shared
across NK and CD8+ T cells. LLM picks "NK_Cell" because it's the more
common label, but ignores CD3D/E/TRAC (TCR core components that NK
cells lack).

**Real NK markers**: NCR1 (NKp46), KLRD1 (CD94), KLRB1 (CD161),
KLRC1, FCGR3A (CD16). If these are NOT in the cluster's top 20
markers, it's not a pure NK cluster.

**Observed**: ovaries_cellranger cluster 18, ovaries_scTE cluster 15,
Uterus_scTE cluster 12 — all confirmed CD3D+CD3E+TRAC+ with NK
annotation. Correction: relabel to `Cytotoxic_T_Cell` or `NK_T_Cell`.

---

## Pattern 2: Mesenchymal_Stem_Cell → Endothelial_Cell (CXCL12+ capillary)

**Signature**: cluster labelled `Mesenchymal_Stem_Cell` with CXCL12 high
**AND** PECAM1/CDH5/VWF/ERG > 0.3 in mean expression.

**Diagnostic**:
```
MSC annotation + PECAM1 > 0.5 + CDH5 > 0.3 + VWF > 0.3
→ high probability Endothelial_Cell_Capillary
```

**Root cause**: CXCL12 is a known MSC marker (stromal stem cell
chemokine), but in endothelium CXCL12 marks capillary EC subtypes
that interact with MSC in the stem cell niche. LLM picks MSC because
CXCL12 is in the MSC literature, but ignores PECAM1/CDH5/VWF.

**References.tsv signal**: when references.tsv cites MSC papers
(PMID 19228591, 37400623, 38568832, 41288937) for a cluster whose
markers include PECAM1/CD34, the LLM is mixing two literatures.

**Observed**: Uterus_scTE cluster 1 — labelled MSC, expression shows
PECAM1=0.88, CDH5=0.63, ESAM=0.41, EMCN=0.75, ADGRL4=0.68. Parent
cluster is `Endothelial_Cell_Vascular` (cluster 0). Correction:
relabel to `Endothelial_Cell_Capillary`.

---

## Pattern 3: M1_Macrophage → Tissue_Resident_Macrophage / Decidual_Macrophage

**Signature**: cluster labelled `M1_Macrophage` with CD86 high **AND**
CD163 > 1.5 (M2 marker) in mean expression.

**Diagnostic**:
```
M1_Macrophage annotation + CD163 > 1.5 + CD86 > 1.5
→ Tissue_Resident_Macrophage (CD163+CD86+ double-positive)
```

**Root cause**: IL1B is a strong M1 marker but often low in tissue
macrophages. CD86 can be high in both M1 and some activated tissue
macrophages. CD163 (canonical M2) co-expressed with CD86 indicates
the dual-positive tissue-resident population found in decidua and
endometrium.

**References.tsv signal**: when M1_Macrophage references.tsv cites
papers titled "M2 macrophage differentiation" (e.g. PMID 28522271:
"Medroxyprogesterone acetate drives M2 macrophage differentiation"),
the LLM knew it was M2-leaning but defaulted to the M1 label because
CD86 was the stronger signal.

**Observed**: Uterus_cellranger cluster 7 — CD163=2.44, CD86=4.15,
IL1B ≈ 0.4. References cite both M1 and M2 papers. Correction:
relabel to `Tissue_Resident_Macrophage`.

---

## Pattern 4: Mesothelial_Cell → Ovarian_Surface_Epithelium (OSE)

**Signature**: ovary cluster labelled `Mesothelial_Cell` with MSLN,
PTGDS, ITLN1, CLDN3/4, ALDH1A1 high.

**Root cause**: mesothelium is the generic term for the cell type
covering body cavities. OSE is the ovary-specific mesothelium.
Calling it `Mesothelial_Cell` loses tissue context. Markers are
identical — only the name is wrong.

**Observed**: ovaries_cellranger cluster 16 (PTGDS=3.78, MSLN=5.53,
ITLN1=5.45), ovaries_scTE cluster 7 (PTGDS=3.74, ITLN1=2.78,
MSLN=5.45). Correction: relabel to `Ovarian_Surface_Epithelium`.

---

## Pattern 5: Theca_Externa_Cell → Perivascular_SMC / Myofibroblast

**Signature**: ovary cluster labelled `Theca_Externa_Cell` or
`Theca_Cell` with strong SMC markers (MYH11, ACTA2, TAGLN, DES,
CALD1) and **no** LHCGR/CYP17A1/CYP11A1/STAR.

**Diagnostic**:
```
Theca_Externa annotation + MYH11 > 0.5 + ACTA2 > 0.5 + TAGLN > 0.5
                                  + LHCGR < 0.5
→ Perivascular_SMC or Myofibroblast
```

**Root cause**: theca interna/externa are steroidogenic cells near
follicles. Theca externa is the outermost layer with fibroblast/SMC
features. LLM conflates the fibrous outer layer with true SMC
clusters that have no steroidogenic activity.

**Observed**: ovaries_scTE cluster 2 — MYH11=0.82, ACTA2=0.46,
CNN1=0.63, DES=0.80, MYLK=1.26 but LHCGR/CYP17A1/CYP11A1/STAR all
low. References.tsv is empty (LLM couldn't find theca externa
literature). Correction: relabel to `Perivascular_SMC`.

---

## Pattern 6: Stalk_Endothelial_Cell → Arterial_Endothelial_Cell

**Signature**: cluster labelled `Stalk_Endothelial_Cell` (angiogenic
tip-stalk terminology) without canonical stalk markers (STAB1, STAB2,
NRP1, ESM1, LAMA4) and without canonical tip markers (ACKR1, DLL4,
PLVAP). Just generic EC housekeeping genes.

**Root cause**: the tip-stalk paradigm is well-known in angiogenesis
literature, but endometrial vasculature is mostly mature/quiescent,
not actively angiogenic. LLM picks the "scientific-sounding" label
without verifying it's biologically appropriate for the tissue.

**References.tsv signal**: empty references.tsv on these clusters is
a strong red flag — LLM could not find supporting papers.

**Observed**: Uterus_cellranger cluster 12. Correction: relabel to
`Arterial_Endothelial_Cell` or merge into the main EC cluster.

---

## Pattern 7: Apoptosis/proliferation markers as identity markers

**Signature**: cluster's `key_markers` field contains CYCS, CASP3,
CASP9, BAX, BCL2 (apoptosis) OR MKI67, TOP2A, PCNA, CCNB1 (proliferation)
OR HSPA1A, HSPB1, DNAJB1 (heat shock) when these are used as identity
markers in the cell_type label.

**Diagnostic**: open `annotation_report.tsv`, look at the `key_markers`
column. If any cluster's key_markers are dominated by stress / cell
cycle / apoptosis genes, that's a state marker being misread as
identity.

**Root cause**: LLMs rank DEG and pick the top genes. When a cluster
is defined by its apoptotic state (e.g., late-luteinizing granulosa)
rather than its lineage, the top DEG are apoptosis genes, not
identity genes.

**Observed**: ovaries_scTE cluster 14 — labelled `Granulosa_Cell`
with key_markers = `CYCS,CASP3`. Reasoning text literally admits
"CYCS is a canonical marker for Apoptotic_Cell". Real CYP19A1/HSD17B1
expression is moderate (1.01/0.88) but lower than main Granulosa
cluster 4. Correction: relabel to `Luteinizing_Granulosa_Cell` and
move CYCS/CASP3 to a separate `quality_flag` field, not identity.

---

## Pattern 8: Epithelial_Luminal/Glandular over-splitting

**Signature**: 3+ clusters all labelled `Epithelial_Cell_Glandular`
or `Epithelial_Cell_Luminal` with near-identical marker panels
(EPCAM, KRT18, KRT19, CLDN3, CLDN4, WFDC2, SLPI all high). Only
distinguishing markers are minor (PIGR vs MSLN vs CLU).

**Root cause**: luminal vs glandular in endometrium is genuinely
hard to distinguish at scRNA level (single-cell loses tissue
architecture). LLM splits them into 3+ subtypes when the data only
supports 1-2.

**Diagnostic**: check the marker expression table — if 3+ clusters
have EPCAM > 1.5 AND KRT18 > 1.5 AND CLDN3 > 1.0, they're likely
one cell type.

**Observed**: Uterus_scTE clusters 15/19/21 — all show EPCAM/KRT18/
CLDN3/CLDN4/SLPI/AGR2 high; only PIGR (15/21) vs MSLN (19) varies.
Correction: merge or use suffix-only distinctions
(`Epithelial_Cell_Glandular_PIGR`, `Epithelial_Cell_Glandular_MSLN`).

---

## Pattern 9: Mural_Granulosa_Cell with stromal/neuronal DEG

**Signature**: ovary cluster labelled `Mural_Granulosa_Cell` with
CYP19A1/INHBA moderate but missing mural-specific markers (ITGA6,
AMHR2, INHBE, TAC3, LRRC17), AND top DEG contains stromal/neuronal
genes (RBFOX1, GPC5, NEK1, BTBD9).

**Diagnostic**: cross-check DEG list against canonical mural granulosa
markers. If top DEG includes neuronal/synaptic genes, the cluster
is likely a doublet or mixed.

**Observed**: ovaries_cellranger cluster 7 — top DEG
GPC5/RBFOX1/NEK1/USP36, mural markers absent. Correction: relabel
to `Granulosa_Stromal_Mixed` or merge with main Granulosa.

---

## Pattern 10: Tubal_Epithelium in ovary data

**Signature**: cluster labelled `Tubal_Epithelium` in an ovary
dataset (PAX8, FOXJ1, OVGP1 high).

**Diagnostic**: check tissue context. Tubal epithelium appearing in
ovary data = sampling contamination from the adjacent fallopian tube
fimbria.

**Root cause**: ovarian samples often include part of the fallopian
tube due to anatomical proximity. LLM doesn't apply contamination
heuristic.

**Observed**: ovaries_cellranger cluster 15 (265 cells, PAX8+FOXJ1+
OVGP1+). Correction: keep label but add contamination flag; do not
treat as a true ovary cell type.

---

## Pattern 11: Cycling-state cluster with lineage unspecified

**Signature**: cluster labelled `Proliferating`, `Cycling`, or
`Mitotic_*` with top DEG dominated by cell-cycle genes (MKI67, TOP2A,
CDK1, BIRC5, NUSAP1, CENPF, ASPM, TPX2, PTTG1, CDC20, histones
H1-3/4/5, H2AZ1/AZ2) and lineage markers partially dampened
(expressed but at lower % than non-cycling same-lineage siblings).

**Why lineage markers look damp**: cell-cycle program rewires ~30% of
the transcriptome at G2/M — lineage-specifying TFs are commonly
downregulated (Stuart et al. 2019 Satija lab; Scialdone et al. 2016
"Resolving the conundrum of cell-cycle-dependent transcription"). This
is NOT lineage loss — it's lineage masking.

**Diagnostic recipe** (verified 2026-09-20, ovaries_scTE cluster 9):
1. **Confirm cycling dominance**: compute S_score / G2M_score with
   `sc.tl.score_genes(adata, gene_list=s_genes / g2m_genes)`. If
   the cluster's G2M_score is positive and >2× any other cluster's,
   it's a genuine cycling population.
2. **Rule out oocyte / oogonia**: adult mammalian ovary has NO
   oogonia (deplete at birth). Germline markers DDX4, DAZL, NANOS3,
   SYCP1/3, PRDM1, POU5F1, ZGLP1 should be <10% if lineage is
   somatic. Oocyte markers (GDF9, ZP3, FIGLA, OOEP, NLRP5) are also
   absent in cycling somatic cells.
3. **Infer lineage via score + UMAP distance**: compute lineage
   scores (`sc.tl.score_genes`) for Granulosa_strong, Stromal,
   Endothelial, SMC, etc. Compare the cluster's score to the dataset
   mean — positive score + best_cluster = inferred lineage. Cross-
   validate with UMAP centroid distance (closest non-cycling cluster).
4. **Validate lineage-marker dampening**: compute
   `cluster / mean(non-cycling_same_lineage_clusters)` for each
   panel marker. Ratio ~0.5-1.1 (retained or modestly dampened)
   confirms lineage; ratio <0.1 across all panel markers would
   indicate loss.

**Label format**: `<Inferred Lineage> + state modifier`. Examples:
- `Cycling Granulosa Cell` (cluster 9 — retained CYP19A1/INHBB/FST
  + granulosa_strong score highest)
- `Cycling Endothelial Cell`
- `Cycling Stromal Cell`

Just `Proliferating` (LLM default) is over-broad — see user
feedback during ovaries_scTE audit.

**Observed**: ovaries_scTE cluster 9 (414 cells, MKI67=78%, TOP2A=79%,
CDK1=73%, BIRC5=67%; AMH=35.5%, CYP19A1=20.8%, INHBB=32.1%,
FST=41.5% — all retained vs C4/C3 quiescent Granulosa clusters at
similar or modestly lower levels; oogonia markers <6%). Correction:
relabel to `Cycling Granulosa Cell`.

---

## Pattern 12: Intra-VSMC state distinction (synthetic vs contractile)

**Signature**: cluster(s) labelled `Smooth_muscle` or
`Vascular_Smooth_Muscle_Cell` in a single-cell dataset. Multiple
clusters may share this label but occupy very different UMAP
positions. One cluster (synthetic) co-expresses contractile SMC
markers (ACTA2, MYH11, TAGLN, CNN1) AND ECM/fibrotic markers
(COL1A1, COL3A1, FN1, TGFBR3, ID4, IGFBP5, SFRP1, DCN). Other(s)
(contractile) express high contractile markers but LOW ECM markers
and may have PDGFRB / RGS5 pericyte features.

**Background literature**:
- Campbell & Campbell 2012 (Circ Res), Rensen et al. 2007 (Netherlands
  Heart J) — original "contractile vs synthetic" dichotomy, used 30+
  years.
- Yap et al. 2021 (PMC8545254) "Six Shades of VSMC" — modern review.
- Multiple scRNA-seq studies confirm contractile and synthetic VSMC
  occupy DISTINCT UMAP clusters (large UMAP separation is the
  expected pattern, not over-clustering). Examples:
  - PMC11669114 aortic dissection: cVSMC vs sVSMC listed as
    independent lineages.
  - Respir Res IPAH multi-omics: contractile / ECM-rich /
    proliferative VSMC subclusters in separate UMAP regions.
  - JCI Insight 2024 (GLS1): "VSMC (contractile)" and "VSMC
    (synthetic)" as independent cell type labels.
  - Cardiovasc Res 2024 (fibrous cap): Myh11+ contractile cluster
    vs Eln/Col8a1+ ECM cluster are UMAP-separated.

**Diagnostic**:
```
Smooth_muscle annotation + high ACTA2/MYH11/TAGLN/CNN1
  + (high vs low) COL1A1/COL3A1/FN1/TGFBR3/ID4/IGFBP5/SFRP1
  + (low vs high) PDGFRB/RGS5 (pericyte-leaning)
→ Split into Synthetic_VSMC (ECM-high) vs Contractile_VSMC (ECM-low)
```

**Why state matters in label**:
- `Synthetic_VSMC` implies active ECM production → fibrotic /
  wound-healing / remodeling context (relevant for ovary repair,
  corpus luteum formation, vascular remodeling).
- `Contractile_VSMC` implies quiescent contractile function (vessel
  tone regulation).
- Both are still VSMC (lineage = vascular smooth muscle), so the
  suffix `_VSMC` (not generic `_SMC`) anchors the lineage.

**Caveat: distinguish synthetic VSMC from myofibroblast**:
- Myofibroblast: ACTA2+ but MYH11/CNN1 LOW + POSTN/TNC/FAP HIGH.
- Synthetic VSMC: ACTA2+ AND MYH11/CNN1 HIGH (retains contractile
  markers) + ECM markers + POSTN/TNC/FAP LOW.
- Confirmed by checking whether contractile SMC markers (MYH11, CNN1,
  DES) are present >50% — if yes, it's VSMC, not myofibroblast.

**Observed**: ovaries_scTE cluster 1 (n=416) — ACTA2 99%, MYH11 99%,
TAGLN 100%, CNN1 93%, MYLK 98% (all retained), COL1A1 60%, COL3A1
66%, FN1 82%, ID4 90%, IGFBP5 99%, SFRP1 92%, TGFBR3 87% (synthetic),
POSTN 2%, TNC 1%, FAP 1% (NOT myo). Pericyte RGS5 2%, KCNJ8 6%.
Correction: relabel to `Synthetic_VSMC`. Cluster 7 and 16 (similar
contractile SMC, no ECM activation): relabel to `Contractile_VSMC`.

**Don't surface this as a "merge clusters" / "over-clustering" issue**
— even when two contractile_VSMC clusters have 95% identical marker
panels, the literature treats them as independent observations of the
same state. Re-clustering at lower resolution would risk losing the
granulosa / pericyte / SMC / stromal distinctions that ARE biologically
distinct. See SKILL.md pitfall "Don't surface over-clustering as an
unsolicited critique".

---

## Diagnostic Workflow

When auditing any auto-mode h5ad, work through these checks in order:

1. **Expression table**: read each cluster's mean expression of
   lineage-specific markers. If marker is in cluster's panel but
   expression < 0.3, the marker isn't actually expressed (panel is
   misaligned).
2. **Top DEG**: scan top 15 DEG. If dominated by rRNA
   (LSU/SSU_rRNA_eukarya), MT genes, or apoptosis/proliferation
   genes, the cluster may be low-quality or defined by state not
   identity.
3. **references.tsv**: count rows per cluster. 0 rows = LLM could
   not find supporting papers = suspicious. Also check whether the
   cited papers' titles actually mention the assigned cell type.
4. **Cross-cluster redundancy**: if 2+ clusters have near-identical
   marker panels, they're likely the same cell type split
   unnecessarily. Use correlation > 0.9 on marker expression as
   heuristic.
5. **Parent cluster check**: if a subcluster's parent is a different
   cell type, the subcluster is probably misannotated. Real
   subclusters should have the same lineage as their parent
   (parent=Stromal → subcluster should also be stromal-like).

---

## Recording Corrections: `cluster_annotations.json`

When the audit identifies corrections, record them per dataset in
`<output_dir>/plots/<pipeline>/auto/cluster_annotations.json`:

```json
{
  "7": {
    "original_cell_type": "M1_Macrophage",
    "corrected_cell_type": "Tissue_Resident_Macrophage",
    "reasoning": "Cluster 7 high expression of macrophage markers but co-expresses CD163=2.44 (M2) and CD86=4.15 (M1) at equally high levels. IL1B is low. CD163+CD86+ double-positive macrophages in endometrium are tissue-resident, not classical M1."
  }
}
```

Key: cluster_id (str). Values: original_cell_type (from
annotation_report.tsv), corrected_cell_type (proposed), reasoning
(cite specific expression values that drove the call).

**As of 2026-09-19, this file is applied natively by `mode_annotate`**
via `--cluster-annotations <path>` (no more manual `adata.obs.loc[...]`
hack). Call after `mode_auto` finishes:

```bash
python scRNAseq.py --mode annotate \
    --input  <output>_auto.h5ad \
    --output <output>_annotated.h5ad \
    --cluster-annotations <output_dir>/plots/<pipeline>/auto/cluster_annotations.json
```

The function writes an audit DataFrame to
`adata.uns["cluster_annotation_overrides"]` (round-trips through
h5ad) so reviewers can trace `original -> corrected -> reasoning`
later. Validation is strict — missing file / bad JSON / unknown
cluster id / missing cell_type column all raise (no silent skip;
project rule: "no fallback logic").

**Caveat for full audit JSONs**: if `cluster_annotations.json`
was authored against the full `annotation_report.tsv` cluster
list, some of those clusters may have been removed from the final
h5ad by `mode_auto`'s `whole_cluster_filter` (see SKILL.md pitfall
"Whole-cluster filter removes clusters from `leiden`"). The strict
mode_annotate will then raise `ValueError: cluster id 'N' not
found in adata.obs['leiden']`. Filter the JSON to an h5ad-specific
subset before calling, or write the JSON against the actual
h5ad cluster list (load h5ad, print
`adata.obs["leiden"].astype(str).unique()` first).

`mode_auto` itself does NOT yet auto-discover the JSON — call
`mode_annotate` AFTER `mode_auto` finishes.
Future: wire `mode_auto` to scan `<plot_dir>/auto/cluster_annotations.json`
and apply it before final h5ad write.

Established convention as of 2026-09-18 across all four macaque
ovary/uterus auto-mode runs.