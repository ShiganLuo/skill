---
name: wps-jsapi-addin-patching
description: Patch WPS JSAPI add-ins via .dotm internals.
metadata:
  hermes:
    tags: [wps, jsapi, dotm, addin, patching]
version: 1.0.0
author: Hermes Agent (autonomous review)
license: MIT
---

## When to Use

Use when a WPS JSAPI add-in (`Zotero-Jsa`, `Obsidian-for-wps`, etc.) installed under `~/.local/share/Kingsoft/wps/jsaddons/` misbehaves and you need to alter or disable a specific JS code path inside its `.dotm` template. **Confirm the user owns the add-in or has authorized patching before touching it.**

Trigger phrases:
- "Zotero/JSA/WPS 加载项 xxx 不对劲，帮我改一下"
- "WPS 这个插件的行为我想改"
- Any task that ends with modifying `JDEData.bin` inside a `.dotm`

# WPS JSAPI Add-in Patching

WPS Linux/macOS add-ins ship as a directory of files plus a `.dotm` template (`Zotero-Jsa.dotm`, `Obsidian-for-wps.dotm`, etc.). The `.dotm` is a ZIP archive whose `word/JDEData.bin` is an XML document with the add-in's JS payload HTML-entity-encoded inside `<codetext>` blocks.

When the add-in misbehaves (e.g. Zotero refresh overwrites your `Bibliography Entry` style), patching the `.dotm` is faster than waiting for an upstream fix and works for any WPS add-in using this format.

## When this skill applies

- An add-in installed under `~/.local/share/Kingsoft/wps/jsaddons/<name>_<version>/` is misbehaving
- You need to disable, neutralize, or modify a JS function inside `JDEData.bin`
- The user has authorized modifying the add-in (these are usually NOT user-owned; confirm before patching)

## Step 1: Inventory and back up

```bash
ADDIN_DIR=~/.local/share/Kingsoft/wps/jsaddons/Zotero-Jsa_1.0.0
DOTM="$ADDIN_DIR/Zotero-Jsa.dotm"
BACKUP_DIR=~/Backups/$(basename "$ADDIN_DIR")-$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"
cp "$DOTM" "$BACKUP_DIR/Zotero-Jsa.dotm.orig"
```

**Always snapshot before every modification.** Use timestamps in backup dir names (e.g. `-v2`, `-v3`) so iteration is reversible.

## Step 2: Unpack the .dotm

`.dotm` is a regular ZIP. Unpack to a working dir:

```bash
WORK=/tmp/wps_patch
rm -rf "$WORK" && mkdir -p "$WORK"
cp "$DOTM" "$WORK/orig.dotm"
unzip -o -q "$WORK/orig.dotm" -d "$WORK/unpacked"
ls "$WORK/unpacked/word/"
```

Key file: `word/JDEData.bin`. It is **not binary** despite the extension — it is an XML document.

## Step 3: Decode JDEData.bin

```bash
python3 << 'PYEOF'
with open("$WORK/unpacked/word/JDEData.bin", encoding="utf-8") as f:
    raw = f.read()

# Extract every <codetext>...</codetext> block (HTML-entity-encoded JS)
import re, html
codetexts = re.findall(r'<codetext>(.*?)</codetext>', raw, re.DOTALL)
print(f"Found {len(codetexts)} <codetext> blocks")
for i, c in enumerate(codetexts):
    decoded = html.unescape(c)
    print(f"  [{i}] encoded={len(c)} decoded={len(decoded)}")

combined = "\n".join(html.unescape(c) for c in codetexts)
# Now search the combined JS for target functions/markers
PYEOF
```

A WPS add-in's JDEData.bin can contain multiple `<codetext>` blocks (often 2-4). The actual code is split between them. **Always concatenate all blocks before searching for the function you want to patch.**

## Step 4: Locate the target function

Use grep on the raw XML to find the byte range, then work in raw form (HTML-entity-encoded) to avoid corrupting the encoding:

