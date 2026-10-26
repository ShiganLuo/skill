# HTML → PDF Export via Chrome DevTools Protocol

Use when the deliverable is a polished printable artifact (resume, certificate,
report cover, design system preview). Self-contained HTML+CSS rendered to
PDF through headless Chrome gives print-grade typography without paying
for wkhtmltopdf or LaTeX.

This is the **rendering** half of an HTML artifact — pair it with
`html-design` or `claude-design` for the authoring half.

## Setup

```bash
google-chrome --headless=new \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-pdf \
  --no-sandbox \
  --disable-gpu \
  --no-first-run \
  --no-default-browser-check \
  --remote-allow-origins=* \
  about:blank
```

The `--remote-allow-origins=*` is **required** on Chrome 111+: without
it, any CDP WebSocket connection from the local script is rejected
with `Handshake status 403 Forbidden`.

## CDP Print-to-PDF call

```python
import json, websocket, base64, time, sys

WS_URL = sys.argv[1]   # ws:// — fetch via PUT to /json/new
HTML  = sys.argv[2]
PDF   = sys.argv[3]

ws = websocket.create_connection(WS_URL, timeout=30)

def cdp(method, params=None):
    msg = {"id": 1, "method": method}
    if params: msg["params"] = params
    ws.send(json.dumps(msg))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == 1: return r

cdp("Page.enable")
cdp("Page.navigate", {"url": f"file://{HTML}"})
time.sleep(2)  # Let fonts and images load

result = cdp("Page.printToPDF", {
    "landscape": False,
    "displayHeaderFooter": False,
    "printBackground": True,             # Print CSS background colors/images
    "paperWidth":  8.27,                 # A4 width  (inches)
    "paperHeight": 11.69,                # A4 height (inches)
    "marginTop":    0,
    "marginBottom": 0,
    "marginLeft":   0,
    "marginRight":  0,
    "preferCSSPageSize": True,            # Honor @page CSS rules
})

pdf_bytes = base64.b64decode(result["result"]["data"])
with open(PDF, "wb") as f: f.write(pdf_bytes)
ws.close()
```

To get a working `ws://` URL, do:

```bash
curl -s -X PUT "http://localhost:9222/json/new" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['webSocketDebuggerUrl'])"
```

## CSS Recipe for A4 One-Pager

The most common use case is a single-page resume or CV that **must
fit on one A4** without overflow. Use this pattern:

```css
@page { size: A4; margin: 0; }

body {
  font-family: "Noto Sans CJK SC", "PingFang SC", sans-serif;
  font-size: 9pt;             /* Start here — adjust ±1pt */
  line-height: 1.4;
  width: 210mm;                /* A4 width minus page margins handled in @page */
  margin: 0 auto;
  padding: 10mm 13mm;          /* Inner padding simulates margins */
  overflow: hidden;            /* Prevent page break to a 2nd page */
  box-sizing: border-box;
}
```

### Compress-to-one-page workflow

Users will often ask "fit this on one page". The script does NOT know
how much content will fit. Iterative compression:

1. Start at `font-size: 10pt`, `line-height: 1.5`, `padding: 12mm 15mm`
2. Render → check page count via `pdfinfo file.pdf | grep Pages`
3. If 2 pages: drop font-size by 0.5pt, line-height by 0.05, padding by 1-2mm
4. Repeat until 1 page

Keep a log of each iteration's parameters — the user will want to revert
to a 2-page version with larger font if the 1-page version is too cramped.

### Pitfalls

- **`overflow: hidden` on body can clip content vertically** if the
  computed height exceeds A4 height. Acceptable trade-off for one-pagers
  (better to clip than to overflow to 2 pages), but always check the
  rendered output.
- **`preferCSSPageSize: True`** lets your CSS `@page` rule win. Without
  it, the CDP `paperWidth`/`paperHeight` params take precedence — which
  can be confusing when you set both and they disagree.
- **CJK fonts on headless Chrome**: font fallback can break if Noto Sans
  CJK is missing. Install it: `apt install fonts-noto-cjk`. Verify with
  `fc-list | grep -i noto`.
- **`chrome --headless=new`** is the modern syntax. `--headless` (old)
  still works but lacks CDP `Page.printToPDF` features like
  `displayHeaderFooter` and proper CSS page sizing.
- **Background colors require `printBackground: True`** in CDP. The
  default is to print no backgrounds — useful for ink-saving, but a trap
  if you designed colored sections.
- **Tab text alignment inside `<table>` won't render correctly** if the
  table has `border-collapse: collapse` and you mix percent + fixed
  widths. Always preview.
- **Don't use `&nbsp;` for spacing.** Real resumes look better with
  CSS `margin`/`padding` than with hardcoded non-breaking spaces.

## Two-Language Resume Pattern

Common when applying to jobs in China and abroad: produce a Chinese PDF
and English PDF from parallel HTML files that share the same CSS class
names but different body content. To stay consistent:

- Keep file names parallel: `罗时敢_简历.html` / `Shigan_Luo_Resume.html`
- Keep CSS file identical (or use CSS variables for `lang` attribute)
- Same script, two invocations
- For the English version: keep `lang="en"` on `<html>`, drop Chinese-only
  font stacks from `font-family`

## Bulk Generation

For generating multiple PDFs (e.g. one per sample in a batch run), use
a Python loop:

```python
for name, html_path, pdf_path in jobs:
    tab_ws = create_tab(port)
    process_pdf(tab_ws, html_path, pdf_path)
```

Don't try to share one tab across PDFs — `Page.printToPDF` is async and
sharing risks overlap. New tab per PDF is the safe pattern.

## When NOT to use this

- **Print-quality booklets with headers/footers**: use `weasyprint` or
  Chromium with `displayHeaderFooter: True` plus header/footer templates.
  This skill covers single-shot artifact generation, not multi-page
  documents with running headers.
- **Tables of contents / bookmarks**: Chrome CDP `printToPDF` does
  not produce PDF outline bookmarks. Use LibreOffice headless or
  `weasyprint` for that.
- **Editable PDF**: Chromium produces flattened PDFs. For editable
  PDFs, use `pdf-lib` in Node or LibreOffice with `convert-to` mode.

## Related

- `creative/html-design` — design vocabulary and process
- `creative/claude-design` — design taste and variants
- `data-science/bioinformatics/SKILL.md` Section I — also uses
  Chrome-CDP for screenshot/visual debugging