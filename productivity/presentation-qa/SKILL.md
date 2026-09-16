---
name: presentation-qa
description: "Quality assurance for presentation decks — programmatic layout inspection, data consistency checks, and visual review checklists. Use when reviewing any .pptx for layout bugs, margin violations, overlapping elements, font issues, or data mismatches before delivery."
---

# Presentation QA

## When to Use

After creating or editing any presentation deck. Also when the user asks you to "review", "inspect", "check", or "audit" a presentation — even if they provide images (JPG/PNG) of slides rather than the .pptx file.

## Two Complementary Approaches

### 1. Programmatic Layout QA (python-pptx)

Write a Python script that extracts every shape's geometry and checks it against thresholds. This catches hard-to-see measurement issues and works when vision APIs aren't available.

**Read [references/programmatic-qa.md](references/programmatic-qa.md) for the full script template and checklist.**

Key automated checks:
- **Margins**: left < 0.5", top < 0.4", right/bottom within 0.3" of slide edge
- **Proximity**: horizontal gap < 0.3" between side-by-side elements, vertical gap < 0.2" between stacked
- **Overlaps**: flag when overlap area > 30% of smaller shape (but exclude deliberate card-contains-text patterns)
- **Fonts**: anything below 10pt for body text
- **Tables**: column widths vs content length, total table width vs slide width
- **Data consistency**: unit mismatches, threshold contradictions, truncated values, inconsistent number formatting
- **Text overflow**: estimate text height vs textbox height — python-pptx does NOT clip text, it renders beyond the box. For each text frame, estimate total height as `sum(n_lines * font_pt * 1.3 / 72 + space_before_pt / 72)` and compare to `shape.height / 914400`. This catches the #1 layout bug in programmatically generated decks.
- **Negative dimensions**: check `shape.height < 0` or `shape.width < 0` — happens when Layout allocates space smaller than element minimum

Run two scripts: one for geometry/layout, one for text/data extraction. Compare the text data against source files to catch copy errors.

### 2. Visual QA (image inspection)

Convert slides to images and inspect visually. Catches color/contrast, alignment feel, and aesthetic issues that programmatic checks miss.

```bash
# Convert to images (requires LibreOffice + Poppler)
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```

**When vision is available**, use this prompt:

```
Visually inspect these slides. Assume there are issues — find them.

Look for:
- Overlapping elements (text through shapes, lines through words, stacked elements)
- Text overflow or cut off at edges/box boundaries
- Elements too close (< 0.3" gaps) or cards/sections nearly touching
- Insufficient margin from slide edges (< 0.5")
- Low-contrast text or icons
- Uneven gaps or alignment issues
- Numbers or data that look wrong or truncated

For each slide, list issues or areas of concern, even if minor.
```

## QA Checklist (Manual)

Use when reviewing slide images directly:

| Check | Threshold |
|-------|-----------|
| Left/top margin | ≥ 0.5" from edge |
| Right/bottom margin | ≥ 0.3" from edge |
| Element-to-element gap (horizontal) | ≥ 0.3" |
| Element-to-element gap (vertical) | ≥ 0.2" |
| Minimum body text size | 10pt |
| Title text size | 36-44pt |
| Caption/footnote size | ≥ 9pt (10pt preferred) |
| Table column width | Must fit longest expected cell text |

## Common Issues Found in Practice

1. **Unit mismatches in data tables** — e.g., FRiP scores displayed as percentages ("0.26%") but thresholds given as decimals (">0.2"). Both can't be right — verify against source data.
2. **Title top margin too tight** — titles at 0.3" from top are common but below the 0.4" recommended minimum.
3. **Card grids with < 0.1" gaps** — 8-step pipeline cards are often squeezed to fit.
4. **9pt description text** — common in pipeline/process slides where many steps must fit horizontally.
5. **Footer/annotation text overlapping background shapes** — the text is rendered on top of a colored bar, but contrast may be poor.
6. **Gene IDs or long identifiers overflowing table columns** — especially in bioinformatics reports.
7. **Bottom elements too close to slide edge** — charts and tables that extend to within 0.2" of the bottom.
8. **Text overflow inside textboxes** — the #1 bug in programmatically generated decks. The textbox shape is within bounds, but the text renders beyond it. python-pptx doesn't clip text. Common in summary slides with 3+ samples where each sample has 5+ lines. Fix: compress text (fewer lines, smaller fonts), set `tf.auto_size = None`, and verify with height estimation script.

## Verification Loop

1. Run programmatic QA → generate issue list
2. If vision available, run visual QA → add to issue list
3. **List all issues** (if none found, look again more critically)
4. Fix issues
5. **Re-verify affected slides** — one fix often creates another problem
6. Repeat until a full pass reveals no new issues

**Do not declare success until you've completed at least one fix-and-verify cycle.**

## PPTX Dimension Reference

| Format | Width | Height |
|--------|-------|--------|
| Widescreen 16:9 | 13.333" | 7.500" |
| Standard 16:10 | 10.000" | 6.250" |
| Standard 4:3 | 10.000" | 7.500" |

EMU: 1 inch = 914400 EMU. Font: 1 point = 12700 EMU.

## Pitfalls

- **python-pptx auto-installs** — if not available, `pip install python-pptx`
- **Overlaps are often intentional** — text inside card shapes is normal; filter by overlap area
- **Slide dimensions vary** — always read from `prs.slide_width/height`, don't hardcode
- **Color checks are heuristic** — RGB brightness is rough; actual contrast depends on background
- **Chart internals aren't exposed** — python-pptx can check chart bounding boxes but not axis labels or legends
- **Vision API may not be available** — fall back to programmatic QA; it catches 80% of issues
- **Subagent visual QA has fresh eyes** — use it even for 2-3 slides; you'll see what you expect, not what's there
