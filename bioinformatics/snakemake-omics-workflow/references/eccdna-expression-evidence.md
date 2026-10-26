# eccDNA Expression Evidence from RNA-seq (ecDNA 转录验证)

Procedure for answering 'does this ecDNA get transcribed?' using the project's
existing outputs (PacVar/decoil ecDNA reconstruction + RNAseq STAR/Arriba
pipeline). Class-level: applies to any decoil-reconstructed ecDNA set with
matched RNA-seq.

## Core principle

Coverage enrichment over the breakpoint is NOT evidence of expression (high
copy number, DNA contamination, and linear readthrough all produce it). The
provable signal is RNA reads SPANNING the circular junction (the ring-closure
join), i.e. junction-spanning transcripts.

## Evidence ladder (run in order; stop when proof suffices)

1. **Reuse Arriba results (zero cost, do first)** — `match_arriba_decoil.py`:
   Arriba fusion breakpoints vs decoil fragment boundaries (±1 kb window; the
   RNA splice breakpoint need not coincide exactly with the DNA circle edge).
   Cheap screening only: a fusion-breakpoint read is indistinguishable in
   sequence space from an ordinary LINEAR rearrangement (translocation/deletion
   makes the two ends adjacent on the same chromosome) — pass-fusion hits are
   a lead, never the verdict; ladder 2 ring-seam evidence is required to
   confirm. Expect zero passed hits against a small ecDNA set — normal, and
   exactly why ladder 2 exists.
2. **Custom-ecDNA reference alignment (systematic, decisive)** —
   `align_ecdna_junction.py`: STAR index from
   `decoil/reconstruct.ecDNA.filtered.fasta` (linearized circles), then count
   reads spanning the ring-closure seam. This is the correct implementation of
   'breakpoint enrichment': count junction-spanning reads, never coverage
   height.
3. **RNA/DNA coverage ratio (supporting figure)** — `rna_dna_ratio.py`: RNA
   reads-per-kb per fragment ÷ the fragment's flanking linear background
   (decoil coverage column is the DNA side). Normalizes away copy-number-driven
   coverage; supporting evidence only.
4. **Long-read RNA (Iso-Seq / direct RNA)** if full-length proof is needed:
   single molecule spanning the junction, cleanly excludes circRNA and
   readthrough. For few targets, capture RNA-seq (probes over junction
   ± flanks) is the cheap sensitive option.

## Implementation

Working scripts live in `workflow/Omics/src/eccDNA/` (README there has verified
commands): `match_arriba_decoil.py` (ladder 1), `align_ecdna_junction.py`
(ladder 2), `rna_dna_ratio.py` (ladder 3). Run with the `RNA` conda env python
(the only env with pysam; repo convention forbids auto-installing deps).

### Ladder 2 via subset-realignment (scheme 1, fast path — verified end-to-end)

Whole-transcriptome STAR vs a ~1.7 Mb ecDNA ref takes ~5-13 h/sample (~74% of
reads map nowhere; chimSegmentMin 10 cannot be dropped). Equivalent fast path:
`samtools view -L <fragment regions.bed>` the whole-genome RNA BAM, `samtools fastq`
back to fastq, then STAR the subset against the ecDNA index (same chimera params
+ `--seedSearchStartLmax 50` + `--winAnchorMultimapNmax >= outFilterMultimapNmax`).
Subset is ~5-10^5 reads, aligns in seconds. STAR 2.7.11b small-genome speedup
flag is `--seedSearchStartLmax 50` (NO seedSearchStartL1Nbases — unrecognized-
parameter fatal error).

