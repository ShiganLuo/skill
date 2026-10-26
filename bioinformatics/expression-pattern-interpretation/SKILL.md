---
name: expression-pattern-interpretation
description: Use when expression heatmap or gene-set patterns look odd.
---

# When to use

- A heatmap (GSVA/ssGSEA/mean-z/module scores) shows unexpected colors: replicates disagree, one group matches an unrelated group, a stem sample looks differentiated
- The user asks why samples score the way they do, or challenges a biological explanation of expression data ("不是很有说服力")
- A figure combines samples from multiple studies, species, or cell states
- A gene-set/enrichment result is about to be published and the user asks whether a confound (proliferation, batch, library type) was stripped

# Always-on rules

1. **结论分层**: report claims as established (with numbers) / ruled out (with the test) / unresolved (with the discriminating experiment). An n=1 contrast is not a mechanism — never present "state X represses Y" from one sample pair without a discriminating test. The user rejects plausible stories.
2. **When challenged, run the decisive test and explicitly retract wrong claims** — do not defend. Retracting three overstated claims and replacing them with one controlled conclusion is the expected response. If the challenge exposes a real hole (e.g. an unstripped confound), tighten the paper claim to only what survives the controlled retest — do not re-assert the original gradient.
3. **Every figure states its metric** (relative vs absolute) in the caption. Relative and absolute metrics answer different questions; KS/rank scores and mean-z/mean-log can even disagree in direction.
4. **Paste-ready prose is one tight academic paragraph**: result -> (if challenged) anomaly -> decisive evidence (3 strongest numbers) -> decision. No process narration, no self-endorsement, no restating the question. Two-species sensitivity results go into ONE combined paragraph (methods once, then per-species findings in the same flow) — not per-species bullet lists; bullets live only in internal notes, never in paste-ready prose.
5. **Statistical language by convention, not emphasis**: |rho| 0.2-0.4 is "中等/中等强度", not "强"; do not inflate a coefficient when the persuasive evidence is the shape (monotone decile profile, per-set residuals) — lead with the shape, give the coefficient as support.
6. **Deliverables consolidate to ONE README.md in the output dir**: methods + results tables + tiered conclusions + paste-ready statements (Chinese body + English Methods), plus a repro command block. Delete intermediate scripts/tables/one-off reports that the README supersedes; keep only scripts that re-run end-to-end and the tables the README cites.
7. **Figure series follow the approved sibling**: when a same-series figure already exists (e.g. the mouse version), clone its layout on the first render — same textwrap width + rotation for x labels, legend at top-center outside the axes, footnote placement, figsize ratio. Do not invent a new style and iterate under review. Within any figure the bars are the visual center: large plot area, compact tick labels (wrap long pathway names to ~20 chars/line via textwrap, rotation 30; never bare full names at 45°), and never let a legend or oversized tick labels cover or dominate the plot. Do NOT merge species into one combined figure unless asked — per-species figures sharing ONE caption file (a `*_caption.md` in the output dir, top-row/bottom-row wording) is the approved form.

# Procedure

## 1. Decode the metric before reading colors

Classify the plotted statistic: relative (z-score, rank, KS/ssGSEA enrichment) or absolute (log2 TPM/counts). For any color-based claim, recompute the absolute per-set score (mean log2(TPM+1) of set genes per sample) as a table and compare against the figure.

Pitfall — same color ≠ same level in z-scored cross-cell-type panels: per-gene z-scores are anchored to the panel mean/SD, so one extreme cell type stretches the scale and two same-colored samples can sit 10x apart in absolute terms. Verify absolute values first; the anomaly often dissolves or relocates.

Pitfall — pale cell ≠ negative score: the colorbar is stretched by the row's extremes, so a POSITIVE mean-z (e.g. +0.10, above half the panel) renders near-white next to +0.5 leaders and reads as "low activity". Before explaining a pale cell, read the numeric table; the question often becomes "why is the leader high" not "why is this low".

