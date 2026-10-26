# Decoil topology_name taxonomy + structure plot layout

## topology_name: 7-type closed enumeration (DECOIL 2.0.2 `utils.TOPOLOGY`)

`get_topology()` in `decoil/output/metrics.py` returns only 0–6. Judged per-cycle
from 6 boolean features (N_FRAG, SMALL_DEL, DUP, INV, INTERCHR, MULTI_REGION,
FOLDBACK) then assigned by LAST-MATCH override, NOT mutually exclusive:

| # | topology_name | meaning |
|---|---|---|
| 0 | simple_circle | single-fragment excision, no SVs inside (N_FRAG==1 short-circuits) |
| 1 | simple_sv | one of: small deletion (gap 10bp..threshold) OR inversion (strand flip) |
| 2 | mixed_sv | small deletion AND inversion both present |
| 3 | multi_region_intra_chr | same-chromosome non-adjacent regions joined (gap >= threshold) |
| 4 | multi_region_inter_chr | fragments from different chromosomes |
| 5 | simple_duplications | same fragment id appears twice (DUP) |
| 6 | foldbacks | current fragment falls inside previous fragment's span (FOLDBACK) |

Notes:
- Threshold: `del_threshold = min(5000, 0.1*plen + 0.1*clen)`; gap < 10bp with
  same coords within 50bp → DUP instead.
- Labels are "most complex feature wins" — a ring tagged simple_duplications
  may also contain inter-chromosomal parts (DUP check runs after INTERCHR).
- 7 types is DECOIL's taxonomy, not a biologically complete one; Amplicon-
  Architect / breakpoint-graph tools model finer structure.

## Structure plot layout: 3-track linear (decoil-viz style), NOT circular

NOTE (history): the linear layout was once declared the settled form and
circular layouts were banned, but the user later revived and iterated the
CGView-style circular `decoil_structure.py` — both renderers now coexist.
Before editing either, CONFIRM which figure the user is actually looking at;
loose PNGs like `a_circ9.png` on the project root are COPIES — re-run the
rule and verify against the real file under output/, never judge "unchanged"
from a stale copy. The current live target is the circular renderer; its
rules live in the "Circular prototype" section below.

The DECOIL paper (Fig 3/4) and decoil-viz (gTrack) render ecDNA as horizontal
track stacks sharing a reference-genome x axis. Ring layouts fail for dense
gene regions (rotated labels, leader-line spaghetti,
broken collision solvers, giant wedge/arc bugs from unclipped exons and
wrap-normalization) unless those geometry traps are handled (see the label-
layout lessons in the decoil-visualization skill).

Layout (top→bottom), one ecDNA per page:
1. Circularity arcs — red arcs (B1/B2…) join adjacent fragment ends, purple
   `circular join` arc closes last-end → first-start. Without these the
   reader cannot tell the molecule is a circle. Reserve ylim (3.6) so arcs
   are not clipped; hairline dashed guides drop from each arc end to the bar.
2. Coverage area profile (bigwig, pale gold).
3. Reconstruction bar — one gray segment per fragment shaded by mean
   coverage, labeled `chr:start-end`, white gaps at breakpoints, red dashed
   verticals through all tracks.
4. Gene model rows — one row per gene: exon blocks + intron line + strand
   arrow, gene names horizontal (never rotated), broken genes orange +
   asterisk, oncogenes purple bold (+TPM when `--tpm` provided).

Geometry rules (each was a real bug):
- Clip exons/gene bodies to the fragment range before mapping; an exon
  outside the fragment range draws a giant arc/bar spanning half the plot.
- Introns >30 kb: draw two short segments + double-slash break mark, never
  a line crossing the window.
- Genes <0.4% of the total ring length: TSV-only, not drawn.
- Fragment windows placed side-by-side with 20 kb padding (decoil-viz
  `reduce(nodes + 200000)`).
- filtered BED with header only raises `pd.errors.EmptyDataError` — catch
  it and emit a 'No ecDNA detected' placeholder (detection guard).
- `np.clip(arr, ...)` — pandas Series.clip raised 'One of max or min must
  be given' inside the sif; use `np.clip(arr, min, None)` form.

Outputs per sample: `decoil_structure_circ<id>.png` (one page per ecDNA),
`decoil_structure.png` (summary grid), `decoil_structure_genes.tsv`
(gene/status/onco/strand/region/median_coverage/tpm). Params:
`Params.decoil.structure.{formats,max_per_fig,one_file_per_cycle}`.

