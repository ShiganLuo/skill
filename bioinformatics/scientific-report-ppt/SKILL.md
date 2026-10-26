---
name: scientific-report-ppt
description: Scientific report PPTs with python-pptx and matplotlib.
tags:
  - pptx
  - report
  - matplotlib
  - scientific
  - presentation
  - bioinformatics
triggers:
  - report PPT
  - analysis report
  - QC report
  - scientific presentation
  - data report slides
---

# Scientific Report PPT Generation

## When to Use

When the user asks for a **scientific report PPT** with figures, charts, and data from bioinformatics analyses. This is the established pattern in the Omics workflow project.

**Do NOT use the JSON spec approach** (pptx_create.py from the powerpoint skill) for scientific reports — it produces text-heavy, visually poor results. The user explicitly rejected this: "太没有内容,太卡通了" (too little content, too cartoonish), "毫无内容,还很丑" (no content, ugly).

## Critical: Look at Existing Report Modules First

Before creating any report PPT, **always check existing report modules** in the project:

```bash
find workflow/Omics/modules -type d -name "*report*"
```

Read their `bin/generate_report.py` to understand the established pattern:
- `workflow/Omics/modules/RNAseq_report/bin/generate_report.py`
- `workflow/Omics/modules/PeakCalling_report/bin/generate_report.py`
- `workflow/Omics/modules/ncRNAseq_report/bin/generate_report.py`

These modules use **direct python-pptx with matplotlib** — follow their exact pattern.

## Pattern Overview

1. **Generate figures with matplotlib** — create professional scientific plots
2. **Save to temp files** via TempImageStore
3. **Build slides** using helper functions (_header, _bullets, _table, _add_picture)
4. **Save PPT** — prs.save(output_path)
5. **Cleanup** temp images

## Key Design Principles

- **Every slide has a header bar** — dark navy (#0D1B2A), white text, 28pt bold
- **Every slide has figures or tables** — NOT just bullet points
- **Color scheme**: Navy + Accent (#00F5D4) + professional neutrals
- **Font sizes**: Header 28pt, body 13-14pt, table 10-11pt
- **Figure quality**: 300 DPI, tight layout, white background
- **No cartoon shapes** — use matplotlib for real scientific figures

## Helper Functions (from report modules)

See `references/helpers.md` for the complete helper function implementations:
- `_header(slide, text)` — navy header bar with white title
- `_textbox(slide, ...)` — styled text box
- `_bullets(slide, ...)` — bullet point list
- `_table(slide, ...)` — table with alternating row colors
- `_add_picture(slide, ...)` — image with aspect ratio preservation
- `TempImageStore` — manages temp figure files

## Workflow

```python
# 1. Create presentation
prs = Presentation()
prs.slide_width = Inches(13.333)  # 16:9
prs.slide_height = Inches(7.5)

# 2. Generate figures
img_store = TempImageStore()
fig, ax = plt.subplots(figsize=(12, 5))
# ... create plot ...
fig_path = img_store.save_fig(fig, "my_plot")

# 3. Build slide
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = C_BG
_header(slide, "My Analysis Results")
_add_picture(slide, fig_path, 0.5, 1.2, 12.3, 5)
_bullets(slide, 0.5, 6.3, 12.3, 1, ["Key finding 1", "Key finding 2"])

# 4. Save
prs.save("output.pptx")
img_store.cleanup()
```

## Pitfalls

- **User explicitly rejected** colored boxes/shapes as figure substitutes — always use matplotlib for real data
- **User explicitly rejected** text-only slides — every slide needs visual content
- **Must check existing report modules** before creating new report PPTs
- **JSON spec approach produces poor results** for scientific presentations
- **Do NOT put PPT files in source code repositories** — output to data directories only
- **User expects you to find real content** — search for figures, diagrams, and data online, don't just create placeholder shapes
- **Include ALL datasets** — if there are 4 groups (e.g., hystera CR, hystera scTE, ovaries CR, ovaries scTE), show ALL of them, not just one
- **Include marker gene lists** — users want to see the complete marker sets used for annotation
- **Don't distort images** — use aspect ratio preservation in `_add_picture()`; never stretch images to fill space
- **Workflow description should be generic** — filtering parameters vary by tissue and quantification method; don't hardcode one specific set of parameters
- **PPT must be comprehensive** — include: workflow, QC results, cell type proportions (all groups), marker lists, differential analysis, conclusions
- **Table formatting** — use alternating row colors, centered text, bold headers (see RNAseq_report pattern)
- **Never hardcode sample-to-group mappings or display names** — `infer_group()` and `_short_name()` must be configurable via JSON config (`sample_groups`, `short_names`) with CLI passthrough (`--sample-groups`, `--short-names` as JSON strings), falling back to auto-detection when not provided. Same for group color maps in plots — use a dynamic fallback palette instead of hardcoded `{"7SL": ..., "U1": ...}` dicts. See `ncRNAseq_report` module for the full pattern: JSON defaults → smk `config.get()` → `_json.dumps()` in cmd → `argparse` → module-level `_SAMPLE_GROUPS` / `_SHORT_NAMES` dicts populated in `main()`.
