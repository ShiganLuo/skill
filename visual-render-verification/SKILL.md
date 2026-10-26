---
name: visual-render-verification
description: Verify visual output renders before delivering files.
version: 1.0.0
author: curator
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [verification, rendering, svg, html, screenshot, vision, qa]
    related_skills: [architecture-diagram, html-design, diagramming, presentation-qa, dogfood]
---

# Visual Render Verification

Hand-written visual artifacts (SVG diagrams, HTML pages, canvas layouts) almost always
have a first-pass defect that is invisible in source: text overflowing its box, labels
overlapped by arrows, CJK tofu, legend collisions. **Never report a visual artifact as
done without looking at its actual rendering.**

## When to Use

- Delivering an HTML page, inline-SVG diagram, or any artifact opened in a browser
- After editing layout/CSS of an existing visual file
- When the user reports "X 不显示 / 看不见 / 排版乱了" — first action is always
  obtaining rendered evidence (screenshot / local render / DOM dump), not text hypotheses

## Recipe (static HTML file, no server)

```bash
google-chrome --headless --disable-gpu --no-sandbox \
  --window-size=1300,2400 --screenshot=/tmp/artifact.png file:///abs/path/to/file.html
```

Then inspect with `vision_analyze` on the PNG. For tall pages, set `--window-size`
height ≥ expected content height, or screenshot in sections.

Why Chrome headless directly: for a self-contained static file it needs no browser
harness, no daemon, no session — it is the shortest reliable path from file to pixels.
(If a browser-automation session is already alive and useful for interaction, driving
that tab works too; for pure "render and look", headless CLI wins.)

## Inspection Checklist

Run through every item — these are the defect classes found in practice:

1. **Text overflow / clipping** — label wider than its container box
2. **Overlap** — text over text, arrow lines crossing through labels
3. **Boundary collisions** — legend or labels touching/inside region boxes
4. **Tofu (□)** — missing glyph coverage, especially CJK
5. **Z-order** — connection lines showing through semi-transparent fills
6. **Truncated content** — last rows cut off at viewport or SVG viewBox edge

Fix → re-screenshot → re-inspect. Iterate until clean; report only what you saw.

## SVG Layout Math (preventing defects at write time)

- **Monospace width estimate**: `chars × 0.6 × font-size` for ASCII in JetBrains Mono;
  **CJK chars ≈ `1 × font-size`** (~1.7× wider than mono ASCII at same px). Mixed
  zh/en lines: sum both parts. Line must be ≤ box width − padding.
- **Overflow fix order**: shrink that line's font-size first (8→7, the "tiny" tier),
  then shorten text (drop qualifiers, use abbreviations), widen the box last —
  widening one box often cascades into the whole layout.
- **Multi-line `<text>`**: each `<tspan>` must repeat `x="..."` or subsequent lines
  drift to the wrong anchor.
- **Fonts**: JetBrains Mono has no CJK glyphs; browsers fall back automatically —
  tofu means the fallback font is missing, check with `fc-list :lang=zh`.
- **Arrows behind boxes**: draw all connection lines right after the background rect,
  then components on top.

## Image Watermark Removal (pixel-healing workflow)

Semi-transparent watermarks (灰字号码、白字 logo) on flat-color backgrounds can be removed
deterministically with numpy — no ML inpainting needed. The hard part is not the fill,
it's **locating the watermark precisely**. Loop:

1. **Locate by pixel statistics, not by eyeballing coordinates** — crop candidate
   regions with PIL, then scan for the watermark's signature: for gray watermarks,
   `(|R-G|<16) & (|G-B|<16) & (110<lum<243)` row by row; for white watermarks on
   tinted backgrounds, `R>thr & G>thr & B>thr`. Print per-row hit counts + x-extents —
   rows with hits give you the exact bounding box. Vision "roughly where is it" answers
   are unreliable; pixel scans are ground truth.
2. **Fill with the surrounding background color** (per-row median of non-watermark
   pixels, or the known flat color), plus tiny Gaussian noise (σ≈1.2) so the patch
   doesn't look dead-flat.
3. **Verify quantitatively AND visually**: re-run the same pixel scan on the output
   (residual count should drop to ~0), then crop the repaired region at 3-4x zoom and
   vision-check it. Iterate — first passes routinely miss part of the watermark (it
   often spans two background regions, e.g. across a white-to-blue bar boundary, or
   extends beyond the box you estimated).
4. **Protect foreground content with hard masks**: when the watermark overlaps real
   content (text, arrows, logos that must stay), add coordinate-based exclusion zones
   and per-pixel classifiers (e.g. "pure white large block = keep" for NEXT-arrow
   text on a dark bar vs. the semi-transparent gray watermark).
5. Sharpen after healing (UnsharpMask + slight contrast), save quality=95.

Pitfalls: `usermod -u`-style "used by process" doesn't apply here, but the analogous
trap is **backgrounds that change across the watermark's extent** — a single fill color
across a white→dark-bar boundary leaves an obvious patch. Split the fill by background
region. And watermarks often have faint anti-aliased edges beyond the pixel-scan
threshold — run a second cleanup pass with relaxed thresholds over the same box.

## Live SPAs and interaction states

For a deployed or dev-served SPA (route content, computed styles, hover/toggle
behavior), static `--screenshot` of a URL is not enough — route chunks and data load
asynchronously, and virtual-time captures race them. Use headless Chrome + CDP over
websocket: navigate, wait real seconds, probe `getBoundingClientRect()` /
`getComputedStyle()`, perform real clicks, then screenshot the SAME state.
Full recipe + validated pitfalls: `references/headless-cdp-verification.md`.

