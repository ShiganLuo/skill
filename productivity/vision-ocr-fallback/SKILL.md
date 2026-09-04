---
name: vision-ocr-fallback
description: "OCR scanned PDFs via vision when tesseract unavailable."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [OCR, PDF, Scanned-Documents, Vision, Fallback, CJK]
    related_skills: [ocr-and-documents, pdf]
---

# Vision-Based OCR Fallback

Use `vision_analyze` to read scanned documents when traditional OCR tools are unavailable.

**Trigger**: pymupdf returns empty text on pages that contain images (scanned PDFs), AND tesseract is not installed AND marker-pdf is too large to install (~3-5GB).

## Step 1: Detect Scanned vs Text Pages

```python
import pymupdf
doc = pymupdf.open("document.pdf")
scanned_pages = []
text_pages = {}
for i in range(doc.page_count):
    page = doc[i]
    blocks = page.get_text("blocks")
    text = page.get_text().strip()
    images = page.get_images(full=True)
    if len(blocks) == 0 and len(images) > 0:
        scanned_pages.append(i)
    elif text:
        text_pages[i] = text
print(f"Text pages: {list(text_pages.keys())}")
print(f"Scanned pages: {scanned_pages}")
```

**Key signal**: `len(blocks) == 0 and len(images) > 0` means the page has a background image but no selectable text layer.

## Step 2: Render Scanned Pages to PNG

```python
from pathlib import Path
output_dir = "/tmp/pdf_pages"
Path(output_dir).mkdir(parents=True, exist_ok=True)

for i in scanned_pages:
    page = doc[i]
    mat = pymupdf.Matrix(300/72, 300/72)  # 300 DPI for OCR quality
    pix = page.get_pixmap(matrix=mat)
    out_path = f"{output_dir}/page_{i+1}.png"
    pix.save(out_path)
```

## Step 3: Vision-Analyze Each Page

Call `vision_analyze` with a specific prompt per page type:

```
vision_analyze(
    image_url="/tmp/pdf_pages/page_4.png",
    question="请完整提取这个页面的所有文字内容，保持原始排版格式。"
)
```

For pages with tables:
```
question="请完整提取这个页面的所有文字内容。如果有表格，用markdown表格格式输出。"
```

Multiple vision_analyze calls can be made in parallel (they're independent).

## Step 4: Merge into Final Document

Combine pymupdf text (for text pages) with vision output (for scanned pages) into a single markdown file. Preserve page order.

## Pitfalls

- **pymupdf4llm timeout**: `to_markdown()` can hang on complex PDFs. Use `get_text()` page-by-page as primary.
- **300 DPI sweet spot**: Lower than 200 DPI loses clarity. Higher than 300 DPI wastes tokens.
- **CJK documents**: Vision models handle CJK well — no language pack needed.
- **Only render scanned pages**: If a page has both text blocks AND images, skip rendering — pymupdf already extracted the text.
- **Large PDFs**: Process scanned pages in batches to avoid context overflow.