```bash
python3 << 'PYEOF'
with open("$WORK/unpacked/word/JDEData.bin", encoding="utf-8") as f:
    raw = f.read()

# Example: find async function zc_setBibStyle(bibStyle)
start_marker = 'async function zc_setBibStyle'
idx_start = raw.find(start_marker)
print(f"function start at offset {idx_start}")

# Find end by searching for known end-of-function marker
end_pattern = 'return false;&#x0A;    }&#x0A;}&#x0A;'   # HTML-entity-encoded
idx_end = raw.find(end_pattern, idx_start)
end_pos = idx_end + len(end_pattern)
print(f"function ends at offset {end_pos}")
old_func = raw[idx_start:end_pos]
PYEOF
```

**Pitfall — greedy regex across nested braces**: don't use `re.DOTALL` with `.*?\n}` to find function endings. Strings inside the JS often contain `}` (e.g. `'Missing bibliography formatting style, please restart Zotero and click update'`). Instead, **anchor on a unique end-marker pattern** like the last `return false; }` line.

## Step 5: Patch the raw XML

To replace a function body, define the new JS, then HTML-entity-encode it the same way:

```python
def js_to_entities(s):
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;')
             .replace("'", '&apos;')
             .replace('\n', '&#x0A;')
             .replace('\t', '&#x09;'))

new_func = '''async function zc_setBibStyle(bibStyle){
    // DISABLED: leave style untouched
    return true;
}'''
new_func_encoded = js_to_entities(new_func)
new_raw = raw[:idx_start] + new_func_encoded + raw[end_pos:]
```

For surgical string replacements inside a function (e.g. neutralize a single assignment), work directly on the raw bytes:

```python
old = b"ftl.Style = geBibsy;&#x0A;"
new = b"if (ftl.Style.NameLocal !== styleName) ftl.Style = geBibsy;&#x0A;"
assert data.count(old) == 1, f"expected 1 match, found {data.count(old)}"
data = data.replace(old, new)
```

**Always assert count is 1** (or whatever you expect). If the count is 0 the marker has drifted; if it's >1 you've hit a substring overlap. Either way, **stop and re-grep** rather than proceeding blindly.

## Step 6: Rezip

```bash
cd "$WORK/unpacked"
rm -f "$WORK/patched.dotm"
zip -r -q -X "$WORK/patched.dotm" .
```

The `-X` flag strips extra Unix attributes that the original ZIP may not have had — keeps the archive as close to WPS expectations as possible.

Verify the zip is intact:

```bash
unzip -t "$WORK/patched.dotm" | tail -3
```

## Step 7: Deploy and verify

```bash
cp "$WORK/patched.dotm" "$DOTM"
echo "MD5 compare:"
md5sum "$BACKUP_DIR/Zotero-Jsa.dotm.orig" "$DOTM"
```

Then **re-read JDEData.bin from the deployed file** (not the unpacked work copy) to confirm the patch landed:

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('$DOTM') as z:
    with z.open('word/JDEData.bin') as f:
        d = f.read().decode('utf-8')
print('has marker?', 'my_marker' in d)
"
```

The add-in is loaded once when WPS starts. **Restart WPS for changes to take effect.**

## Pitfalls

- **JDEData.bin looks binary but is text**. `file` reports it as "XML document". Don't try to `strings | grep` and assume you're seeing the full payload — `<codetext>` is HTML-entity-encoded so `&#x0A;` not `\n`. Use the Python decoding step.
- **Multiple `<codetext>` blocks**. A function may live in block 2, but variables/imports in block 0. Search the concatenation.
- **`.~` lockfile exists**. When WPS has the add-in loaded, you may see `.~Zotero-Jsa.dotm`. WPS locks the file while running; close WPS before `cp`-ing in your patched version.
- **Adding new code that uses unfamiliar APIs**. WPS JSAPI exposes a subset of Word VBA. Properties like `Style.NameLocal` may exist in Word but throw in WPS, falling through `try/catch` and silently bypassing your `if` guard. Always test the patched add-in by triggering the code path (open doc, refresh, observe).
- **First patch can target the wrong code path**. In the Zotero-Bibliography-Entry case, the obvious target (`ftl.Style = geBibsy`) wasn't the actual culprit — the real interference was `zc_setBibStyle` rewriting the *style definition* (`paraFormat.FirstLineIndent` etc.) itself. When the user's first report says "X is being overwritten on refresh", trace the entire refresh code path before patching — there may be multiple write sites.
- **Loading each codetext block separately loses cross-block references**. Some add-ins split a single class across blocks. If a patch produces a syntax error, check that you didn't accidentally re-encode a block that was already plain.