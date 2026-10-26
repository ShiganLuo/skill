# Programmatic figure audit + legend/schematic generation (matplotlib)

Recipes distilled from multi-round review loops on generated figures (ecDNA
topology legend, structure plots). Use whenever a rendered figure must be
verified without trusting eyeballs, or a small-multiples schematic is built.

## 1. Text-overlap audit via renderer bboxes

Floating annotation labels ("SV 段", "foldback", "chrA"…) placed near a title
or caption overlap at final DPI even when they look fine in the editor.
Audit mechanically:

```python
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
for ax in fig.axes:
    boxes = [(t.get_text(), t.get_window_extent(renderer=renderer))
             for t in ax.texts if t.get_text().strip()]
    # all pairs, overlap AREA > ~4 px^2 (ignore hairline touches)
```

Run it as an import-and-monkey-run harness (sys.argv patched, call module's
`main()`, grab `plt.gcf()`) so the audit stays outside the plot script.

## 2. Geometry audit via palette mask + polar scan

For ring/donut schematics, verify arcs and slits from pixels: build a boolean
mask of ALL ring-palette colors (including alpha-composited blends, e.g.
50% red on white), take the LARGEST 4-connected component (this excludes
text glyphs of the same colors — the #1 source of false positives), center =
bbox midpoint, then scan 1440 samples at band mid-radius counting angular
gaps. Interpretation: 0.2° gaps are anti-aliasing artifacts (ignore); gaps
matching designed slits/markers are expected; anything else is a bug.

## 3. Schematic design rules (small-multiples legend panels)

- **Generate schematics with matplotlib only — never HTML+headless-Chrome
  screenshots.** Hand-written SVG arc math is unverifiable; a full-circle
  `stroke-dasharray` dash-covers the ENTIRE ring (use short arc paths), and
  transform-rotate mistakes draw stray shapes. Wedge patches make the
  geometry exact and auditable (see §2).
- **Semantic gap/slit rules (user-fixed)**: white hairline slit (≈1.5°,
  full band width) = the single excision breakpoint, drawn ONLY when the
  ring is one uniform segment (otherwise the breakpoint position is
  unknowable); multi-segment rings get NO slit — color boundaries already
  encode the junctions. A slit must be a hairline, never half the ring.
- **Degenerate-range trap**: `Wedge((0,0), r, 32, 392)` renders a FULL ring
  with no gap (392 = 360 + 32). For a slit centered at 30° write
  `(30.75, 389.25)` — end angle must be < start + 360 − slit_width.
- **Direction glyphs**: small dark-on-dark triangles are invisible. Show
  orientation reversal as LARGE WHITE arrows embedded in the band, with
  reference arrows in the opposite direction on the flanking normal
  segments — the contrast carries the meaning. No black stroke elements
  on ring schematics.
- **Labels: ring cavity beats periphery** — per-segment labels inside the
  hollow center (at each arc's mid-angle) never collide with the panel
title/caption; peripheral labels at r≈1.4 routinely overlap both.
- **Delete redundant floaters** — an annotation whose meaning already
  appears in the caption collides with it and adds nothing; the caption
  stays.

## 4. CJK fonts in containers

Containers typically ship Latin-only fonts while the host has CJK — copy a
host `.ttc` (e.g. NotoSansCJK-Regular.ttc) to a bind-mounted `/tmp/fonts/`,
`font_manager.fontManager.addfont(path)`, set `rcParams["font.family"]` to
`FontProperties(fname=path).get_name()`. Gate: zero `Glyph ... missing`
warnings on savefig (matplotlib prints them to stderr per glyph).