Quick triage — column-wide vs row-specific: if the suspect sample is depressed across ALL gene sets (compare its mean-z on every row), the cause is sample state/quality (cell-cycle fraction, culture state, library), not the pathway; corroborate with sample-to-sample correlation. Only a row-specific deviation on an otherwise-normal sample is candidate pathway biology.

## 2. Establish provenance before biology

Read the meta/design file first (GEO accession in data_id/design columns, SE vs PE, contaminated_organism). Track study/state/protocol per sample; annotate figure columns with study and state (e.g. `TLSC2[166216·2C-like]`).

Pitfall — same group name ≠ same batch: each study ships its own control, so "three mESC samples" may be two experiments. Correlation follows study, not group label.

## 3. Check replicate consistency at transcriptome level

Sample correlation on top-5000 variable genes (log2 scale). Same-study replicates should be ≈0.98–0.99. If "replicates" disagree, they are different states or quality — model them as separate groups; never average them.

Pitfall — stem-cell cultures are heterogeneous populations and bulk RNA-seq averages states, so two "replicates" can sit at different points of a state continuum (ESC-like vs 2C-like).

## 4. Triage the anomaly with marker panels + QC

Check in order: identity markers (is the label correct), state markers, lineage markers, feeder/contamination markers, detected-gene count (TPM>1), top-5 expressed genes (composition). This separates state effect vs contamination vs quality. Panels: `references/stem-cell-state-markers.md`.

## 4b. Rule out RNA degradation (long-gene artifact) before pathway biology

When one sample is depressed across many pathways, test the library before the cell. Degraded RNA loses coverage toward the 5' end, so long genes are systematically underestimated — and genome-stability/DDR gene sets are long-gene-rich, so their scores collapse without any biology.

1. Library metrics: parse the aligner's Log.final.out per sample (unique-mapping %, multi-mapping %, average insert size). A degraded library shows uniquely low unique% + high multi% + short inserts versus its peer replicates, at normal depth.
2. Decisive genome-wide test: Spearman correlate gene Length (featureCounts `Length` column) with the sample's deviation from its peer-group mean (log2TPM). A healthy library is ~0; degradation is strongly negative and monotone across length deciles. Run a healthy replicate through the same test as a control.
3. Quantify per gene set: regress deviation on log10(length), then average the residuals per set. The degradation bias is monotone but NOT linear in log-length, so also report a nonparametric (length-decile) correction — the linear residual understates how much was artifact. If a pathway's apparent collapse mostly vanishes in the residual, the heatmap pattern is the artifact, not regulation.
4. Direct BAM confirmation: `samtools depth -a -r <region>` over 5'/mid/3' gene-body thirds for long set genes vs short housekeeping controls. Degradation signature: long-gene 5' coverage drops to ~0.3x of healthy samples while short controls stay ~1.1x, and 3'/5' coverage ratios exceed replicates.
5. Short genes are immune, so 2C-like/pluripotency markers (Zscan4, Dppa3) score high in the same degraded sample — a "pluripotency strong + genome stability collapsed" split inside one sample is itself a degradation red flag, not a state shift. Panels: `references/ddr-pathway-biology.md`.

Verdict: exclude the sample from cross-sample z-scored figures or rebuild the library; on a degraded library, report residual set-level signals as uninterpretable rather than biology. Recipe: `references/rna-degradation-qc.md`.

## 5. Test specificity before claiming pathway regulation

Rank all genes by the contrast's log2FC (sample vs its peer group). Report each gene set's median percentile in that global distribution, plus control panels matched for regulatory logic (S-phase/E2F-regulated genes vs constitutive genes vs housekeeping).

- Set moves with its program's control panel AND a constitutive control set does not move → passenger of the program (e.g. "DNA repair down" that is really the S-phase module down).
- Set moves beyond its program's control panel → pathway-specific.

