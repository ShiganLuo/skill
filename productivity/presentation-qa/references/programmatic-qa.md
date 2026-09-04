# Programmatic PPTX Layout QA — Script Templates

## Script 1: Geometry + Layout Audit

Checks every shape's position, size, margins, proximity to other shapes, font sizes, and table dimensions.

```python
#!/usr/bin/env python3
"""Programmatic PPTX layout QA — geometry, margins, proximity, fonts."""
import sys
try:
    from pptx import Presentation
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-pptx", "-q"])
    from pptx import Presentation

PPTX_PATH = "path/to/file.pptx"  # <-- EDIT THIS
prs = Presentation(PPTX_PATH)
slide_w = prs.slide_width / 914400
slide_h = prs.slide_height / 914400
print(f"Slide: {slide_w:.2f}\" x {slide_h:.2f}\"")

for i, slide in enumerate(prs.slides, 1):
    print(f"\n{'='*60}\nSLIDE {i}\n{'='*60}")
    shapes = []
    for j, shape in enumerate(slide.shapes):
        l = (shape.left or 0) / 914400
        t = (shape.top or 0) / 914400
        w = (shape.width or 0) / 914400
        h = (shape.height or 0) / 914400
        r, b = l + w, t + h
        shapes.append({'n': shape.name, 'l': l, 't': t, 'w': w, 'h': h, 'r': r, 'b': b})

        print(f"\n  [{j}] {shape.name}")
        print(f"      ({l:.3f}\", {t:.3f}\") {w:.3f}\"x{h:.3f}\"  R={r:.3f}\" B={b:.3f}\"")

        # Margin checks
        if l < 0.5: print(f"      ⚠️ LEFT margin {l:.3f}\"")
        if t < 0.4: print(f"      ⚠️ TOP margin {t:.3f}\"")
        if r > slide_w - 0.3: print(f"      ⚠️ RIGHT edge {r:.3f}\" (slide={slide_w:.3f}\")")
        if b > slide_h - 0.3: print(f"      ⚠️ BOTTOM edge {b:.3f}\" (slide={slide_h:.3f}\")")

        # Font size checks
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.size:
                        fs = run.font.size / 12700
                        if fs < 10:
                            print(f"      ⚠️ SMALL FONT {fs:.0f}pt: \"{run.text[:60]}\"")

        # Table checks
        if shape.has_table:
            t_tbl = shape.table
            cws = [t_tbl.columns[c].width / 914400 for c in range(len(t_tbl.columns))]
            cw_strs = ['{:.2f}"'.format(w) for w in cws]
            print(f"      TABLE {len(t_tbl.rows)}x{len(t_tbl.columns)} widths={cw_strs}")
            tbl_right = l + sum(cws)
            if tbl_right > slide_w + 0.1:
                print(f"      ⚠️ TABLE extends past slide: {tbl_right:.3f}\"")

    # Pairwise proximity + overlap
    print(f"\n  --- Proximity ---")
    for a in range(len(shapes)):
        for b in range(a + 1, len(shapes)):
            sa, sb = shapes[a], shapes[b]
            ho = min(sa['r'], sb['r']) - max(sa['l'], sb['l'])
            vo = min(sa['b'], sb['b']) - max(sa['t'], sb['t'])
            if ho > 0.1 and vo > 0.1:
                area = ho * vo
                min_area = min(sa['w']*sa['h'], sb['w']*sb['h'])
                if min_area > 0 and area > min_area * 0.3:
                    print(f"  ⚠️ OVERLAP: '{sa['n']}' & '{sb['n']}' ({ho:.3f}\"x{vo:.3f}\")")
            # Horizontal gap (overlapping vertical range)
            if vo > 0:
                if sa['r'] <= sb['l']:
                    gap = sb['l'] - sa['r']
                    if 0 <= gap < 0.3:
                        print(f"  ⚠️ H-GAP: '{sa['n']}' → '{sb['n']}': {gap:.3f}\"")
                elif sb['r'] <= sa['l']:
                    gap = sa['l'] - sb['r']
                    if 0 <= gap < 0.3:
                        print(f"  ⚠️ H-GAP: '{sb['n']}' → '{sa['n']}': {gap:.3f}\"")
            # Vertical gap (overlapping horizontal range)
            if ho > 0:
                if sa['b'] <= sb['t']:
                    gap = sb['t'] - sa['b']
                    if 0 <= gap < 0.2:
                        print(f"  ⚠️ V-GAP: '{sa['n']}' → '{sb['n']}': {gap:.3f}\"")
                elif sb['b'] <= sa['t']:
                    gap = sa['t'] - sb['b']
                    if 0 <= gap < 0.2:
                        print(f"  ⚠️ V-GAP: '{sb['n']}' → '{sa['n']}': {gap:.3f}\"")
```

## Script 2: Text + Table Data Extraction

Extracts all text content and table data for manual review and data consistency checks.

```python
#!/usr/bin/env python3
"""Extract all text and table data from PPTX slides."""
from pptx import Presentation

PPTX_PATH = "path/to/file.pptx"  # <-- EDIT THIS
prs = Presentation(PPTX_PATH)

for i, slide in enumerate(prs.slides, 1):
    print(f"\n{'='*60}\nSLIDE {i}\n{'='*60}")
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                print(f"  {shape.name}: \"{text}\"")
        if shape.has_table:
            t = shape.table
            print(f"  TABLE ({len(t.rows)}x{len(t.columns)}):")
            for ri in range(len(t.rows)):
                row = [t.cell(ri, ci).text.strip() for ci in range(len(t.columns))]
                print(f"    Row {ri}: {row}")
```

## What Each Check Catches

| Check | What it finds |
|-------|---------------|
| Left margin < 0.5" | Elements too close to left edge, risk of clipping |
| Top margin < 0.4" | Title or header too close to top, looks cramped |
| Right/bottom < 0.3" from edge | Risk of clipping in presentation mode or printing |
| H-gap < 0.3" | Side-by-side cards/charts/tables too close |
| V-gap < 0.2" | Stacked elements too close, feels cramped |
| Overlap > 30% | Elements obscuring each other (vs deliberate card+text) |
| Font < 10pt | Text too small to read when projected |
| Table extends past slide | Columns wider than available space |
| Text extraction | Data inconsistencies, unit mismatches, truncation |

## Common Findings in Bioinformatics Reports

- **Gene IDs overflow table columns** — ENSMUSG00000125576 (20 chars) in a 1.60" column
- **Unit mismatches** — FRiP scores as "0.26%" vs threshold ">0.2" (is 0.2 = 20% or 0.2%?)
- **Pipeline step cards at 9pt** — 8 steps squeezed into one row, descriptions unreadable
- **Stat cards 0.25" apart** — below 0.3" threshold but often acceptable for card grids
- **Number formatting inconsistency** — "298" vs "1,544" (some with commas, some without)
