---
name: linux-hardware-troubleshooting
description: "Diagnose and fix Linux hardware issues — audio (ALSA/PipeWire/PulseAudio, HDA codec pins, modprobe model overrides), WiFi (regulatory domains, ath12k/ath11k/iwlwifi driver quirks, self-managed firmware), GPU/X server (hybrid GPU config conflicts, Xorg fatal errors, kwin crashes, NVIDIA driver interactions). Covers diagnostic workflows, modprobe parameter fixes, firmware quirks, and hardware-specific workarounds. Trigger: user reports audio, WiFi, or system freeze/hang symptoms on Linux."
tags: [linux, hardware, audio, wifi, gpu, xorg, nvidia, hybrid-gpu, alsa, pipewire, ath12k, modprobe, hda, troubleshooting]
related_skills: []
---

# Linux Hardware Troubleshooting

Umbrella skill for diagnosing and fixing hardware issues on Linux — currently covers audio, WiFi, and GPU/X server subsystems. All share the same diagnostic philosophy and many fix patterns.

## Shared Diagnostic Philosophy

1. **Run diagnostics first, propose fixes second.** Never guess — gather evidence.
2. **Finish the diagnosis before presenting options.** When the user asks "why did X happen", complete the root-cause investigation end-to-end before asking the user to choose a fix. Asking "which fix do you want?" mid-diagnosis is a workflow failure — the user explicitly called this out. Push through to the actual cause first, then present options if there are multiple.
3. **Never disconnect the user's active connection** during debugging (WiFi, audio input).
4. **modprobe parameters are read at module load time** — changes require reboot. Warn the user.
5. **Module unloading often fails** with "Device or resource busy" on modern hardware. Plan for reboot.
6. **Hardware-specific quirks are common** — the same laptop model may need different fixes for different subsystems.
7. **Time-correlation claims need evidence.** When something "happened at T0" and the user reports a problem "now at T1", verify the actual crash/freeze time in crash files (`stat -c '%y' /var/crash/*`) and journalctl timestamps. Don't assume the user's "now" matches the latest crash — they may be remembering a recent one while the current session is fine.

## Common Fix Pattern: modprobe Parameters

Both audio and WiFi issues are frequently fixed via modprobe configuration:

```bash
# Set parameter (survives reboot)
echo "options <module> <param>=<value>" | sudo tee /etc/modprobe.d/<name>.conf

# Undo
sudo rm /etc/modprobe.d/<name>.conf
sudo reboot
```

**Pitfall:** Parameters are read-only at module load time. No runtime workaround exists — reboot is mandatory.

## Common Pitfall: Module Unloading

Some drivers depend on modules that cannot be unloaded (e.g., `qcom_scm` for Qualcomm WiFi). `modprobe -r <driver>` will fail with "Device or resource busy". Don't attempt module unloading unless the user agrees to reboot.

## Common Technique: bash_history Mining

When system logs (journal, dmesg) don't reveal when or why a config was created or a command was run, `~/.bash_history` is often the next source of truth. Many users enable shell history logging without timestamps, but the line order + relative position to other commands is usually enough to reconstruct a sequence.

```bash
# Find config-touching commands
grep -niE "nvidia|prime|hybrid|gpu|xorg|sddm|prime-select|gpu-manager|blacklist" ~/.bash_history

# Reconstruct sequence with line numbers
grep -n "<command>" ~/.bash_history
```

**Pitfall:** bash_history does not record `sudo` commands separately — the original command appears in user history, but the actual file modification timestamp belongs to root. Cross-reference bash_history with `stat <file>` to pin down "when this exact config was written".

**Use case:** User reports a problem but you need to know what manual configuration they did in the past. Especially valuable for hybrid GPU / X server problems where `/etc/X11/xorg.conf.d/*.conf` files exist without any package owning them (`dpkg -S <file>` returns "no path found").

## Subsystem Details

- **Audio issues** → see `references/audio-troubleshooting.md`
- **WiFi issues** → see `references/wifi-troubleshooting.md`
- **GPU / X server freeze or failure** → see `references/gpu-xorg-troubleshooting.md`

Each reference contains the full diagnostic workflow, fix approaches, pitfalls, and known hardware issues for that subsystem.

## Quick Decision Tree

```
Hardware problem on Linux?
│
├── Audio: no sound / no mic / wrong routing
│   └── references/audio-troubleshooting.md
│       → arecord -l, pactl sources, amixer, HDA codec pins
│       → Fix: modprobe model= or hdajackretask
│
├── WiFi: can't see networks / 5GHz missing / won't connect
│   └── references/wifi-troubleshooting.md
│       → iw reg get, nmcli, dmesg, lspci
│       → Fix: cfg80211 ieee80211_regdom or firmware update
│
├── System freeze / hang / "mouse won't move" / black screen after reboot
│   └── references/gpu-xorg-troubleshooting.md
│       → /var/crash/* mtimes, Xorg.0.log*, journalctl kwin/plasma/GL reset,
│         /etc/X11/xorg.conf.d/* ownership (dpkg -S), bash_history mining,
│         /dev/dri/card* enumeration
│       → Fix: remove manual Xorg configs conflicting with gpu-manager
│       → Verification: smoke test (boot + login + Xorg no errors)
│
└── Other hardware → new subsystem to add to this umbrella
```

## Adding New Subsystems

When a new hardware troubleshooting topic is identified, add it as a new section in this SKILL.md and create `references/<subsystem>-troubleshooting.md` with the full diagnostic workflow. Keep the umbrella SKILL.md as the entry point with the shared philosophy and decision tree.