Pitfall — audit the set's composition before treating any set as a constitutive control: Reactome genome-stability sets are not pure pathway biology. REACTOME_TELOMERE_MAINTENANCE (~104 mouse genes) is ~70% replication-dependent histones (H2bc/H2ac/H3/H4 families) plus replication machinery (Pcna, Pola1, Pold); only ~31 genes are core telomere biology (shelterin/CST/Tert/Dkc1/RPA). The histone fraction dilutes the core signal, so set-level scores track proliferation and any whole-set conclusion must be retested on the core-gene split. Check gene content for cell-cycle genes; a true control set must be constitutive by composition, not by name.

## 5b. Cell-cycle analysis on genome-stability sets: saturation audit + robustness check, not confound removal

CONSTRUCT GATE — decide the estimand BEFORE running any removal. Genome stability is a general property of the cell state: a dividing state's replicative-stress response and maintenance activity ARE part of its stability phenotype, so proliferation is a downstream correlate of state, not a confounder to regress out. (a) For the descriptive state claim (e.g. a potency-gradient figure), full-set scores are the PRIMARY evidence; the cell-cycle analysis answers only two measurement questions — which sets are saturated (audit) and whether the gradient survives without cell-cycle genes (robustness). (b) For index/cross-system component use (e.g. a genome-stability index), non-confounding is a component-SELECTION criterion — prefer structural ratios or core-gene subsets — which does not retroactively water down the descriptive figure. Never word the analysis as 'controlling for proliferation' in either case.

Mechanics (both framings): genome-stability GSVA sets overlap heavily with cell-cycle genes (26-97% across the 13 Reactome DDR sets in a real panel). Run this whenever the compared states differ in growth rate:

1. Proliferation score per sample: mean z of ~30 canonical markers (Mki67, Top2a, Pcna, Mcm2-7, Tyms, Rrm2, Fen1, Cenpf, Birc5, Ccna2, Ccnb1/2, Ccne1/2, E2f1, Ube2c, Aurkb, Plk1, Bub1, Cdk1, Espl1, Nusap1, Prc1, Stmn1). Compare group means and state WHERE the difference sits — typically somatic-vs-stem, not within stem states; a confound between two states only exists if their proliferation differs.
2. Quantify set composition: % of each set's genes found in Reactome "Cell Cycle" (map human GMT symbols to mouse case-insensitively via an upper-case index).
3. Recompute every set score (per-gene z across samples, then mean over set genes) after removing cell-cycle genes. Report per set: r(score, proliferation) before/after and the key group contrast before/after. Do NOT tier evidence strength by |r| with proliferation — under the state-phenotype construct a set that stays proliferation-linked is reflecting the state's biology, not a weakened claim; the only hard gate is set size: <10 genes remaining = SATURATED by cell-cycle genes, and neither its full nor cleaned score is ever read as repair activity anywhere in the analysis. Optionally core-gene subsets (e.g. shelterin/CST only) as a second control.
4. Interpretation — the analysis has two outputs: (i) the saturation list (which sets cannot be read as repair activity), (ii) the robustness verdict. Direction preserved after removal = the full-set gradient is not an artifact of cell-cycle composition — write this as the robustness sentence. Sets moving from ~0 to small positive are UNMASKING (the full set diluted the signal) — this strengthens the full-set claim, never qualifies it. Under the state-phenotype construct the full-set contrast is primary evidence — never downgrade it to 'directional evidence' because r with proliferation stays high. Read the actual contrasts; never assume a gradient held or failed without the numbers.
5. Build the proliferation score from markers with ZERO overlap against the tested sets (drop markers found in any set before scoring) — overlapping markers (Pcna, Mcm, Cdk1 are in most DDR sets) inflate r and invite a circularity objection. Report how many markers were dropped.
6. Pick the canonical Cell Cycle set, not a sibling: GMTs carry many near-duplicate entries ("Cell Cycle", "Cell Cycle Mitotic", "Cell Cycle Checkpoints", "Diseases of mitotic cell cycle"). Use the top-level "Cell Cycle" entry (Reactome R-HSA-1640170, 657 human genes) and record the ID in the README — picking by fuzzy grep silently grabs a different entry.
7. Ortholog mapping for cross-species set removal: symbol-based uppercase lookup (`{g.upper(): g}` index of the target matrix, look up each source symbol uppercased). Human Cell Cycle 657 -> 630 mouse hits; 1:many orthologs hit ALL mouse paralogs (conservative for removal — cannot under-remove), but orthologs with different symbols are missed (only acceptable because removal, not quantitation, is the goal; state this caveat in the README). Record the method — it will be asked about.
8. A set whose contrast moves from ~0 to small positive after removal is UNMASKING (the full set diluted the signal), not contradiction — say so explicitly; a sign flip positive->negative is the dangerous case. Regression correction (score ~ group + proliferation) is the reviewer-suggested alternative but usually infeasible here: n~15, group vs proliferation near-collinear (little within-group variation), plus study batch. Prefer gene removal and give the infeasibility reason in one Methods sentence instead of presenting regression results.
9. Pitfall — apply sample EXCLUDE on ORIGINAL names BEFORE display RENAME: renames can collide with excluded names (e.g. display-rename hFibroblasts4→hFibroblasts1 while original hFibroblasts1 is an excluded total-RNA library) and silently drop kept samples — the group ends up empty or short with no error. Filter exclusions on original column names first, then strip prefixes and rename for display.

