# PDF Generation with Reportlab (Chinese Resume)

## Quick Start

```bash
pip install reportlab pymupdf
```

## Template Script

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Chinese font
pdfmetrics.registerFont(TTFont('Chinese', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'))

# Styles
PRIMARY = HexColor('#1a1a1a')
SECONDARY = HexColor('#4a4a4a')
ACCENT = HexColor('#2563eb')
LIGHT_GRAY = HexColor('#e5e7eb')

name_style = ParagraphStyle('Name', fontName='Chinese', fontSize=18, leading=22, textColor=PRIMARY, spaceAfter=2*mm)
contact_style = ParagraphStyle('Contact', fontName='Chinese', fontSize=9, leading=11, textColor=SECONDARY, spaceAfter=3*mm)
section_style = ParagraphStyle('Section', fontName='Chinese', fontSize=11, leading=13, textColor=ACCENT, spaceBefore=3*mm, spaceAfter=2*mm)
h3_style = ParagraphStyle('H3', fontName='Chinese', fontSize=10, leading=12, textColor=PRIMARY, spaceBefore=2*mm, spaceAfter=1*mm)
body_style = ParagraphStyle('Body', fontName='Chinese', fontSize=9, leading=11, textColor=SECONDARY, spaceAfter=1*mm)
bullet_style = ParagraphStyle('Bullet', fontName='Chinese', fontSize=9, leading=11, textColor=SECONDARY, leftIndent=8, spaceAfter=1*mm, bulletIndent=0)

# Document
doc = SimpleDocTemplate('resume.pdf', pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=15*mm, bottomMargin=12*mm)

# Education table (time right-aligned)
edu_data = [
    ['<b>School</b> — Major', '2024 - 2027'],
    ['Details...', ''],
]
edu_table = Table(edu_data, colWidths=[120*mm, 50*mm])
edu_table.setStyle(TableStyle([
    ('FONT', (0,0), (-1,-1), 'Chinese', 9),
    ('ALIGN', (1,0), (1,-1), 'RIGHT'),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('TOPPADDING', (0,0), (-1,-1), 0),
    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ('LEFTPADDING', (0,0), (-1,-1), 0),
]))

# Build
content = [Paragraph('Name', name_style), ...]
doc.build(content)
```

## Key Layout Parameters (A4 single page)

- Margins: 18mm left/right, 15mm top, 12mm bottom
- Font sizes: name=18, section=11, h3=10, body=9, bullet=9
- Line spacing: 1.2x font size (leading)
- Section divider: HRFlowable with LIGHT_GRAY
- Space between sections: 3mm before, 2mm after
- Education table: 120mm + 50mm columns

## Verification Workflow

```python
import pymupdf

# Check page count
doc = pymupdf.open('resume.pdf')
print(f"Pages: {doc.page_count}")  # Must be 1

# Convert to image for vision_analyze
page = doc[0]
pix = page.get_pixmap(dpi=200)
pix.save('resume_preview.png')
```

Then use `vision_analyze` on the PNG to verify layout before presenting.

## Common Pitfalls

- **Chinese font not found**: Try multiple paths in order:
  - `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`
  - `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`
  - `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc`
- **Two pages**: Reduce font sizes by 0.5pt, tighten margins by 1mm, or shorten content
- **Hollow content**: Don't merge bullet points into paragraphs; keep structure but shorten each bullet
