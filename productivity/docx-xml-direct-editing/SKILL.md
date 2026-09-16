---
name: docx-xml-direct-editing
description: "Edit .docm files or bulk-restructure Word docs via raw XML."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [word, docx, docm, xml, office, documents, restructuring]
    category: productivity
    related_skills: [docx]
---

# Docx XML Direct Editing

When `python-docx` cannot handle a file (`.docm` macro-enabled documents,
corrupted packages, or files with non-standard content types), fall back
to direct XML manipulation via `zipfile` + `xml.etree.ElementTree`. Also
use this approach for **bulk section restructuring** — inserting,
deleting, and rewriting many paragraphs in a single pass — even on valid
`.docx` files, because python-docx's paragraph-index API becomes fragile
when doing 20+ insertions/deletions in one operation.

## When to Use

- `python-docx` raises `ValueError: not a Word file, content type is
  'application/vnd.ms-word.document.macroEnabled.main+xml'` (`.docm`).
- You need to restructure an entire chapter/section: delete N paragraphs,
  insert M new ones, rewrite text in others — all in one pass.
- The built-in `docx_edit.py` scripts can't handle the scale or
  complexity of the edit.
- **Not for**: simple find-replace or single-paragraph edits — use the
  standard `docx` skill scripts for those.

## Prerequisites

- Python 3.10+ (stdlib only: `zipfile`, `xml.etree.ElementTree`, `copy`)
- No external packages needed

## Core Technique

### 1. Read the document

```python
import zipfile
import xml.etree.ElementTree as ET

with zipfile.ZipFile(path) as z:
    xml_bytes = z.read('word/document.xml')
    other_files = {n: z.read(n) for n in z.namelist()
                   if n != 'word/document.xml'}

tree = ET.fromstring(xml_bytes)
ns_w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ns = {'w': ns_w}
body = tree.find('.//w:body', ns)
paragraphs = list(body.findall('w:p', ns))
```

### 2. Identify paragraphs

Word stores styles as numeric IDs in `w:pStyle` `w:val` attribute.
Common values (vary by template):

| val | Typical meaning |
|-----|----------------|
| 3   | Heading 1 (chapter) |
| 4   | Heading 2 (section) |
| 5   | Heading 3 (subsection) |
| 6   | Heading 4 (sub-subsection) |
| 15  | Figure caption |
| (empty) | Body text |

```python
def get_style(p):
    pPr = p.find('w:pPr', ns)
    if pPr is not None:
        pStyle = pPr.find('w:pStyle', ns)
        if pStyle is not None:
            return pStyle.get(f'{{{ns_w}}}val', '')
    return ''

def get_text(p):
    return ''.join(
        t.text for r in p.findall('.//w:r', ns)
        for t in r.findall('w:t', ns) if t.text
    ).strip()
```

### 3. Create new paragraphs from templates

**Always** deepcopy an existing paragraph of the target style to use as
template. This preserves all XML attributes (spacing, indentation, fonts)
that you'd miss if building from scratch.

```python
from copy import deepcopy

tpl_body = deepcopy(paragraphs[some_body_idx])
tpl_h5 = deepcopy(paragraphs[some_h5_idx])
tpl_h6 = deepcopy(paragraphs[some_h6_idx])

def make_paragraph(text, style, template_p):
    new_p = deepcopy(template_p)
    # Remove old runs (preserve drawings/picts)
    for r in list(new_p.findall('w:r', ns)):
        if r.find('.//w:drawing', ns) is None and r.find('.//w:pict', ns) is None:
            new_p.remove(r)
    # Set style
    pPr = new_p.find('w:pPr', ns)
    if pPr is None:
        pPr = ET.SubElement(new_p, f'{{{ns_w}}}pPr')
        new_p.insert(0, pPr)
    pStyle = pPr.find('w:pStyle', ns)
    if pStyle is None:
        pStyle = ET.SubElement(pPr, f'{{{ns_w}}}pStyle')
    pStyle.set(f'{{{ns_w}}}val', style)
    # Add text run (copy rPr from template)
    if text:
        rPr_ref = None
        for r in template_p.findall('.//w:r', ns):
            for t in r.findall('w:t', ns):
                if t.text and t.text.strip():
                    rPr_ref = r.find('w:rPr', ns)
                    break
            if rPr_ref is not None:
                break
        r = ET.Element(f'{{{ns_w}}}r')
        if rPr_ref is not None:
            r.append(deepcopy(rPr_ref))
        t = ET.SubElement(r, f'{{{ns_w}}}t')
        t.set(f'{{{ns_w}}}space', 'preserve')
        t.text = text
        idx = list(new_p).index(pPr) + 1
        new_p.insert(idx, r)
    return new_p
```

### 4. Modify existing paragraph text in-place

```python
def set_para_text(p, text, template_p=None):
    if template_p is None:
        template_p = p
    # Remove non-drawing runs
    for r in list(p.findall('w:r', ns)):
        if r.find('.//w:drawing', ns) is None and r.find('.//w:pict', ns) is None:
            p.remove(r)
    # Add new run
    r = ET.Element(f'{{{ns_w}}}r')
    rPr_ref = template_p.find('.//w:rPr', ns)
    if rPr_ref is not None:
        r.append(deepcopy(rPr_ref))
    t = ET.SubElement(r, f'{{{ns_w}}}t')
    t.set(f'{{{ns_w}}}space', 'preserve')
    t.text = text
    pPr = p.find('w:pPr', ns)
    idx = list(p).index(pPr) + 1 if pPr is not None else 0
    p.insert(idx, r)
```

