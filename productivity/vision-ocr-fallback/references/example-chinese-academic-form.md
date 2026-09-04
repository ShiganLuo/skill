# Real-World Example: Chinese Academic Form PDF

## Input
- File: 7-page Chinese PDF (专业实践工作计划表)
- Pages 1,3,7: text-based (pymupdf extracted text directly)
- Pages 2,4,5,6: scanned images (zero text blocks,1 image each)
- Size: 2.4MB

## Detection Output
```
Page 1: TEXT (128 chars)
Page 2: SCANNED (image only, no text layer)
Page 3: TEXT (631 chars)
Page 4: SCANNED (image only, no text layer)
Page 5: SCANNED (image only, no text layer)
Page 6: SCANNED (image only, no text layer)
Page 7: TEXT (206 chars)
```

## Approach
1. pymupdf extracted text from pages1,3,7 directly
2. Rendered pages2,4,5,6 to PNG at300 DPI (2480x3509 pixels)
3. vision_analyze called in parallel on all4 images
4. Merged into single5,594-char markdown file

## Vision Prompts Used
- Page2 (说明): "请完整提取这个PDF页面的所有文字内容，保持原始排版格式。这是一个中文文档页面。"
- Pages4-6 (含表格): "请完整提取这个PDF页面的所有文字内容，保持原始排版格式。这是一个中文文档页面，可能包含表格。"

## Result
All content successfully extracted including:
- Basic info table (姓名/性别/出生日期 etc.)
- Numbered work items (多组学测序策略, 数据处理与质量控制, etc.)
- Progress schedule table (2025.09-2026.03)
- Expected outcomes paragraph
- Signature sections

## Lessons
- Table formatting in vision output was inconsistent — some came as ASCII tables, some as prose
- The model did well with Chinese text including technical terms (外显子组测序, RNA-seq, etc.)
- Parallel vision_analyze calls saved significant time
