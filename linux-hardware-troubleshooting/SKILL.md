---
name: linux-hardware-troubleshooting
description: "Diagnose and fix Linux hardware issues — audio (ALSA/PipeWire/PulseAudio, HDA codec pins, modprobe model overrides), WiFi (regulatory domains, ath12k/ath11k/iwlwifi driver quirks, self-managed firmware). Covers diagnostic workflows, modprobe parameter fixes, firmware quirks, and hardware-specific workarounds. Trigger: user reports audio or WiFi problems on Linux."
tags: [linux, hardware, audio, wifi, alsa, pipewire, ath12k, modprobe, hda, troubleshooting]
related_skills: []
---

# Linux Hardware Troubleshooting

Umbrella skill for diagnosing and fixing hardware issues on Linux — currently covers audio and WiFi subsystems. Both share the same diagnostic philosophy and many fix patterns.

## Shared Diagnostic Philosophy

1. **Run diagnostics first, propose fixes second.** Never guess — gather evidence.
2. **Never disconnect the user's active connection** during debugging (WiFi, audio input).
3. **modprobe parameters are read at module load time** — changes require reboot. Warn the user.
4. **Module unloading often fails** with "Device or resource busy" on modern hardware. Plan for reboot.
5. **Hardware-specific quirks are common** — the same laptop model may need different fixes for different subsystems.

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

## Subsystem Details

- **Audio issues** → see `references/audio-troubleshooting.md`
- **WiFi issues** → see `references/wifi-troubleshooting.md`

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
└── Other hardware → new subsystem to add to this umbrella
```

## Adding New Subsystems

When a new hardware troubleshooting topic is identified, add it as a new section in this SKILL.md and create `references/<subsystem>-troubleshooting.md` with the full diagnostic workflow. Keep the umbrella SKILL.md as the entry point with the shared philosophy and decision tree.
