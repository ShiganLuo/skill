---
name: linux-font-installation
description: "Install fonts on Linux for WPS/LibreOffice."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [fonts, WPS, Chinese, linux, typography]
---

# Linux Font Installation

Install Microsoft core fonts and Chinese fonts for WPS Office / LibreOffice on Linux, with fontconfig aliases.

## Step 1: Install Microsoft Core Fonts (no sudo needed)

These are EULA-freely redistributable: Arial, Times New Roman, Courier New, Georgia, Verdana, Trebuchet MS, Comic Sans, Impact, Webdings, Andale Mono.

```bash
# cabextract needs libmspack (often missing without sudo)
# Use 7z instead — it's pre-installed on most systems and handles .exe CAB archives

cd /tmp && mkdir -p msfonts && cd msfonts

# Download from SourceForge (official source for ttf-mscorefonts)
for f in andale32.exe arial32.exe arialb32.exe comic32.exe courie32.exe \
         georgi32.exe impact32.exe times32.exe trebuc32.exe verdan32.exe webdin32.exe; do
  curl -sL --max-time 60 -o "$f" "https://downloads.sourceforge.net/corefonts/$f"
done

# Extract TTF files
mkdir -p extracted
for f in *.exe; do
  7z x -oextracted -y "$f"
done

# Install to user fonts directory
mkdir -p ~/.local/share/fonts
cp extracted/*.TTF extracted/*.ttf ~/.local/share/fonts/
```

**Pitfall**: `cabextract` often fails with `libmspack.so.0: cannot open shared object file`. Always use `7z` instead.

## Step 2: Install Chinese Fonts

Microsoft Chinese fonts (SimSun, SimHei, YaHei, FangSong, KaiTi) are NOT freely redistributable — no legal download source.

**Option A: Copy from Windows** (best quality)
```
# From C:\Windows\Fonts\ — copy these to ~/.local/share/fonts/:
simsun.ttc    # 宋体
simhei.ttf    # 黑体
msyh.ttc      # 微软雅黑
simfang.ttf   # 仿宋
simkai.ttf    # 楷体
```

**Option B: Open-source alternatives** (no Windows needed)
```bash
# LXGW WenKai (霞鹜文楷) — excellent open-source Chinese font
curl -sL --max-time 120 -o ~/.local/share/fonts/LXGWWenKai-Regular.ttf \
  "https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf"

# System packages (if sudo available):
# sudo apt install fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk
```

System already has: Noto Sans/Serif CJK SC, WenQuanYi Zen Hei, AR PL UKai CN.

## Step 3: Fontconfig Aliases (make WPS find Chinese fonts by name)

WPS looks for "SimSun", "SimHei", "Microsoft YaHei" etc. by name. If you only have open-source alternatives, create aliases:

```bash
mkdir -p ~/.config/fontconfig/conf.d
```

Write `~/.config/fontconfig/conf.d/99-wps-chinese-aliases.conf`:

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias><family>SimSun</family><prefer><family>Noto Serif CJK SC</family></prefer></alias>
  <alias><family>宋体</family><prefer><family>Noto Serif CJK SC</family></prefer></alias>
  <alias><family>SimHei</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>黑体</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>Microsoft YaHei</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>微软雅黑</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>FangSong</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>仿宋</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>FangSong_GB2312</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>KaiTi</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>楷体</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>KaiTi_GB2312</family><prefer><family>AR PL UKai CN</family></prefer></alias>
  <alias><family>LiSu</family><prefer><family>Noto Serif CJK SC</family></prefer></alias>
  <alias><family>YouYuan</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
</fontconfig>
```

If real .ttf files are installed (Option A), skip aliases — delete the config file.

## Step 4: Refresh Cache

```bash
fc-cache -fv ~/.local/share/fonts/
```

**Verify aliases**:
```bash
fc-match "SimSun"          # → Noto Serif CJK SC (alias) or SimSun (real font)
fc-match "SimHei"          # → Noto Sans CJK SC
fc-match "Microsoft YaHei" # → Noto Sans CJK SC
fc-match "Arial"           # → Arial (MS core font installed)
fc-match "Times New Roman" # → Times New Roman
```

## Pitfalls

- `cabextract` needs `libmspack.so.0` — use `7z` instead (pre-installed on Ubuntu)
- SourceForge downloads can be slow/timeout in China — no reliable mirror known
- GitHub releases (LXGW fonts) also slow in China — try `ghproxy.com` mirror or `git clone` via SSH
- Aliases are NOT perfect substitutes — real fonts from Windows produce better rendering
- After installing real fonts, delete the alias config to avoid conflicts
- `fc-cache` invalid cache warnings are harmless — fonts still work
- WPS restart required for font changes to take effect