## PDF deliverables

A PDF can be "generated" and still be wrong: a silent second page, the last
line under the bottom margin, content clipped by a fixed-height body. Gate
before delivery:

```python
import pymupdf
d = pymupdf.open(path)
print(d.page_count)                                   # expect 1 for a one-pager
p = d[0]
print(p.rect.height, max(b[3] for b in p.get_text('blocks')))   # page height vs max text y
p.get_pixmap(dpi=110).save("/tmp/page1.png")          # then vision_analyze the PNG
```

- `max text y` near `page height − bottom padding` means the next line of
  copy overflows — **trim copy, never fonts**: cut the summary's weakest
  clauses, then merge/cut the least-relevant bullets, then fold trailing
  one-line list items together. Stay inside the established font scale.
  (Bilingual pairs overflow routinely: the English twin runs longer than the
  Chinese original, so an edit that fit in Chinese can spill in English.)
- A fixed-height body (`height: 297mm; overflow: hidden`) either spills onto
  a second page or clips silently — neither errors, so page count **and** a
  render check are both required.
- Vision-check the PNG for: clipped bottom row, a header/title row that
  wrapped onto two lines, and the final section being present.

## Avatars and platform-cropped images

An avatar can look fine at 512px and fail in actual use. Platform rules
dominate: WeChat/QQ render avatars as CIRCLES (corners cut), GitHub as a
square; contact lists show them at 48–64px. Before delivering:

1. **Compose inside the safe area** — all content within the inscribed
   circle; full-bleed background color (no transparency at the corners).
2. **Build ONE crop+scale preview sheet**: circular alpha mask, each
   candidate at real display sizes (120px AND 48px) on BOTH light and dark
   backgrounds, then a single `vision_analyze` on the sheet — one inspection
   covers every candidate × size × theme.
3. **Legibility degrades unevenly** — 1px line art vanishes when scaled
   down (draw strands ≥5–7px on a 512px canvas); text-heavy designs
   (terminal prompts) blur to blobs at 48px while geometric marks (monogram,
   glyph) stay readable. Prefer shape-based designs for small-display use.
4. First-pass procedural art routinely reads as scattered blobs at small
   size — fix, re-render, re-check the sheet. Report only what the sheet
   showed.

Real case: DNA-helix avatar — 1px strands invisible at 48px (fixed at 7px);
pixel-DNA first pass scattered (fixed with per-row rungs + inter-row block
interpolation); terminal prompt sharp at 120px, illegible at 48px → steer
users away from text designs for WeChat/QQ.

## Pitfalls

- **Headless screenshots can show a WHITE/blank region while the DOM is fully
  rendered — trust DOM probes over the pixels.** CaptureScreenshot sometimes returns
  a frame that hasn't painted freshly-mounted or post-interaction content (seen twice:
  an SPA article body, and an el-drawer opened seconds earlier — vision reported
  "empty" while `getBoundingClientRect()` showed the elements at visible coordinates
  with correct colors). Protocol: after any suspicious blank shot, probe
  `rect / getComputedStyle().opacity / innerText` — if the probe says visible, wait
  ~3–4s and re-shoot before concluding anything. Never report "content missing" from
  a screenshot whose DOM probe says otherwise, and never "fix" code based on one
  blank capture.
- **Selector pitfalls when probing overlay components**: `document.querySelector('.el-drawer')`
  may match the CLOSED drawer instance (empty shell) instead of the open one — Element Plus
  can leave multiple in the DOM. Match by title text or take the one with non-trivial
  `innerHTML`. Same class of trap: the article page's row is `.article_box` while the
  book page's is `.content-row` — copying a selector across pages silently returns null
  (a null that then looks like "the component is gone").
- **Pin the feedback to the exact page first**: when the user reports a visual defect,
  it may target a DIFFERENT page than the one you just changed. Reproduce the exact URL
  they name (a pasted URL is ground truth — open that one, at a common viewport) before
  patching anything. This session: three rounds of feedback ("导航栏遮挡 / 正文贴边 /
  文章那么小") were attributed to the book-reading page while half of them were about
  the ARTICLE page — always confirm which page before editing.
  If the complaint wording is ambiguous about WHICH element or page,
  ask one short clarifying question instead of guessing — repeated wrong guesses cost
  more than one question.
  - **Read the feedback as a literal desired end-state before coding it**: "鼠标没移动到
    边界就隐藏" was a SPEC ("the handle should hide when the mouse isn't at the edge"),
    not a complaint about current behavior — reading it as a grievance led to shipping the
    exact opposite (always-visible) and a wasted round. Restate the sentence as the target
    condition in one line before implementing; if it still feels ambiguous, send that
    one-line reading to the user first.
- Screenshotting before the file is saved, or re-screenshotting a stale path —
  confirm the file mtime / re-write before capture.
- `--window-size` too small → bottom of page silently missing from the PNG; verify the
  captured image actually contains the footer/last section.
- Claiming "verified" from a screenshot you did not actually vision-check — the PNG
  existing is not evidence; the inspection is.
- **Asking vision "which side is it on?"** — vision can be confidently WRONG about
  sidedness (an rtl drawer with its ✕ at the panel's inner-left was reported "on the
  left" twice while `getBoundingClientRect` said right-anchored). For left/right,
  overlap, or gap disputes, get numbers: element rects, computed styles, or
  tint-the-element + PIL pixel bounding boxes. Also note viewport emulation in a CDP
  session resets between tool calls — keep set-metrics → interact → probe inside one
  call (see `references/headless-cdp-verification.md`).