Pitfall — when the user challenges the PURPOSE of the removal, run the direction-comparison table before defending anything: side-by-side full-set vs cleaned contrast per set, flag any sign flip. If no conclusion changes direction (common: unmasking only), the 'decoupling-based' qualification (e.g. 'human is weaker because |r| stays high, so directional evidence only') is UNSUPPORTABLE and must be retracted in the same reply — proliferation is a downstream correlate of state, so a high r is not evidence against the contrast. Only measurement-level outputs survive the challenge: the saturation list (sets with <10 genes left) and the robustness verdict.

Pitfall — never cite a GSEA/set-enrichment result for a SATURATED set: the overlap makes the score track proliferation, so a significant NES can point OPPOSITE to the repair biology (e.g. a replication-stress set scoring 'down' in fast-dividing cells because it is really a cell-cycle module and the comparison is against even-faster-dividing cells). Before quoting any set-level result into a narrative, check its saturation status from the audit table.

Answer-first rule: when the user asks a WHY question, answer THAT question first and only it. Two shapes: (a) 'why does the figure NOT show X' — first state the figure shows only what the GMT/result contains (check the GMT line count vs figure rows); (b) 'why do we need to do X (e.g. remove a confound)' — the answer is the MOTIVATION grounded in the project's downstream use case (what the score feeds into, e.g. an index that must measure its target because a later validation stage breaks otherwise), with the measured numbers that justify it — NOT a menu of algorithms or a diagnosis of the data. Analysis beyond the question, prescriptive advice, and method proposals come only after, and only if asked. Analytical documents go to the path the user names (e.g. project data/), not wherever the script ran.

Pitfall — grouping defines the conclusion: pooling cell states of different potency into one bar averages away the top-type signal. In human data the hTBLC-vs-hESC contrast was consistently positive across all 7 reliable DDR sets, but pooling hTBLC with 8C-like ci8CLC into one "toti" group collapsed it to ~0. When a cell type sits at the top of a potency hierarchy (user will say "全能性更强"), give it its OWN group/bar before interpreting any pooled null as "no difference". Otherwise two parallel scripts/figures diverge mid-session — keep ONE script per species and one figure per question; split groups inside it (the TSV gains per-state columns, the figure gains a bar), never a second script that re-does the same pipeline with a different grouping.

