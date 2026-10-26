# DDR / genome-stability pathway sets: biological grouping and mouse marker panels

Depth for steps 4 and 5c — biology behind the 13 Reactome GSI sets.

## Set grouping by repair fidelity (interpret contrasts in these classes, not alphabetically)

- Faithful/template-dependent repair: HDR (HRR), MMR
- Fast/error-prone repair: NHEJ, TLS (Y-family polymerases)
- Lesion load / replication stress: Fanconi anemia (ICL repair, replication-fork stability), ATR activation, DSB response
- Mitotic/phase-anchored: spindle checkpoint, cell-cycle checkpoints, chromosome maintenance (phase-composition sensitive — annotate, don't over-interpret)
- Composition-hazard: telomere maintenance (~70% replication histones; test only the shelterin/CST/Tert/Dkc1/RPA core)

## Repair-machine axis: read rate-limiting factors, not set means

The set-level GSVA contrast can be flat while the underlying repair MODE shifts. Two
per-gene checks that resolve more than the sets:

- **NHEJ vs HDR cores with set-specificity control**: genome-wide median Δ(sample−peers)
  must be ~0 for a set-level shift to be real (a nonzero global offset = technical bias).
  A real mode shift shows as: NHEJ set median offset clearly positive AND Δ>0.3 gene
  fraction ~2x the genome-wide rate, driven by rate-limiting factors (Lig4, Prkdc/DNA-PKcs,
  Polm) — not the abundant scaffold subunits (Ku70/80 are high everywhere and can move the
  OPPOSITE direction). HDR side: Brca1 and Rad51 can move oppositely; read the core
  (Rad51/Brca2) separately from Brca1.
- **Named-gene pitfalls**: Cdc73 (PAF1 complex, cell-cycle gene) vs Ccdc73 (coiled-coil,
  unrelated) are DIFFERENT loci one letter apart — GTF gene_name matching is exact, but
  hand-built marker lists and eyeballed greps conflate them.

## Mouse state marker panels (mean log2TPM reading rules in SKILL.md step 4)

- 2C/totipotent-like: Zscan4d + Zscan4 family, Zfp352, Tcstv1/Tcstv3, Dux, Dppa3, Eif4a3l2, Gm29216. Zscan4d and Tcstv family are near-zero in ESC but >4 log2 in true 2C-like — they are the discriminative markers, not Dppa3 (high everywhere).
- Naive pluripotent: Pou5f1, Nanog, Sox2, Esrrb, Klf4, Tbx3
- Primed: Fgf5, Otx2, Dnmt3a/3b

## Proliferation / phase panels (build with zero overlap vs tested sets; report dropped count)

- Proliferation: Mki67, Top2a, Pcna, Mcm2-7, Tyms, Rrm2, Fen1, Cenpf, Birc5, Ccna2, Ccnb1/2, Ccne1/2, E2f1, Ube2c, Aurkb, Plk1, Bub1, Cdk1, Espl1, Nusap1, Prc1, Stmn1 (~18 of 28 typically drop against DDR sets)
- S-phase: Rrm2, Tyms, E2f1/2, Aspm; G2/M: Ccnb1/2/3, Aurkb, Plk1, Cenpf, Espl1, Smc4, Top2a, Kif20b, Hmgb2 (filter to present + zero-overlap at runtime)

## Repair-balance ratios (confound-resistant primary metrics)

- HDR:NHEJ — repair fidelity balance; embryo-like states run lower
- FA:HDR — lesion-load vs template-dependent repair
- NHEJ:(HDR+MMR) — fast vs faithful repair

Compute on absolute log2TPM set means; expect ~2.0-2.5 for HDR:NHEJ in mouse stem states (ESC ~2.2-2.4, 2C-like lower).

## Damage-status axis (transcriptome reads response, not load)

- Stress axis: Atf3, Jun, Fos, Gadd45a, Pmaip1, Rela (AP-1/NF-kB + DDR-responsive)
- p53-target axis: Cdkn1a, Mdm2, Sesn2, Zmat3 (Pmaip1 overlaps the stress axis — keep it in only one panel)
- Reading rule: stem cells run LOW baseline stress (mouse mESC ~2.8-4.9 mean log2TPM); a group above baseline is RESPONDING to a damage/stress signal. Culture stress, dissociation, and library stress light the same program — claim "activated p53/stress program" only; lesion load itself requires gamma-H2AX foci or comet assay.
- State-intrinsic test: the axis must correlate positively with the state-marker score across same-state samples; a negative correlation (state-marker-highest sample scoring lowest on stress) reclassifies the signal as culture-related, not state biology.
- Per-sample MAD screening (robust z |>2| full-cohort + within-group peer deviation) finds which SAMPLE carries the signal when a group contrast is confounded by one odd culture — verify replicates agree (Δ<0.1) before calling it real.
- Observed HDR-NHEJ baselines — compare within-species gradients only, never absolute values across species: mouse somatic ~-0.85, stem +0.6 to +0.75; human somatic ~-2.20, stem -1.8 to -1.5 (human stem cells stay negative — species baselines differ).

## Expected embryo-like DDR signature

Fast repair + lesion load up (NHEJ, Fanconi, DSB response), faithful repair flat-to-lower (HDR, MMR, ATR), G2/M-anchored sets low from phase composition (S-high/G2M-low cell-cycle structure), plus 2C markers high. The 4 "reverse" sets in such a pattern are proliferation passengers (r(score, prolif) > +0.4), not pathway suppression.