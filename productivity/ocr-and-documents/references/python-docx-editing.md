# python-docx: Reading & Editing Word Documents

## .doc (legacy) → .docx Conversion

python-docx only handles .docx (Office Open XML). For old .doc (Compound Document / OLE2):

```bash
libreoffice --headless --convert-to docx "input.doc" --outdir /tmp/
```

- Output lands in the `--outdir` directory with `.docx` extension
- Suppress Java warnings with `2>&1 | grep -v javaldx` if needed
- LibreOffice preserves tables, merged cells, images, and formatting well
- If LibreOffice is not available, `antiword` or `catdoc` can extract plain text but lose all structure

**Pitfall**: Always convert .doc → .docx FIRST, then use python-docx. Don't try to read .doc directly.

## Installing python-docx

```bash
pip install python-docx
```

On systems with SOCKS proxy issues: `env -u http_proxy -u https_proxy -u all_proxy pip install python-docx`

## Reading Document Structure

```python
from docx import Document
doc = Document('file.docx')

# Paragraphs
for i, p in enumerate(doc.paragraphs):
    if p.text.strip():
        print(f'P{i}: {p.text}')

# Tables
for ti, table in enumerate(doc.tables):
    print(f'Table {ti}: {len(table.rows)}r x {len(table.columns)}c')
    for ri, row in enumerate(table.rows):
        cells = [c.text.strip().replace('\n', ' | ') for c in row.cells]
        print(f'  R{ri}: {cells}')
```

## Inspecting Merged Cells

Tables often have merged cells (gridSpan for horizontal, vMerge for vertical).
You CANNOT reliably tell which cells are merged from `.text` output alone —
python-docx returns the same underlying `_tc` element for all cells in a merged group.

```python
from docx.oxml.ns import qn

for ri, row in enumerate(table.rows):
    for ci, cell in enumerate(row.cells):
        tc = cell._tc
        tc_pr = tc.find(qn('w:tcPr'))
        grid_span = v_merge = None
        if tc_pr is not None:
            gs = tc_pr.find(qn('w:gridSpan'))
            if gs is not None:
                grid_span = gs.get(qn('w:val'))
            vm = tc_pr.find(qn('w:vMerge'))
            if vm is not None:
                v_merge = vm.get(qn('w:val'))  # 'restart' or None(=continue)

        # Show paragraph-level detail
        for p in cell.paragraphs:
            runs = [(r.text, r.bold) for r in p.runs]
            print(f'  R{ri}C{ci}: gridSpan={grid_span} vMerge={v_merge} '
                  f'align={p.alignment} runs={runs}')
```

**Key insight**: When gridSpan=N, python-docx repeats the same cell object N times
in the row iteration. So `row.cells[0] is row.cells[1]` when col 0 has gridSpan=2.
To find the "real" content cell, pick the first one (lowest column index).

## Editing Table Cell Content

### Clear and rewrite a cell

```python
from docx.enum.text import WD_ALIGN_PARAGRAPH

cell = table.rows[1].cells[3]

# Clear all existing runs in all paragraphs
for p in cell.paragraphs:
    for r in p.runs:
        r.text = ""

# Use the first paragraph (preserves cell formatting)
first_para = cell.paragraphs[0]
first_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
run = first_para.add_run("New text here")
run.font.size = Pt(10.5)
run.font.name = '宋体'

# Add a second paragraph (e.g., for evaluation line)
eval_para = cell.add_paragraph()
eval_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
eval_run = eval_para.add_run("合格☑   不合格□")
eval_run.font.size = Pt(10.5)

# Remove any leftover empty paragraphs
while len(cell.paragraphs) > 2:
    p_element = cell.paragraphs[-1]._element
    p_element.getparent().remove(p_element)
```

### Pitfalls

1. **Don't replace the cell object** — modify in-place. `cell = new_content` does nothing.
2. **Clear runs, don't delete paragraphs** — deleting all paragraphs can break the XML structure.
   Clear text from runs instead, then add new content to existing paragraphs.
3. **Alignment values**: `WD_ALIGN_PARAGRAPH.LEFT=0, CENTER=1, RIGHT=2, JUSTIFY=3`
4. **Font name**: For Chinese text, use `'宋体'` (Song) or `'仿宋'` (FangSong). Setting `font.name`
   alone may not work for CJK — also set `font.element` with East Asian font via XML if needed.
5. **Merged cell write target**: When a cell has gridSpan, write to the FIRST cell index only
   (e.g., `row.cells[0]` not `row.cells[2]`). All indices in the span share the same XML element.

## Reading Images in Cells

```python
from docx.oxml.ns import qn

for p in cell.paragraphs:
    for r in p.runs:
        if r._element.findall('.//' + qn('w:drawing')):
            print("[IMAGE found]")
        if r._element.findall('.//' + qn('w:pict')):
            print("[PICT found]")
```

## Common Document Patterns (Chinese Academic Forms)

Chinese university forms (实践报告, 开题报告, etc.) typically use:
- First table: basic info (name, ID, advisor, dates)
- Middle tables: content areas (may span full width with gridSpan)
- Last table: evaluation section with rows for:
  - 实践导师意见 (practice supervisor comment)
  - 校内导师意见 (university advisor comment)
  - 审核意见 (review committee comment)
  - Each has: comment text + 合格□/不合格□ checkbox + signature + date

The evaluation cells typically have a pre-filled template like:
`合格□   不合格□   实践导师签名：\n年   月   日`

Strategy: insert comment text as a new paragraph BEFORE the evaluation line,
keep the template line below for printing + hand-signing.