**Feed SE, not PE — and account for EVERY read**: junction counting needs no
pairing, and dropping unpaired reads drops exactly the reads of interest (a
junction read's mate often falls outside the ecDNA regions or fails to align).
`samtools fastq -1 r1 -2 r2 -0 r0 -s rs` (FOUR files; `-0` alone writes only
READ_OTHER and silently discards READ1/READ2 — the all-zero round came from
this), then pass all four comma-joined to `STAR --readFilesIn`. Never feed a
proper-pair-only subset: that scores all-zero and looks like a clean negative.
Grep 'input reads' from Log.final.out before trusting any junction count.

**align_ecdna_junction.py misses soft-clip seam reads**: STAR local mode often
soft-clips the across-seam part instead of wrapping; the script's pos=0 junction
test requires aligned blocks reaching BOTH record start and record end, so these
reads score 0. Independent check: scan every BAM read's soft-clip and test exact
match against the opposite side of the record (both strands, clip>=10, MAPQ>=10,
skip sec/supp). Random 4^-N match = no false positives at N>=15. Accept <=1
mismatch only when the same variant recurs across independent reads (a shared
mismatch = real RNA variant cluster, not noise).

**Two junction classes, different proof strength** — count and report separately:
fragment junctions (between fragments ON the ring) only prove continuity of the
reconstructed structure — linear rearrangements produce identical read patterns,
same strength as Arriba fusion hits; ring-seam reads (linearized 1|L) exist
ONLY on a circle and are the decisive evidence. Judgment threshold (>=3) applies
to ring-seam-level evidence; fragment-junction-only = 'continuity supported,
circular transcription unproven'. internal reads = 0 means pipeline failure or
wrong circle sequence, NOT a negative.

Working driver script pattern: `output/iteration/eccDNA_index/align_subset_se.sh`
(extract -> 4-way fastq -> STAR -> junction stats). Full method write-up with
reasoning lives in `workflow/Omics/src/eccDNA/METHOD.md` (证据 2); figure script
`plot_junction_evidence.py` (same dir) renders the evidence panel pair.
⚠️ its per-sample homolog-ring map is hard-coded — verify each entry against
`filtered.bed` (chr4 locus, start < 145.5 Mb) before rendering: a wrong entry
silently plots a different sample's unrelated circle (DMSO_P20 was mapped to
circ82/chr17:306Mb instead of circ22/chr4) and the figure contradicts the
text. When the map is hard-coded, check the figure AND the report agree.
Verified final (4 samples x 2 reps): (a) DMSO_P06 circ33 rep2 EXPRESSION-positive
(4 independent seam reads 0-1 mm + fragment-junction nonsplice=8, rep1
concordant at 2+0 seam), (b) PlaB_P06 circ35 / PlaB_P20 circ31 weak
(fragment-junction 4-6/rep but seam 0-1), (c) DMSO_P20 all-negative.
circ33/35/31 = same chr4:145.1-35Mb ring (Platr16/Gm13230/Zfp268, non-coding).
Results: `output/iteration/eccDNA_index/junction_results/RESULTS.md`; figure:
`junction_evidence.png` via `src/eccDNA/plot_junction_evidence.py` (grouped
per-sample seam/fj/backsplice bars + seam-only headline panel; bar groups must
center exactly at x=gi via symmetric half-offsets — naive `base+ci*w` offsets
make tick labels misalign; rep bars need an explicit gap or they touch).
Junction-opportunity counts differ per ring (1-frag=1 seam-only, 2-frag=2,
3-frag=3): never compare raw fj counts across rings; the >=3 threshold lives on
the seam layer which is naturally 1 site per ring.

### Ladder 2 junction classification (align_ecdna_junction.py)

STAR aligns reads to the linearized ecDNA record; a seam-spanning read appears
as either a split alignment (CIGAR N) or a supplementary pair. The script
counts per junction: continuous crossing (one block extends min_anchor bases
to both sides) = nonsplice evidence; split blocks abutting the junction (left
block ends at the junction, or right block starts at it, each with >=
min_anchor anchored) = backsplice. It skips secondary AND supplementary
alignments, so a seam-crossing read reported by STAR as two supplementary
records is NOT counted — cross-check `--chimSegmentMin` chimeric output for
circle-junction events before declaring absence. Split reads where the N gap
lands adjacent to (not exactly on) the junction are deliberately not counted:
an N that starts hundreds of bases from the junction is an ordinary intron,
not the seam.

