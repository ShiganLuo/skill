---
name: linux-fontconfig
description: "Fontconfig troubleshooting: tofu, wrong font, CJK."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [fonts, fontconfig, CJK, Chinese, linux, typography, rendering, troubleshooting]
---

# Linux fontconfig: Architecture, Diagnostics & Per-Software Font Resolution

## When to Use

- Chinese/CJK characters display as boxes (tofu)
- Wrong font is being selected for a language or style
- Newly installed fonts are invisible to some programs
- Font rendering quality issues (blurry, strokes merging)
- Need to understand how a specific program (matplotlib, LaTeX, Java, browser) finds fonts
- Configuring font aliases for WPS or other apps expecting Windows font names

## Core Concept

fontconfig is the **single font broker** on Linux. Applications request fonts by generic name + language (e.g. `sans-serif:lang=zh`), and fontconfig returns a concrete file path. The chain:

```
Font files → fc-cache indexes → fontconfig rules → fc-match resolves → FreeType renders
```

## Quick Diagnostics

```bash
fc-list :lang=zh                              # all installed Chinese fonts
fc-match "sans-serif:lang=zh"                 # what sans-serif resolves to
fc-match -s "sans-serif:lang=zh" | head -10   # full fallback chain
fc-query /path/to/font.ttf                    # how fontconfig sees a font file
fc-conflist                                   # all config files + priority
fc-cache -fv                                  # rebuild cache (run after install)
FC_DEBUG=4 fc-match "sans-serif:lang=zh" 2>&1 | head -50  # debug matching
```

## Configuration Hierarchy

```
/etc/fonts/fonts.conf              ← system default, DO NOT edit
/etc/fonts/conf.d/*.conf           ← system rules (sorted by numeric prefix)
/etc/fonts/local.conf              ← system admin custom
~/.config/fontconfig/fonts.conf    ← user custom
~/.config/fontconfig/conf.d/       ← user rules (99-xxx = highest priority)
```

Numeric prefix determines order: 10-xx (rendering defaults) → 30-xx (aliases) → 99-xx (user overrides).

## Per-Software Font Resolution

| Software | Uses fontconfig? | Cache to clear? | Notes |
|----------|-----------------|-----------------|-------|
| GTK/Qt apps | Yes | — | Fully dependent on fontconfig |
| Firefox/Chrome | Yes (discovery) | — | CSS fallback chain is browser-side, but font lookup goes through fontconfig |
| matplotlib | Indirect | `~/.cache/matplotlib/` | Has its own font cache; must delete after installing new fonts |
| reportlab | **No** | — | Must register fonts manually with `pdfmetrics.registerFont(TTFont(...))` |
| PIL/Pillow | **No** | — | Needs explicit font file path in `ImageFont.truetype()` |
| XeLaTeX/LuaLaTeX | Yes | — | Use `\setmainfont{Name}` or `\setCJKmainfont{Name}` |
| pdfLaTeX | **No** | — | Uses .tfm metric files, not fontconfig |
| Java Swing | Yes | — | Uses `fc-match "Dialog"` for default |
| Terminal emulators | Yes (via Pango) | — | Needs monospace font with CJK support |
| WPS Office | Yes + aliases | — | Needs `99-wps-chinese-aliases.conf` for Windows font name mapping |
| Docker/headless | Yes | — | Needs `libfontconfig1` package even if fonts are installed |

## CJK Alias Mapping

When programs request Windows font names, fontconfig aliases redirect to Linux equivalents:

| Requested | Alias → |
|-----------|---------|
| SimSun / 宋体 | Noto Serif CJK SC |
| SimHei / 黑体 | Noto Sans CJK SC |
| Microsoft YaHei / 微软雅黑 | Noto Sans CJK SC |
| FangSong / 仿宋 | AR PL UKai CN |
| KaiTi / 楷体 | AR PL UKai CN / LXGW WenKai |
| LiSu / 隶书 | Noto Serif CJK SC |
| YouYuan / 幼圆 | Noto Sans CJK SC |

Config file: `~/.config/fontconfig/conf.d/99-wps-chinese-aliases.conf`

## Rendering Settings

Default values (set in 10-xx conf files):
- `antialiasing = true`
- `hintstyle = hintslight` — light hinting is best for CJK (heavy hinting merges strokes)
- `sub-pixel = rgb` — LCD sub-pixel layout
- `lcdfilter = lcddefault`

## Pitfalls

- **matplotlib has its own font cache** (`~/.cache/matplotlib/`). Installing new fonts requires deleting this cache separately from `fc-cache`.
- **reportlab and Pillow do NOT use fontconfig**. They need explicit file paths — no amount of `fc-cache` fixes helps.
- **Docker containers need `libfontconfig1`** even if fonts are installed. Without it, fontconfig can't function.
- **`hintfull` breaks CJK** — strokes merge. Always use `hintslight` for Chinese/Japanese/Korean.
- **After installing real Windows fonts, delete the alias config** to avoid conflicts between real fonts and aliases.
- **`fc-cache` "invalid cache" warnings are harmless** — fonts still work correctly.
- **WPS needs a restart** after font changes — it caches fonts at startup.
