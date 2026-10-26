---
name: linux-input-methods
description: Use when Chinese IME input fails on Linux desktops.
---

# Linux Input Method (IME) Troubleshooting

Scope: 中文输入法 on Linux desktops (Ubuntu/GNOME focus, fcitx4/fcitx5/ibus), including browser/app-specific input failures.

## User preference (apply to every run)

- User communicates in Chinese; reply in Chinese.
- Confirm the root cause with evidence (dpkg/apt logs, process env, session type) BEFORE proposing fixes. Explain what each command does and why — do not just paste commands.
- User runs `sudo` commands in their own terminal; give paste-ready commands with expected side effects called out explicitly.

## Diagnosis first (gather state before touching anything)

```bash
# Which framework is installed, running, selected?
dpkg -l | grep -E 'fcitx|ibus'        # status codes matter: iU = unpacked-not-configured,
                                       # rc = removed-with-config, un = never installed
pgrep -a 'fcitx|ibus'                 # what is actually running (only ONE framework should run)
im-config -m                          # available IM methods (only lists INSTALLED ones)
cat ~/.xinputrc                       # which IM im-config will start at login

# Session type + environment (two places, check BOTH)
loginctl show-session <id> -p Type    # wayland vs x11
echo "GTK_IM_MODULE=$GTK_IM_MODULE QT_IM_MODULE=$QT_IM_MODULE XMODIFIERS=$XMODIFIERS"
grep -E 'IM_MODULE|XMODIFIERS' /etc/environment
systemctl --user show-environment | grep -E 'IM_MODULE|XMODIFIERS'   # systemd --user may differ

# App-specific: is the app native Wayland or XWayland?
ls -l /proc/<PID>/fd | grep wayland    # wayland socket fd → native Wayland backend
```

Two input paths exist and behave differently:
1. **Toolkit IM module path** (`GTK_IM_MODULE=fcitx` / `QT_IM_MODULE=fcitx`): app talks DIRECTLY to fcitx5 over D-Bus. Works regardless of Wayland/X11. This is why GNOME Settings can type Chinese while Chrome cannot.
2. **Wayland text-input path** (native Wayland apps): app → compositor (`zwp_text_input-v3`) → routed to IM framework. Depends on compositor support and app flags (see Chromium section).

## Hard facts (verified)

- **fcitx4 and fcitx5 are mutually exclusive at PACKAGE level**: `fcitx5` declares `Conflicts: fcitx (<< 1:5)` and `fcitx` declares `Conflicts: fcitx5`. Installing one with `apt install -y ...` silently REMOVES the other — and anything depending on it (e.g. sogoupinyin). ALWAYS read the `Remove:` line of apt's plan before confirming.
- **Sogou Pinyin for Linux (4.x) is fcitx4-only**: deps are `fcitx, fcitx-frontend-gtk2/gtk3/qt5, fcitx-module-x11`. It cannot work under fcitx5. There is no fcitx5-compatible Sogou deb.
- `dpkg -i <deb>` never installs dependencies; on missing deps it leaves the package in state `iU` (unpacked, unconfigured). Fix via `apt install <deps> <package>` or `apt --fix-broken install`, not repeated dpkg.
- `apt autoremove` after removing a package purges its auto-installed deps — removing sogou wipes the fcitx4 library stack this way.
- `im-config -n <name>` only accepts IMs whose packages are currently installed; running it for fcitx before fcitx4 is installed fails/returns "invalid" and leaves `~/.xinputrc` unchanged.
- Only one framework may RUN at a time (they contend for the same input channel/D-Bus). Switching: `pkill fcitx5; fcitx -d`.
- After fcitx4+sogou are installed, never run `apt install fcitx5` again — it will rip sogou out (see Conflicts above).

## Chromium/Electron under Wayland: IME works in GTK apps but not the browser

Status: root cause sourced from ArchWiki fcitx5 page + Chromium docs; the flag fix was DIAGNOSED but NOT yet verified end-to-end (user had not tested at session end). Try in order, verify by actually typing Chinese.

1. **Fix A (native Wayland, preferred)**:
   ```
   google-chrome-stable --enable-wayland-ime --wayland-text-input-version=3
   ```
   Why: Chromium defaults to `zwp_text-input-v1` while GNOME implements only v3 (protocol mismatch → no IME channel), and Chromium's Wayland IME support is off unless `--enable-wayland-ime`.
2. **Fallback B (XWayland)**: `google-chrome-stable --ozone-platform=x11` — forces the X11 backend so Chrome uses the same `GTK_IM_MODULE=fcitx` direct path that already works for GNOME apps. Reliable, older path.
3. **Never mix A and B flags** (wayland-ime flags are meaningless/harmful under `--ozone-platform=x11`).
4. Persist a working flag: copy `/usr/share/applications/google-chrome.desktop` → `~/.local/share/applications/` and append flags to every `Exec=` line (user copy overrides system file).
5. Verify: check running process cmdline / `chrome://version` "Command Line", then have the user type Chinese in a page (agent cannot verify typing itself).

Related known caveat (ArchWiki, untested here): GNOME does not implement Wayland's `input-method-v2`, so fcitx5's Wayland frontend cannot show its popup on GNOME — candidate-window issues may need the kimpanel GNOME extension. On KDE Wayland, fcitx5 must be selected as the Virtual Keyboard in System Settings (launched by KWin).

## Session transcript / full command history

See `references/ubuntu2604-sogou-fcitx-conflict.md` for the verified end-to-end case: error output, apt/dpkg log forensics, and the exact conflict sequence.