Pitfall — reviewer suggests regression, gene removal wins here: n~15 with group vs proliferation near-collinear (little within-group variation) makes the regression coefficient unidentifiable, and study batch (multiple GEO sources per state) adds a confound larger than proliferation. Prefer gene-set removal + zero-overlap proliferation score; give the infeasibility in one Methods sentence citing the collinearity premise instead of presenting regression numbers.

Pitfall — do not remove a confound before justifying WHY, and phrase removal correctly: for a state-phenotype claim, 'removal' is not a step at all — full-set scores are primary and the cell-cycle analysis is worded as a measurement-validity audit + robustness check (saturation list + direction-preserved verdict), never as 'controlling for proliferation'. For index/cross-system use, the motivation is the score's downstream USE (e.g. it feeds a genome-stability index whose later tumor/pan-cancer validation — an extreme-proliferation system — becomes uninterpretable if the sets track proliferation with mixed signs); handle by component SELECTION (structural ratios 5c, core-gene subsets), not by regression. Removing also has a COST to state: if the low-proliferation state IS the biology (totipotent-like cells grow slowly), 'removal' re-scopes conclusions to non-proliferation-dependent DDR differences and discards that real state effect.

## 5c. Diagnose BEFORE deconfounding: classify each set's deviation by its r(score, proliferation)

Before choosing any removal algorithm, compute the zero-overlap proliferation score (5b step 1/5) and correlate every set score against it across samples. This one table decides both the biology and the method:

- **Proliferation-positive sets (r > +0.4)**: for INDEX purposes the state contrast on these sets is a passenger — regression/gene-removal CANNOT rescue them when proliferation and state are near-collinear (small n, little within-group variation); reclassify them out of the component pool. For descriptive state claims this r is NOT disqualifying (see 5b construct gate) — full-set scores stand as primary evidence.
- **Proliferation-negative sets (r < −0.4)**: the contrast survives AGAINST the proliferation direction (state has lower proliferation yet higher score) — direction is confound-proof, but keep the absolute-scale effect size; report the z figure only as display.
- Check the phase structure too, not just total proliferation: S-phase vs G2/M marker scores per group. A G2/M-rich set scoring low in one state can be cell-cycle PHASE composition, not pathway suppression — annotate those sets as phase-dependent rather than running removal.

Then, for the biology, regroup sets by what they DO rather than by the observed direction: e.g. DDR sets split into faithful repair (HDR, MMR), fast/error-prone repair (NHEJ, TLS), and lesion-load/replication-stress modules (Fanconi/ICL, ATR, DSB response). A pattern like "fast repair + lesion load up, faithful repair flat-to-down" is itself the state's biology (embryo-like reliance on template-free repair) even though half the sets moved the other way — do not narrate it as "most pathways up, 4 anomalies".