The decoil-visualization skill (user-owned — see SKILL.md pointer) carries
the same layout-evolution history; if either file changes, keep the two
semantically aligned.

## Circular prototype (decoil_structure.py): legend + truncation graphic language

The CGView-style circular prototype still exists (`--one-file-per-cycle`
per-cycle PNGs) and is held to these rules (user-verified):

- **Legend entries are FUNCTIONAL ELEMENTS as horizontal straight bars, not
  mini gene models.** Two earlier designs were rejected in sequence: a
  straight-line miniature gene model, then an arc mini-model — the user could
  not map either onto the on-circle elements and asked for element swatches
  instead. Current form: coverage (gold bar), exon (solid bar, EXON_W tall),
  intron (DASHED line at INTRON_W drawn with a real matplotlib linestyle —
  not fake block-segments, which rendered as an unreadable smudge), UTR (bar
  with the same white-overlay paleness as on the circle), oncogene (bar with
  dark outline, only when present), junction break (two bare slashes, NO
  background swatch — a decorative backing square was rejected — only when
  present).
- **All gene-element legend swatches share ONE colour (the gene MAGENTA).**
  Colour differences between gene-element entries read as an error ('why do
  the legend colours differ'); shape/height/opacity alone distinguish
  elements. The legend explains element TYPES, not per-gene state — do not
  add a truncated-colour entry unless asked.
- **Legend entries are conditional on what the figure actually contains** —
  no static entry list. Pass flags (has_truncated, has_onco) from the draw
  loop; a ring with no truncated genes gets no break entry.
- **Truncated genes are encoded by gene-block colour PLUS `//` break gaps.**
  Intron connectors are uniformly DASHED (`Wedge` with `facecolor="none"`,
  `edgecolor=col`, `linestyle=(0,(2.5,1.8))`) for every gene — dashed introns
  are the settled style (user request overrode the earlier solid rule). Keep
  them from reading as a fake full dashed circle: thin (INTRON_W ~8% of
  EXON_W) and drawn only between adjacent exons. Orange-vs-magenta
  alone is illegible — orange sits close to the coverage gold, and colour-only
  encoding dies in grayscale printing.
- **`//` break marks are PER-END, gated on a real clipping boundary — never
  "both ends unconditionally".** `to_ang` returns (t2, t1) = (HIGH-coord end,
  LOW-coord end) independent of strand; pair each angle with its genomic
  coordinate (t1↔gene.start, t2↔gene.end) and draw `//` at an end only when
  that coordinate sits on a fragment boundary (±2 bp) OR the gene extends
  past the fragment boundary (the visible end is the clip point itself — a
  gene whose TSS side is cut off has its clipped end AT the fragment edge,
  not at the gene's own coordinate). A truncated gene whose far end wraps
  across the ring start sits on intact reference sequence there: no mark.
  The earlier unconditional both-ends rule painted a `//` at the wrap end of
  genes whose break was 60 kb away — the user read it as a second truncation
  and asked why (verified per-end via a Line2D-spy re-render plus pixel-angle
  audit before concluding).
  NEVER on internal exon/UTR boundaries. The old per-exon proximity test
  (`abs(ex_start - boundary) < 2`) painted `//` onto UTR ends at gene tails
  (UTRs hug the clipping boundary by definition), which the user read as
  meaningless marks.
- **Gene element hierarchy (user-settled): solid full-height exon blocks
  (alpha=1) > UTR as a PALER OVERLAY inside the exon band (white alpha=0.65,
  same radius and width as the exon — reads as the pale ends of the exon
  block, the standard browser convention) > thin dashed intron line.** NO CDS
  layer — this is a DNA-level plot, not a transcript model; a three-layer
  exon/CDS/UTR stack was explicitly rejected, and a separate half-height UTR
  block layer was also rejected (unreadable at plot scale and visually
  doubled the gene length). Elements must be distinguishable by
  shape/height/opacity, not by subtle colour alone. Geometry constants
  (user-tuned over several rounds): R_GENE=0.60, LANE_W=0.11, EXON_W=0.075,
  INTRON_W=0.006, MAGENTA=#8E3A6B (deep — the earlier #A0457A was 'not dark
  enough'; EXON_W=0.10 was 'too long radially'). The 3' strand arrowhead sits
  attached to the outer edge of the last exon block and small — a larger
  arrow floating mid-intron reads as a stray triangle with no referent.
- **No dedicated fragment-junction ticks.** The coverage ring's white gaps and
  the `//` break symbols already encode the join twice; a third coral tick
  marker is redundancy the user deleted. Never re-add junction marks.
- **Re-run for verification**: copy the exact CLI from the newest
  `visualization/decoil_structure_<sample>_*.sh` (it records bed/summary/
  gtf/bw paths), run via
  `apptainer exec --bind /data/pub:/data/pub <decoil.sif> python .../decoil_structure.py ...`,
  then vision-check the PNG (legend overlap, break marks visible, arrow
  visible at 300 dpi).
- **Two Omics copies have diverged for decoil**: only the main copy
  (20260207_Exome) has the visualization bin scripts; the zls copy's
  decoil/bin holds only pbsv2decoil.py. Do not blind-sync decoil
  visualization scripts to zls.

## decoil_structure.py code structure (post-refactor)

All helpers are module-level. Extracted in three passes: (1) the nested closures — arc-overlap test (`_arc_contains`), break-gap marker (`_mark_break`), legend block (`_legend_block`), per-cycle draw (`_draw_and_collect`), grid page (`_grid_page`, now RETURNS its gene rows instead of closing over a list); (2) the gene-structure ring coordination layer — `_draw_gene_ring(ax, genes, circ_id, spans, circ_len, onco_genes, tpm, bw_path, exons_df, utr_df) -> (gene_rows, has_truncated, has_onco)` (renamed from `_draw_gene_structures` — plural name described a ring, not N genes), called by `draw_cycle_circular` between the coverage ring and hub/legend; (3) the per-gene renderer `_draw_gene_structure(ax, gene, transcripts, t2, t1, lane, contained, spans, circ_len, onco) -> (r_lane, lab_ang)` — ONE gene in, draws only that gene, taking a `transcripts: Dict[str, Dict[str, List[Tuple[int,int]]]]` dict with the SAME shape `plot_gene_model_all_transcripts` takes (keyed by gene name here; one transcript per gene; keys are `{'exons', 'UTRs'}` — no CDS).

GTF loading is single-pass: `load_gtf_all_features(path) -> {'genes','exons','utrs'}` (CDS deliberately NOT loaded — the plots show exon/intron/UTR structure, not coding detail; 4 separate passes over a full GENCODE GTF cost ~6 s, one pass ~3 s). The `cds_df` parameter was removed from the entire chain (`draw_cycle_circular` → `_draw_gene_ring` → `_grid_page`/`_draw_and_collect` → `plot_structures` → `main`); the standalone `load_gtf_features(path, feature_type)` remains as a generic utility. Dead helpers removed along the way: `_draw_break_gaps` (superseded by gene-span-level `_mark_break(ax, r_lane, t_lo, t_hi, col, exon_w)`), `_legend_block`, `_draw_legend_gene`, `_draw_break_gap_at_arc` — when a rendering approach is replaced, delete its superseded helpers the same pass and `grep` for orphan references. Rules for future edits:

- **Drawing functions are single-subject: one gene (or one element) per call.** When asked to split a draw loop, shape the extracted function like the project's existing per-subject convention (`plot_gene_model_all_transcripts`: ax + one feature + its data), NOT as a loop-with-params. Cross-gene state (greedy lane assignment, label collision avoidance against already-placed `lab_ang`s) stays in the coordination layer; the single-gene function RETURNS suggestions (`lab_ang`) and the coordinator places labels and mutates shared records. Coordination-layer params (tpm, bw_path) may stay in the single-gene signature for symmetry even when currently unused — note them as such in the docstring.

- When extracting a closure, closure-captured variables become explicit
  parameters and EVERY call site must be updated in the same pass; fix all
  LSP 'missing argument' diagnostics before moving on.
- Extracting a closure to module scope EXPOSES Optional-typing bugs the
  nested def hid from the checker. Typical: `tpm[gname]` with
  `tpm: Optional[dict]`. Narrow once with a local alias
  (`tpm_map = tpm or {}`) instead of scattering `if tpm` guards.
- After structural patches, `grep -n '^def <name>'` to confirm each function
  is defined ONCE — `py_compile` passes with duplicate defs (the later one
  silently shadows the earlier), so compile success is not refactor success.
  A patch that inserts a new def before an existing signature can leave the
  old def's orphaned body behind; grep or whole-file pyright catches it,
  py_compile does not.
- `gffutils` is NOT in decoil.sif and `create_db()` is dead code (GTF goes
  through `load_gtf_features`); keep `import gffutils` inside try/except.
  Never add a hard top-level import of a package absent from the sif — a
  failed import kills the whole script at load time.
- **Verify a plot change by dumping the drawing calls, not by squinting at
  pixels.** Wrap `Axes.plot`/`Axes.add_patch` with a spy that records color /
  data coords, render to /tmp, then classify: this distinguishes a `//` break
  mark (two 45° Line2D segments at the gene lane) from a 71 bp exon that
  renders as a visually identical 1×EXON_W radial bar — pixel color alone
  cannot (both are the truncated gene's colour). Run the spy on a single-cycle
  BED (grep the circ_id rows into a temp BED) so other rings' elements don't
  pollute the trace; the renderer draws ALL cycles in one process.
- **Script deps vary by env, not by sif**: `decoil_structure.py` needs
  `pyBigWig` — present in the `DNA` conda env (runs bare, no apptainer
  needed); the RNA env lacks it. Check `python -c "import pyBigWig"` per env
  instead of assuming the sif is the only runtime.
- Smoke-test refactors with a synthetic fixture (2-fragment BED + one-row
  summary.txt, optionally a small GTF covering intact / truncated /
  oncogene+TPM cases) run inside decoil.sif, exercising BOTH modes: default
  grid and `--one-file-per-cycle` (check rc=0, all output files exist, and
  for GTF runs that `_genes.tsv` rows match the fixture). Vision-check the
  PNG for the gene blocks / labels / // breaks.
- When benchmarking alternatives before refactoring (e.g. gffutils vs plain
  parsing), run the benchmark ONCE against the production-scale input and
  decide from the numbers; do not chase cross-checker inference questions
  with more experiments.
- TSV fixtures written through the write tool get `\t` stored as LITERAL
  backslash-t text, surfacing later as a baffling `KeyError: 'circ_id'` at
  load time. Fix the fixture with
  `sed -i 's/\\t/\t/g; s/\\n/\n/g'` and confirm via `cat -A`
  BEFORE debugging the script — the script was fine.
- IDE type-inference questions (e.g. hover claims `list[bool]` for
  `list(dict.fromkeys(bed["circ_id"].astype(str)))`): the runtime type is
  `list[str]` — trust it and answer with the mechanism plus an explicit
  annotation (`circ_ids: List[str] = ...`). Hover types come from the
  checker's pandas stubs (Pylance bundles its own; bare `npx pyright` on
  this host resolves no pandas at all), so they disagree by design. Do NOT
  burn many calls reproducing inference across checker versions — the user
  reads that as stalling on a question with a one-paragraph answer.

## Topology legend (7-type schematic)

`modules/decoil/bin/topology_legend.py` renders the 7 types as closed rings
(matplotlib Wedge patches — never HTML/SVG). Graphic language: color =
fragment/source chromosome; hairline white slit ≈1.5° full band width = the
single excision breakpoint (simple_circle ONLY; multi-segment rings encode
junctions by color boundaries, no slit); orange dashed arc = SV segment;
inversion = large WHITE arrows on the green arc running counter to the
reference arrows on the blue arcs (small dark-on-dark triangles are
invisible — direction CONTRAST carries the meaning); dark/light red A/A′ =
duplicated copies; nested orange arcs = foldback. No black elements.

Wedge pitfall: `Wedge(..., 32, 392)` renders a FULL ring (392 = 360+32);
a slit needs end angle < start + 360 − slit_width, e.g. (30.75, 389.25).

QA gates after every legend edit (both mechanical):
1. Text overlap: draw canvas, all-pairs `Text.get_window_extent(renderer)`
   with overlap area > 4 px² counting — floating annotations near panel
   titles/captions collide most. Ring labels go in the cavity (r≈0.55),
   never the periphery.
2. Geometry: palette mask + largest connected component (excludes same-
   color text glyphs — the top false-positive source) + polar scan at band
   mid-radius; 0.2° gaps are anti-aliasing noise.
