# Chinese Academic Thesis Generation in Docx Format

When generating Chinese academic theses (硕士/博士学位论文) as .docx files, the JSON spec approach in `docx_create.py` breaks for large documents with Chinese text. Use the direct python-docx approach instead.

## Why JSON Spec Fails for Large Chinese Documents

The `docx_create.py` JSON spec approach has these failure modes with Chinese academic text:
1. **Escaped quotes in strings**: Chinese text containing `"` inside Python f-strings or JSON causes `SyntaxError`
2. **Special characters**: Text with `<`, `>`, `&` in bioinformatics contexts (e.g., `C>T`, `C[C>T]G`) breaks JSON parsing
3. **Long paragraphs**: JSON files with 200+ paragraphs of Chinese text are hard to debug when errors occur

## Reliable Approach: Direct python-docx Script

Write a Python script using `python-docx` directly, save to `/tmp/`, execute via `terminal`.

```python
#!/usr/bin/env python3
from docx import Document
from docx.shared import Pt, Mm
from docx.enum.text import WD_BREAK

doc = Document()
section = doc.sections[0]
section.page_width = Mm(210)
section.page_height = Mm(297)
section.top_margin = Mm(25)
section.bottom_margin = Mm(25)
section.left_margin = Mm(30)
section.right_margin = Mm(25)

def add_body(text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(24)  # Chinese indent = 2 chars
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    run.font.size = Pt(12)  # 小四号

# ... add content ...
doc.save("output.docx")
```

## Chinese Thesis Standard Formatting

| Element | Font | Size | Style |
|---------|------|------|-------|
| Title (封面) | SimSun (宋体) | 22pt (二号) | Bold, centered |
| Chapter heading | SimHei (黑体) | 16pt (三号) | Bold |
| Section heading | SimHei (黑体) | 14pt (四号) | Bold |
| Body text | SimSun (宋体) | 12pt (小四) | 1.5 line spacing |
| Abstract | SimSun (宋体) | 11pt (五号) | Normal |

- First line indent for body: `Pt(24)` (2 Chinese characters at 12pt)
- Page: A4 (210x297mm), margins 25mm top/bottom, 30mm left, 25mm right
- TOC: Add as placeholder text, user updates fields in Word

## Pitfalls

1. **pip install timeout in execute_code**: `pip install` inside `execute_code` sandbox often times out. Use `terminal` for pip installs.
2. **openpyxl for Excel inspection**: When pandas is too slow for large Excel files, use `openpyxl.load_workbook(read_only=True, data_only=True)` with `iter_rows(max_row=3)` for fast header inspection.
3. **Unicode escapes**: When writing Chinese text in Python scripts, use raw strings or `\u` escapes if the terminal encoding is uncertain. Better: write the script via `write_file` tool (handles UTF-8 correctly) then execute via `terminal`.
4. **TOC field codes**: python-docx writes field codes but Word/LibreOffice must compute the actual TOC entries. Add a placeholder note telling the user to update fields.
5. **Paragraph count**: A full thesis typically has 200+ paragraphs. The script approach is more maintainable than JSON spec for this scale.