STAR index build for a tiny ecDNA reference (run_module standalone mode):
`python run_module.py --module star --sdm --rules star_index -o <run_dir>
--genome.references.GRCm39.fasta <reconstruct.ecDNA.filtered.fasta>` — see
`references/run-module-invocation.md` for the wrapper machinery. Key
config-key trap: the input function reads `genome.references.<g>.fasta`, NOT
`genome.fasta` — a `--genome.fasta` override is silently ignored. For a
tens-of-kb reference override `--Params.star.index.sjdbOverhang <readlen-1>`
(the smk hardcodes 100). `genomeSAindexNbases` needs no manual value: the smk
auto-computes min(14, log2(genomeSize)/2 − 1) from the fasta when
`Params.star.index.genomeSAindexNbases` is unset (explicit config still wins).

### Ladder 1 noise stratification (mandatory)

Arriba's `*_discarded_fusions.tsv` contains ~10⁵ min_support-rejected chimeras
that match essentially ANY coordinate pair. Matched-by-discarded-only is
labeled `discarded_only_noise_prone` and must not be cited as expression
evidence; only `*_passed_fusions.tsv` hits count at ladder 1. Expect zero
passed hits against a small ecDNA set — that is a normal result, not a bug,
and is exactly why ladder 2 exists.

### Ladder 3 ratio

RNA side uses reads-per-kb; the background is the fragment's own linear flank
BOTH sides ±50 kb with EVERY ecDNA interval of the sample (all circles,
including its own) subtracted from the windows — library size cancels in the
ratio. Masking is mandatory, not optional: for short fragments the naive
left-flank window is 44–49/50 kb other fragments of the SAME circle, so the
'background' is the ring's most-transcribed segment and active fragments get
called silent (homolog-ring M/S scored 0.2–0.3x unmasked, 1.4–3.0x masked).
A 'left-only avoids the next fragment' shortcut is wrong — it maximizes the
contamination instead. Dedupe reads by query_name per window; when a window
has zero reads (evidence=flank_empty) the ratio is inf and is library-depth
noise, never activation (a ring scoring 120–400x unmasked scored 3–4x masked).
Report per-fragment, never ring-mean. Figure: `plot_rna_dna_ratio.py` ->
`rna_dna_ratio/rna_dna_ratio_evidence.png`. Panel A: homolog-ring fragments,
bars per fragment, values labeled with both reps (e.g. '7.7x / 6.8x').
Panel B is a FRAGMENT-LEVEL HEATMAP (replaced the earlier ring-mean dot plot
after review): rows = (sample, circle, fragment) sorted by locus, columns =
samples, cell = log2(mean-of-reps ratio) on a red/blue diverging scale centered
at 1x with per-cell ratio annotations, row label = fragment coords + circ id in
the family's color, family color strips + divider lines + f1..f9 tags on the
right, and a below-panel legend mapping family colors to loci and marker genes.
flank_empty fragments render as gray 'n.e.' cells (or a hollow marker at a
fixed left anchor when using a dot plot); never drop them silently — a NaN
mean from pandas silently keeps the surviving replicate, which is fine, but a
both-rep-empty fragment must stay visible as n.e.

Fragment is the reliable analysis unit for this evidence (the ratio is computed
per fragment against its own masked flank, and one circle can mix active and
silent segments — homolog-ring L 6-7x vs M/S 1.4-3x — so ring-mean averages
that heterogeneity away). Keep the ring-level summary in the companion RESULTS.md
table, but the figure stays fragment-level.

Verified batch run (4 samples x 2 reps, masked flanks): fragment-level ratios
answer 'is this RING segment transcribed above the linear background', NOT
'is the ring transcribed as a circle' — homolog-ring fragments sit at 6–7x
(large) and 1.4–3x (mid/small) with both reps concordant; DMSO_P20's homolog
ring shows the same ~6x on its large fragment yet zero seam reads: linear-
active sequence copied into the ring keeps transcribing, but no readthrough
across the seam. Low-background loci (chr3:106Mb ring) shift several-fold with
the masking choice — rank rings by magnitude, do not bin at a 2x threshold.

