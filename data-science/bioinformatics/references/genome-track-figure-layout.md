# Multi-Track Genome Figure Layout (family rows + gene models)

Patterns for figures that stack multiple genomic feature rows (per-family or
per-sample tracks, breakpoint lines, gene models, labels) — e.g. ecDNA
breakpoint-family figures built from decoil BED + GENCODE GTF.

## Architecture: plan/draw separation (mandatory)

Split the script into pure layout planners and per-layer draw functions; the
orchestrator only calls them:

```
plan_lanes(genes)                -> lane assignment (largest gene innermost)
plan_labels(genes, span, pad)    -> [(row, x_left, text, color)], n_rows
plan_breakpoints(members, …)     -> shared / private breakpoint positions
plan_family(...)                 -> full layout dict incl. ylim, band heights
draw_tracks / draw_breakpoints /
draw_gene_models / draw_labels   -> one visual layer each
plot()                           -> plan all rows, allocate axes, call drawers
```

Why: iteration requests almost always target ONE layer ("labels too crowded",
"arrows too loud"). With separation you edit one draw function or one constant;
with interleaved code every tweak risks regressing other layers.

## Compute the layout BEFORE touching the axes

Label-row packing determines the required ylim. The planning pass must run the
EXACT same packing algorithm the drawing pass will use, and its outputs (lane
count, label row count, positions) must be stored in the layout dict that the
drawer consumes. Never re-estimate row counts in the drawing loop with a
different formula — plan/draw disagreement shows up as unequal bottom margins
and label/axis collisions.

## px-per-unit pitfall (the big one)

With equal-height subplots but different ylim ranges per row, a CONSTANT
data-unit gap renders at DIFFERENT pixel heights — text height especially:
`text_height_data ≈ fontsize_pt * 1.45 * data_per_pt`. If uniform visual gaps
matter, allocate axes height proportional to each row's data total
(`gridspec_kw={"height_ratios": [...]}` with one common scale) so px per data
unit is identical everywhere. Otherwise accept the variance and size the bottom
pad from the row's own data_per_pt.

## Text and clipping

- `ax.text` is NOT clipped to the axes by default. Any label whose x is clamped
  near a panel edge needs `clip_on=True`, AND the clamp must use an inflated
  width (`x1_lim - txt_w * 1.15`) so the rendered text stays fully inside.
- Label collision packing: estimate width as `len(txt) * fontsize * 0.66 *
  data_per_pt`; underestimating causes overlapping labels (the estimate must be
  generous). Process labels in genomic order; a label joins the first row whose
  last span ends before it starts, else a new row.
- Center labels under the VISIBLE (clipped-to-locus) gene center, not the raw
  gene start.

## Conventions for gene tracks (user-approved)

- Lane assignment: largest gene innermost (lane 0 = closest to the feature
  tracks); overlapping genes cascade to lower lanes.
- Gene model per decoil_structure style: exon blocks (one hue per gene), pale
  half-height UTR overlays, thin intron connectors, small 3' chevron on the
  body midline (subtle — a large chevron upstages the structure).
- ALL gene names get labels (unannotated Gm/Rik genes included); labels sit in
  one zone below the models, in genomic left-to-right order, centered under
  their gene; partial genes get a `*` suffix.
- Breakpoints: shared (≥2 carriers) = dark dashed line spanning only carrier
  tracks with the carrier count on top (count y capped so it cannot reach the
  header); private (single circle) = light dashed line on the owning track.
  Don't draw private lines at positions already covered by a shared line.

## Iteration discipline when the user is reviewing

- Freeze the last-approved version before changing layout logic (copy the file
  or commit); chained refactors on the live artifact compound failures — one
  bad idea stacked on another produced an unusable figure that had to be fully
  reverted.
- Prototype a risky layout change on ONE family row and get confirmation
  before applying it to the whole figure.
- Separate layout constants (HEAD, LANE_PITCH, ROW_H, pads) as named module
  constants; tune spacing by editing constants, not by hunting through draw
  code.
- Beware `bbox_inches="tight"`: it finalizes axes size at save time, so any
  renderer-based measurement before save is unreliable — use deterministic
  arithmetic (figure width, panel fraction, font pt) instead.

## Background-window pitfall (coverage ratio analyses)

When computing fragment/background coverage ratios (RNA over region vs
flank), the background window must EXCLUDE the feature intervals themselves
(all circles/regions from the BED). For short fragments the naive flank window
is mostly other feature intervals, inflating the background with feature
transcription and calling active fragments silent. After fixing, re-derive all
recorded conclusions from the new numbers and update the project METHOD doc —
do not leave stale tables next to corrected ones.