**Structural RATIO metrics beat any deconfounding algorithm when proliferation × state is collinear (the common case the user's public-data experience confirms: removal underperforms there)**: ratios of sets with shared proliferation drive (HDR:NHEJ, FA:HDR, NHEJ:(HDR+MMR)) cancel the first-order proliferation effect, are computable at n=2/group, and carry direct biological meaning (repair-fidelity balance). Verify on absolute log2TPM means, not z scores. Prefer validating a ratio on an independent public dataset over re-running set-level removal; report z-heatmap conclusions only alongside the absolute table.

## 5d. Evaluate cell states along calibrated dimensions, not by outlier hunting

When the user asks to biologically evaluate/compare cell classes (somatic vs pluripotent vs totipotent-like), deliver a GROUP x DIMENSION table with a normal-baseline calibration for each dimension — not a per-sample outlier screen. Dimensions: (1) repair-mode choice HDR-NHEJ (plus SSBR panel), (2) damage status (stress axis + p53-target axis), (3) proliferation (total + S/G2M phase split — see 5c/5b), (4) stress SOURCES (TE de-repression + replication-stress core machinery — see below). Calibrate each dimension's normal value per cell class FIRST (somatic HDR-NHEJ negative, stem positive; stem stress baseline low), then read group positions against the calibration.

Stress-source dimension (endogenous pressure the state faces): (a) TE transcriptional de-repression from the TEcount matrix — sum TE rows (names contain ':') over gene-count rows per sample, score log2((TE_reads+1)/(gene_reads+1)) per group; potency-gradient TE families (ERVL/UCON etc.) are expected to be highest in totipotent-like/8C-like groups and this is the state's endogenous replication-stress and insertion-risk source, not a QC problem. (b) replication-stress core machine (Atr/Atrip/Chek1/Clspn/Topbp1/Rpa1-3 panel, ~10-12 curated genes) — track whether its between-state difference matches the proliferation difference in magnitude; matching magnitudes = no EXCESS replication stress beyond the cell-cycle structure.

When the user asks the pressure-and-coping question ("这些细胞面临什么压力、如何应对"), structure the report as three acts — (1) stress sources (TE + fast replication), (2) coping programs (HDR-mode shift + maintenance-program gain), (3) response status (stress/p53 axes NOT lit) — and land on the balance verdict: sources up + coping upgraded + response unlit = the state CONTAINS the pressure (active stabilization), which is positive stability evidence. Never invert it into 'this state suffers more damage' — the response dimension is what forbids that reading.

Damage-axis panels (mouse; uppercase symbols for human): stress Atf3/Jun/Fos/Gadd45a/Pmaip1/Rela; p53 targets Cdkn1a/Mdm2/Sesn2/Zmat3 (Pmaip1 is in both panels — drop from one to avoid double counting).

Pitfall — damage RESPONSE is not damage LOAD: the stress axis lights from culture stress, dissociation, and library stress identically to DNA damage; the strongest transcriptome claim is "activated p53/stress response program", never "high lesion load" — gamma-H2AX foci or comet assay is the discriminating experiment.

Pitfall — a state-intrinsic claim needs a within-state correlation test: if "high damage response" is claimed as intrinsic to a state, the axis must correlate POSITIVELY with the state-marker score across same-state samples (requires >=3 samples spanning sources). A negative correlation (e.g. the most-2C-like sample scoring lowest on stress) falsifies the claim and reclassifies the signal as culture/batch-related. A single-dataset signature must also be adjudicated on an independent dataset with more samples of the same state before entering any conclusion — an n=2 state contrast that does not replicate on a larger same-state cohort is a culture-specific event.

Pitfall — GMT name formats differ between repo copies of the same gene-set file (lowercase-with-spaces vs UPPER_UNDERSCORE with a URL second field): parse by splitting each line on tabs and keying on the first field lowercased; never assume a fixed name format — verify parsed set names against the scores TSV row names before computing.

Pitfall — do not frame biology answers around the index: when the user asks a biology evaluation question, answer in the dimensions' own terms (what each cell class does, what counts as normal); repeatedly tying conclusions back to what the score means for an index reads as off-scope.

## 6. Quantify composition effects before invoking them

Sum the TPM share of dominant transcripts per sample; the squeeze on all other genes ≈ Δshare in log2 units. If that is far below the observed shift (usually it is — hundredths of a log2), drop the composition claim instead of citing it.

## 7. Cross-system coherence

For claims that generalize (species, cell-state analogues), test every available analogue. One counterexample falsifies "state X → Y"; if analogues differ (blastomere-like vs 2C-like), state that the states differ rather than averaging them into one story. Species differ in baseline too (human ESC sets show low DDR activity, mouse ESC high) — compare within-species gradients, never absolute scores across species.

## 8. Report in three tiers, then the fix

Established (with the numbers), ruled out (with the test), unresolved (with the discriminating experiment: EdU/Ki67 flow, single-cell, protein level). Figure fix for cross-study panels: absolute-scale heatmap as main figure + relative version as control + annotation bar carrying study/state.
