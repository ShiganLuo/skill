---
name: docx-xml-string-edit
description: "Use when a .docx paragraph edit must keep REF fields intact."
---

# Docx XML String Edit (field-preserving)

Targeted sentence replacement inside a .docx without a full
parse-serialize round-trip, so that field codes (figure cross-references
like `REF _Ref...` with `w:fldChar` begin/separate/end runs) survive
untouched.

## When to use

- Rewriting one sentence/paragraph of a thesis body that contains a
  cross-reference field (e.g. "（如图 6）" where 图 6 is a REF field).
- python-docx is unavailable in the analysis env (stdlib-only is fine).
- NOT for restructuring many paragraphs — that needs full XML editing
  (see docx-xml-direct-editing).

## Procedure

1. Backup: `cp file.docx file.docx.bak_<desc>`.
2. Read raw XML and locate the target text:

```python
import zipfile
xml = zipfile.ZipFile('1.docx').read('word/document.xml').decode('utf-8')
i = xml.find('目标句片段')
print(xml[i-200:i+900])   # inspect run boundaries & fields around it
```

3. Replace as a plain string op on the raw XML. Rules:
   - assert `xml.count(old) == 1` before replacing;
   - include a few characters of surrounding context in `old` so the
     replacement cannot straddle a run boundary;
   - keep characters abutting a field (e.g. the '（如' before a 图 N
     reference) in BOTH old and new strings;
   - verify the target text sits inside ONE `<w:t>` run (a sentence split
     across runs must be replaced run by run, or use full XML editing).

```python
old = '原句……（如'
new = '改写句……（如'
assert xml.count(old) == 1
xml = xml.replace(old, new)
```

4. Rewrite the zip preserving every other entry and ZipInfo metadata:

```python
import os
with zipfile.ZipFile('out.docx', 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/document.xml':
            data = xml.encode('utf-8')
        zout.writestr(item, data)
os.replace('out.docx', src)
```

5. Verify: re-parse with ElementTree, extract paragraph text, confirm the
   new sentence is present, the old is gone, and the field runs
   (fldChar/instrText) are intact around it.

## Pitfalls

- A paragraph may look continuous in text view but be split across many
  `<w:t>` runs (spell-check boundaries, CJK/latin font switches). Always
  inspect the raw XML around the match before choosing `old`.
- Do not parse -> ET.tostring -> write unless you register every namespace
  the document uses; string replacement avoids that whole class of failure.
- Analysis envs may lack python-docx (import error is expected); the
  zipfile+stdlib path needs no install.