## Measured outcome (ladder 3, PlaB_P20 vs E14-2)

- Ladder 1: zero passed hits; all 1005 matches discarded-only.
- Ladder 3: masked-flank ratios — circ47/43 (chr5:149Mb) 144–244x,
  circ82/105/100 (chr17:306Mb) 11–22x, circ9 3–4x, homolog-ring fragments
  1.4–7x; circ81/55/58/99/104 at or below background. Ratio alone is
  supporting, not conclusive. Superseded unmasked numbers (M/S <=0.3x
  'silent', circ9 120–800x) were flank-contamination artifacts.
- Ladder 2 outcome (see subset-realignment section above): circ33-class ring
  positive in DMSO_P06, weak in PlaB reps, DMSO_P20 negative — note the
  DMSO-group internal inconsistency (P06 positive, P20 negative); do not
  collapse treatment-vs-control into a single direction claim.

## User-facing explanation pattern (for this evidence class)

When asked 'why does this prove expression', lead with the structural
exclusivity argument (a read spanning the ring seam cannot come from any
linear transcript), then walk the confounds (coverage/copy number, circRNA
back-splice motif, linear readthrough, mapping artifacts) and finish with the
boundary: it proves the ring is a transcription TEMPLATE, not transcript
structure or absolute abundance. When asked why fusion-gene breakpoint reads
are weaker: breakpoint adjacency exists on the LINEAR genome after
rearrangement; ring-seam adjacency exists only on the circle.

## circRNA confound (mandatory disambiguation in method 2)

Circularization is often intronic, so linear-genome back-splicing produces
junction reads with IDENTICAL coordinates. Disambiguate by splice motif at
the junction:

- circRNA = spliceosome back-splice → canonical GT-AG motif at the junction;
- ecDNA template transcription = UNSPLICED contiguous reference sequence
  across the seam.

Count the two classes separately: only unspliced seam-spanning reads support
ecDNA expression. Also report fold-enrichment over an ecDNA-negative sample's
background chimeric rate rather than raw counts.

## Method attribution (checked against primary sources — do not re-cite blindly)

Zhu 2023 (Nat Genet 55, 880-890, scEC&T-seq) does NOT describe RNA-vs-ecDNA-
reference junction counting; its RNA side is Smart-seq2/RSEM quantification +
Arriba fusion calling (STAR chimeric, v2.1.0 `-F 150 -U 700`; confident set:
breakpoint coverage >=50x, >=30% split/discordant, amplicon +/-10 Mb only —
its thresholds assume merged multi-cell coverage, relax for single samples).
Its 'junction-spanning reads' phrase refers to scCircle-seq DNA reads at SV
breakpoints, not RNA. Ladder 2 is this project's own design; its logic derives
from DNA-layer circle-supporting chimeric reads (scCircle-seq, Circle-Map).
Ladder 3's original in Zhu 2023 is CPM coverage correlation + copy-number vs
expression Pearson; the ratio-vs-flank design is a project improvement.
Verify every method-attribution citation against the paper full text before
it enters METHOD.md — page numbers included (55, 880-890, not 1366-1377).

## Data locations (20260207_Exome layout)

- ecDNA: `output/PacVar/eccdna/<sample>/decoil/reconstruct.ecDNA.filtered.{bed,fasta}`,
  `reconstruct.links.txt`, `fragments_clean_*.bed`;
  `reconstruct.json` = per-circle fragment breakpoint records (label='ecDNA';
  superset of the filtered bed — use json for cross-sample breakpoint
  comparisons, bed for the filtered analysis set)
- gene annotation per ring: `.../visualization/decoil_structure_genes.tsv`
  (circ_id/gene/status/onco/region/median_coverage/tpm)
