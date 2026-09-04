# HTML+CSS Two-Column Resume Layout (Chrome Headless)

When reportlab output looks "ugly" or when single-page density requires better layout control, use HTML+CSS with Chrome headless for PDF generation. This approach gives much better visual results (colors, gradients, flexbox columns, card-style sections).

## Architecture

```
Markdown source (.md)  →  Python script  →  HTML with embedded CSS  →  Chrome headless  →  PDF
     (editable)           (parse + render)      (two-column flexbox)     (--print-to-pdf)
```

User edits the `.md` file and runs `python3 gen_resume.py` to regenerate.

## Quick Start

```bash
# Chrome must be available
which google-chrome

# Generate
python3 gen_resume.py input.md output.pdf
```

## HTML Template with Two-Column Layout

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 9pt; line-height: 1.45; color: #2d3748;
    background: white; padding: 12mm 15mm;
}

/* Header with blue accent bar */
.header {
    display: flex; align-items: stretch;
    margin-bottom: 10px; border-radius: 4px; overflow: hidden;
}
.header-accent {
    width: 6px;
    background: linear-gradient(180deg, #1e40af 0%, #3b82f6 100%);
    flex-shrink: 0;
}
.header-content {
    padding: 8px 12px; background: #f0f4ff; flex-grow: 1;
}
.header-content h1 {
    font-size: 20pt; color: #1e3a5f; margin-bottom: 1px;
    letter-spacing: 2px; font-weight: 700;
}
.header-content .title {
    font-size: 10pt; color: #2563eb; margin-bottom: 4px; font-weight: 500;
}
.header-content .contact {
    font-size: 8.5pt; color: #4a5568;
    display: flex; flex-wrap: wrap; gap: 12px;
}
.header-content .contact-item::before {
    content: ""; display: inline-block; width: 4px; height: 4px;
    background: #3b82f6; border-radius: 50%; margin-right: 4px;
}

/* Two-column layout */
.container { display: flex; gap: 20px; }
.left { width: 36%; flex-shrink: 0; }
.right { width: 64%; border-left: 2px solid #e2e8f0; padding-left: 18px; }

/* Section titles with blue bar accent */
.section { margin-bottom: 8px; }
.section-title {
    font-size: 10pt; font-weight: 700; color: #1e40af;
    padding-bottom: 3px; border-bottom: 2px solid #dbeafe;
    margin-bottom: 5px; display: flex; align-items: center; gap: 5px;
}
.section-title::before {
    content: ""; display: inline-block; width: 4px; height: 14px;
    background: #2563eb; border-radius: 2px;
}

/* Content */
.content p { margin-bottom: 3px; font-size: 8.5pt; line-height: 1.4; color: #4a5568; }
.content ul { list-style: none; padding: 0; margin: 3px 0; }
.content li {
    margin-bottom: 3px; font-size: 8.5pt; line-height: 1.35;
    padding-left: 12px; position: relative; color: #4a5568;
}
.content li::before {
    content: "▸"; position: absolute; left: 0; color: #3b82f6; font-size: 8pt;
}
.content b { color: #2d3748; font-weight: 600; }

/* Education card style */
.edu-item {
    margin-bottom: 5px; padding: 4px 6px;
    background: #f8fafc; border-radius: 4px; border-left: 3px solid #dbeafe;
}
.edu-item .school { font-weight: 700; font-size: 9pt; color: #2d3748; }
.edu-item .major { font-size: 8pt; color: #6b7280; margin-bottom: 2px; }
.edu-item .time { font-size: 7.5pt; color: #9ca3af; }
.edu-item .detail { font-size: 8pt; color: #4a5568; margin-top: 3px; }

/* Skill category */
.skill-category { margin-bottom: 6px; }
.skill-category .label { font-weight: 600; font-size: 8.5pt; color: #2d3748; margin-bottom: 2px; }
.skill-category .items { font-size: 8pt; color: #4a5568; line-height: 1.4; }

/* Experience header */
.exp-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; }
.exp-header .company { font-weight: 700; font-size: 9.5pt; color: #2d3748; }
.exp-header .time { font-size: 7.5pt; color: #9ca3af; white-space: nowrap; }
.exp-subtitle { font-size: 8pt; color: #6b7280; margin-bottom: 5px; font-style: italic; }

/* Project card */
.project-block {
    margin-bottom: 6px; padding: 5px 6px;
    background: #fafbfc; border-radius: 4px; border: 1px solid #e2e8f0;
}

/* Print */
@media print {
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; padding: 12mm 15mm; }
    .section-title { break-after: avoid; }
    .exp-header, .project-block, .edu-item { break-inside: avoid; }
}
</style>
</head>
<body>
<!-- Header -->
<div class="header">
    <div class="header-accent"></div>
    <div class="header-content">
        <h1>姓名</h1>
        <div class="title">职位</div>
        <div class="contact">
            <span class="contact-item">电话</span>
            <span class="contact-item">邮箱</span>
        </div>
    </div>
</div>

<!-- Two columns -->
<div class="container">
    <div class="left">
        <!-- 个人总结, 教育背景, 专业技能 -->
    </div>
    <div class="right">
        <!-- 实习经历, 项目经历 -->
    </div>
</div>
</body>
</html>
```

## Python Generator Script (gen_resume.py)

```python
#!/usr/bin/env python3
"""Resume generator: HTML → PDF via Chrome headless"""
import sys, subprocess

def main():
    input_html = sys.argv[1] if len(sys.argv) > 1 else 'resume.html'
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else 'resume.pdf'
    
    result = subprocess.run([
        'google-chrome', '--headless', '--disable-gpu',
        f'--print-to-pdf={output_pdf}', '--no-margins',
        f'file://{input_html}'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ PDF generated: {output_pdf}")
        import pymupdf
        doc = pymupdf.open(output_pdf)
        print(f"  Pages: {doc.page_count}")
        doc.close()
    else:
        print(f"✗ Failed: {result.stderr}")

if __name__ == '__main__':
    main()
```

## Two-Column Content Distribution

**Left column (~36%)** — "能力基础":
- 个人总结 (2-3 sentences)
- 教育背景 (reverse chronological, card style)
- 专业技能 (by category)

**Right column (~64%)** — "实践应用":
- 实习经历 (company + bullets)
- 项目经历 (project cards with border)

## Layout Tuning for Single Page

When content overflows to 2 pages, adjust in this order:
1. Reduce `padding` on body (12mm → 10mm)
2. Reduce `line-height` (1.45 → 1.35)
3. Reduce `margin-bottom` on `.section` (8px → 6px)
4. Reduce `font-size` on body (9pt → 8.5pt)
5. Reduce header padding and font sizes
6. Cut content (better than squeezing)

**NEVER** just reduce line-height to extreme values — content becomes unreadable. Cut sections instead.

## Verification

```python
import pymupdf
doc = pymupdf.open('resume.pdf')
page = doc[0]
pix = page.get_pixmap(dpi=200)
pix.save('preview.png')
# Then use vision_analyze on preview.png
```

## Pitfalls

- **User said "太丑"**: reportlab output lacks visual polish. Switch to HTML+CSS approach immediately.
- **User said "不可以编辑调整"**: They want to edit the SOURCE, not the generated HTML. Keep markdown as the editing surface, generate HTML from it.
- **Just compressing text ≠ fixing layout**: When user says "还是两页", don't just cut words. Fix the layout (columns, spacing, font sizes) first.
- **Always verify visually**: Generate PDF → PNG → vision_analyze before presenting to user. Never trust that markdown looks good in PDF without checking.
- **Chrome headless --no-margins**: Required because @page margin in CSS handles margins. Without this flag, Chrome adds its own margins on top.
- **Flexbox gap**: Not supported in all Chrome headless versions. If columns don't separate, add margin/padding instead.