### 5. Insert and delete paragraphs

```python
# Delete (iterate in reverse to keep indices stable)
for idx in sorted(indices_to_delete, reverse=True):
    body.remove(paragraphs[idx])

# Insert (after refreshing paragraphs list)
paragraphs = list(body.findall('w:p', ns))
pos = list(body).index(anchor_para) + 1
for i, new_p in enumerate(new_paras):
    body.insert(pos + i, new_p)
```

### 6. Write back

**Critical**: register ALL namespaces before serializing, or the output
XML will have `ns0:`, `ns1:` prefixes that Word can't open.

```python
ET.register_namespace('w', ns_w)
for prefix, uri in [
    ('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'),
    ('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'),
    ('a', 'http://schemas.openxmlformats.org/drawingml/2006/main'),
    ('pic', 'http://schemas.openxmlformats.org/drawingml/2006/picture'),
    ('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006'),
    ('w14', 'http://schemas.microsoft.com/office/word/2010/wordml'),
    ('w15', 'http://schemas.microsoft.com/office/word/2012/wordml'),
]:
    ET.register_namespace(prefix, uri)

modified_xml = ET.tostring(tree, encoding='UTF-8', xml_declaration=True)
with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zout:
    zout.writestr('word/document.xml', modified_xml)
    for name, data in other_files.items():
        zout.writestr(name, data)
```

## Narrative-Driven Section Restructuring (Lessons Learned)

When rewriting an entire thesis chapter/section, resist the urge to organize
by data type (mutations → DDR → TE → integration). Instead, build a **narrative
arc**:

1. **Hook** — frame a central question (e.g., "does reprogramming cost genome stability?")
2. **Act 1** — present the surprising observation (mutations in DDR genes themselves)
3. **Act 2** — reveal the mechanism (repair strategy switch: fidelity → speed)
4. **Act 3** — show the consequence (transposons exploit the gap)
5. **Act 4** — integrate into a model (mutation→repair→TE cascade)
6. **Resolution** — biological significance + bridge to next chapter

Each H5 title should be a story beat, not a data category label.
"修复防线的失守与转座子的复活" creates curiosity; "转座子分析" does not.

**Pitfall: Patchwork editing ≠ rewriting.** If you move/merge existing paragraphs
instead of writing new text, the user will notice. When asked to "清空重写",
delete ALL content in the range and write from scratch. Never reuse old paragraph
text as-is.

**Pitfall: Ask before doing massive rewrites.** Draft the narrative structure
(new H5 titles + one-sentence summary of each section) and get user buy-in
before writing 50+ paragraphs. The user may want to adjust the story arc.

## Pitfalls

- **ALWAYS backup first.** `shutil.copy2(path, backup)` before any write.
- **Index shift on insert/delete.** After inserting or deleting paragraphs,
  all subsequent indices change. Either refresh `paragraphs = list(body.findall(...))`
  after each batch, or process in reverse order for deletions.
- **Don't hardcode paragraph indices.** Find paragraphs by text content
  matching, not by absolute index — the document may have been edited
  between planning and execution.
- **Style IDs are template-specific.** `style='5'` means H3 in one template
  but could be something else in another. Always dump styles first:
  `{i} [{get_style(p)}]: {get_text(p)[:100]}`.
- **Deepcopy for templates.** Never build a `w:p` element from scratch —
  you'll miss dozens of implicit attributes. Always deepcopy an existing
  paragraph of the target style.
- **Template paragraphs carry over images.** When creating text-only paragraphs
  from a deepcopy template, the template may contain `<w:drawing>` (embedded
  images) or `<w:pict>` elements inside runs. These get duplicated into your
  new "text" paragraphs, causing ghost images in Word. **Fix**: strip ALL runs
  from the template immediately after deepcopy, before using it:
  ```python
  tpl = deepcopy(paragraphs[some_idx])
  for r in list(tpl.findall('w:r', ns)):
      if r.find('.//w:drawing', ns) is None and r.find('.//w:pict', ns) is None:
          tpl.remove(r)
      # Keep drawing-containing runs ONLY if the new paragraph needs images
  ```
  Then add your text run fresh.
- **Preserve drawings and picts.** When clearing runs from a paragraph,
  check for `w:drawing` or `w:pict` children before removing — figures
  and embedded objects live inside runs.
- **Namespace registration is mandatory.** Without `ET.register_namespace`
  for all prefixes used in the document, the serialized XML gets `ns0:`,
  `ns1:` prefixes that Word cannot parse. The list of prefixes varies by
  document — check the root element's attributes.
- **`.docm` vs `.docx` content type.** python-docx checks the content type
  in `[Content_Types].xml`, not the file extension. Renaming `.docm` to
  `.docx` does NOT fix the issue.

## Verification

After writing back, always verify by parsing the output and printing the
restructured section:

```python
with zipfile.ZipFile(path) as z:
    with z.open('word/document.xml') as f:
        verify_tree = ET.parse(f)
# Print section headings and content to confirm structure
```

Also open the file in Word/LibreOffice to confirm it renders correctly —
XML validity does not guarantee Word compatibility.
