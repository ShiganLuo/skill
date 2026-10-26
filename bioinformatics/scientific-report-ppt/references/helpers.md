# python-pptx Helper Functions for Scientific Reports

Extracted from `workflow/Omics/modules/RNAseq_report/bin/generate_report.py`.

## Constants

```python
SLIDE_W = 13.333  # 16:9 aspect ratio
SLIDE_H = 7.5
HEADER_H = 0.85
MARGIN_L = 0.5
MARGIN_R = 0.5
CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R
DPI = 300

# Color scheme
C_NAVY = RGBColor(0x0D, 0x1B, 0x2A)
C_ACCENT = RGBColor(0x00, 0xF5, 0xD4)
C_BLUE = RGBColor(0x00, 0xB4, 0xD8)
C_GREEN = RGBColor(0x00, 0xA8, 0x78)
C_RED = RGBColor(0xD6, 0x45, 0x45)
C_ORANGE = RGBColor(0xF0, 0x9A, 0x36)
C_TEXT = RGBColor(0x2D, 0x37, 0x48)
C_MUTED = RGBColor(0x71, 0x80, 0x96)
C_BG = RGBColor(0xFA, 0xFB, 0xFC)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
```

## TempImageStore

```python
import tempfile
import shutil
import os

class TempImageStore:
    def __init__(self):
        self.paths = []

    def save_fig(self, fig, stem: str) -> str:
        fd, tmp_path = tempfile.mkstemp(prefix=f"{stem}_", suffix=".png")
        os.close(fd)
        fig.savefig(tmp_path, dpi=DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self.paths.append(tmp_path)
        return tmp_path

    def cleanup(self):
        for path in self.paths:
            if os.path.exists(path):
                os.unlink(path)
```

## Header Bar

```python
def _header(slide, text: str):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(SLIDE_W), Inches(HEADER_H))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_NAVY
    bar.line.fill.background()
    tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(0.12), Inches(CONTENT_W), Inches(0.6))
    tf = tx.text_frame
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = C_WHITE
```

## Text Box

```python
def _textbox(slide, left, top, width, height, text, font_size=14, bold=False, color=C_TEXT, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = align
    return box
```

## Bullets

```python
def _bullets(slide, left, top, width, height, items, font_size=13, color=C_TEXT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.space_after = Pt(6)
    return box
```

## Table (with alternating row colors)

```python
def _table(slide, left, top, width, height, data, font_size=11):
    rows = len(data)
    cols = len(data[0]) if data else 1
    shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(height))
    tbl = shape.table
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = str(value)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = C_NAVY
            elif r % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(0xF1, 0xF5, 0xFA)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(font_size)
                p.alignment = PP_ALIGN.CENTER
                if r == 0:
                    p.font.bold = True
                    p.font.color.rgb = C_WHITE
                else:
                    p.font.color.rgb = C_TEXT
    return tbl
```

## Add Picture (with aspect ratio preservation)

```python
def _add_picture(slide, path: str, left: float, top: float, max_w: float, max_h: float):
    if not path or not os.path.isfile(path):
        return None
    from PIL import Image as PILImage
    img = PILImage.open(path)
    aspect = img.size[0] / max(img.size[1], 1)
    width = max_w
    height = width / aspect
    if height > max_h:
        height = max_h
        width = height * aspect
    x = left + (max_w - width) / 2
    slide.shapes.add_picture(path, Inches(x), Inches(top), Inches(width), Inches(height))
    return width, height
```

## Slide Template (blank layout with background)

```python
def make_slide(prs, title_text):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = C_BG
    _header(slide, title_text)
    return slide
```