- fusions: `output/RNAseq/fusion/<genome>/<sample>/<sample>_{passed,discarded}_fusions.tsv`
  (#gene1, gene2, breakpoint1, breakpoint2, site columns)
- scripts: `workflow/Omics/src/eccDNA/{match_arriba_decoil,align_ecdna_junction,rna_dna_ratio,plot_junction_evidence,breakpoint_families,plot_breakpoint_families}.py`
  + METHOD.md (full方案, references cited)
- breakpoint-sharing families: `breakpoint_families.py` clusters circles from
  `reconstruct.json` (label=ecDNA; json has MORE circles than filtered.bed —
  e.g. DMSO_P20 circ96 exists only in json) into families: shared breakpoint =
  fragment edge within ±200 bp on the same chromosome, family = ≥2 shared
  breakpoints (union-find). TSV output has per-family member list + per-
  breakpoint detail (coordinate, carrier count, spread). Verified 4-sample
  result: 28 circles → 9 families; families 2–8 are single-fragment circles
  with 0–1 bp breakpoint reproduction = the SAME ring inherited across
  samples; family 1 (chr4 homolog ring) is the only family with internal
  structure divergence (5 circles, 8 breakpoints, partial sharing: outer ends
  4/5 circles, central ones 2–3) = one ancestor ring rearranged during
  passage. 'Homologous ring' therefore means the shared-breakpoint FAMILY,
  not identical fragments; fragment-level comparison is valid only between
  structurally identical rings (35 vs 31). Figure: `plot_breakpoint_families.py`
  (one row per family, circles sample-colored, dashed lines span only the
  carrier tracks, count = carriers) -> `eccDNA_index/breakpoint_families.png`.
- junction results + figure: `output/iteration/eccDNA_index/junction_results/`
  (`<rep>.se.tsv` per-replicate counts, `RESULTS.md` report, `junction_evidence.png/pdf`);
  indices under `output/iteration/eccDNA_index/<sample>/index/`, SE alignments under
  `.../align_se/<rep>/`; subset driver `output/iteration/eccDNA_index/align_subset_se.sh`
- family gene annotation: `annotate_family_genes.py` (GRCm39 GENCODE vM38) ->
  `breakpoint_family_genes.tsv` (family/locus/gene/full-partial) +
  `breakpoint_family_genes_structures.tsv` (exon/UTR blocks, transcripts merged)
- evidence-3 report: `output/iteration/eccDNA_index/rna_dna_ratio/RESULTS.md`

## Documentation style for this evidence class (user requirement)

METHOD.md / RESULTS.md describe the FINAL method only — no error-process
narratives ('initial version did X wrong', 'corrected to Y', 'superseded
numbers', 'withdrawn'). Standing requirements that must stay are written as
operational MUSTs ('all four fastq files must be fed to STAR', 'circle
intervals must be masked'), never as 'we initially forgot'. Results reports
state coverage completeness explicitly (regions.bed == filtered.bed fragment
counts per sample; internal reads nonzero = true negative) and list explicit
negatives — silent collective zeros are not enough when a reviewer asks
'did you analyze every ring'.

## Biological interpretation pattern (family-level conclusions)

Pair each family's gene content with its evidence-2/3 status:
- segment transcription (evidence 3) is family-CONSISTENT — every member of a
  family shows the same active/silent state (inherited from the locus), so
  'same family => same segment-transcription state' held in all 9 families;
- circular transcription (evidence 2 seam) is RARE and family-internal
  heterogeneous: 4/26 rings total, all in the structurally-divergent chr4
  family (circ33 positive; PlaB weak; circ22 negative despite 6x segment
  transcription) — structure divergence and detectable circular
  transcription co-occurred;
- high RNA ratio != circular transcription (family 6 Hmgb1 ring 141-244x,
  family 2 Glo1/Dnah8 6.5-21.9x, both zero junction reads): the RNA is linear
  background, per the core principle.
Phrase conclusions per ring, never 'family 4 expressed': the family is a
breakpoint-sharing classification, not an expression unit (DMSO_P06 positive,
PlaB weak, DMSO_P20 negative inside family 4).
