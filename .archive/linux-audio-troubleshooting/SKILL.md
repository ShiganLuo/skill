---
name: linux-audio-troubleshooting
description: "Diagnose and fix Linux audio input/output issues — microphone not detected, no sound, ALSA/PipeWire/PulseAudio routing. Covers HDA codec pin analysis, modprobe model overrides, hdajackretask, and common Realtek ALC quirks."
tags: [linux, audio, alsa, pipewire, hda, realtek, microphone, troubleshooting]
---

# Linux Audio Troubleshooting

## Diagnostic Workflow

Run these in order to gather evidence before proposing fixes:

```bash
# 1. List capture hardware
arecord -l

# 2. List PulseAudio/PipeWire sources (should show mic input, not just monitor)
pactl list sources short

# 3. List ALSA cards
cat /proc/asound/cards

# 4. Check ALSA mixer state for the relevant card
amixer -c <N> contents

# 5. Analyze HDA codec pin configuration (the critical step)
cat /proc/asound/card<N>/codec#0 | grep -B2 -A15 "Node 0x"
```

## Key Indicators

- **pactl sources only shows `.monitor`** = no mic input source recognized at all
- **`Mic Jack: off` in amixer** = external mic jack not detected
- **Pin Default `0x411111f0`** = [N/A] disabled pin (generic fallback)
- **Pin Default `0x90xxxxxx`** = [Fixed] internal device (usually working)
- **Pin Default `0x03xxxxxx`** = [Jack] external connector

## Fix Approaches (in order of simplicity)

### 1. modprobe model parameter
```bash
echo "options snd-hda-intel model=<MODEL>" | sudo tee /etc/modprobe.d/alsa-fix.conf
sudo reboot
```

Common ALC274 models to try: `auto`, `alc274-eapd`, `alc274-dmic`, `alc274-sense-combo`
For other Realtek codecs: check kernel docs or try `auto` first.

### 2. hdajackretask (GUI tool)
```bash
sudo apt install linux-sound-base alsa-tools-gui
sudo hdajackretask
```
Select codec → find pin → set Override → "Install boot override" → reboot.

### 3. hda-verb (manual pin config, advanced)
```bash
sudo apt install hda-verb
hda-verb /dev/snd/hwC<D>D0 <NID> <Verb> <Parameter>
```

## Pitfalls

### hdajackretask may not show all pins
The tool only exposes pins with specific ALSA mixer controls. Pins marked `[N/A]` in codec info often do NOT appear in hdajackretask's pin list. Don't assume the pin "doesn't exist" — it may just be invisible to the GUI.

**Workaround:** If hdajackretask doesn't show the pin you need, use modprobe model parameter approach instead.

### Model parameter must match codec
`model=alc274-dmic` only works for ALC274. Other codecs have different model names. Check `/sound/pci/hda/patch_realtek.c` in kernel source for available models per codec.

### Modprobe override is persistent
The fix survives reboots. To undo: `sudo rm /etc/modprobe.d/alsa-fix.conf && sudo reboot`.

### Verification after fix
```bash
# Record 3 seconds and play back
arecord -d 3 -f S16_LE -r 44100 /tmp/test.wav && aplay /tmp/test.wav
```

## Hardware Detection Summary

Use this to identify the codec and card number:
```bash
cat /proc/asound/cards          # card numbers
cat /proc/asound/card<N>/codec#0 | head -5   # codec name
```

### patch= firmware override may silently fail
hdajackretask generates a firmware file (e.g. `/lib/firmware/hda-jack-retask.fw`) and adds a `patch=` line to modprobe.d. However, **the Pin Default in the live codec dump may not change** — it still shows the original value. This means the override is NOT applied at the hardware level, even though the file and modprobe option exist. PipeWire/PulseAudio will not create a capture source.

**Diagnosis:** After setting up the firmware patch, check the live codec:
```bash
cat /proc/asound/card<N>/codec#0 | grep -A5 "Node 0x12"  # or relevant pin
```
If `Pin Default` still shows `0x40000000` or `0x411111f0` instead of the patched value, the firmware override failed.

**Workaround:** Use `model=` parameter instead of `patch=`. The `model=` parameter tells the driver which preset to use and is more reliably applied:
```bash
echo "options snd-hda-intel model=alc274-eapd" | sudo tee /etc/modprobe.d/alsa-fix.conf
sudo reboot
```

## Known Issue: MSI Alpha 17 C7VG (Realtek ALC274)
Internal mic pin (Node 0x12) defaults to `0x40000000` ([N/A] Line Out). Only external mic jack (Pin 0x19, `0x03a19030`) is detected. `pactl list sources` shows only `.monitor`, no mic input source.

**Pin layout (card 2):**
- Node 0x12: Internal Mic — Pin Default `0x40000000` [N/A] ← needs fix
- Node 0x19: External Mic Jack — Pin Default `0x03a19030` [Jack] ← working
- Node 0x17: Speaker — Pin Default `0x90170110` [Fixed] ← working
- Node 0x21: Headphone — Pin Default `0x03214020` [Jack] ← working

**Fix:** `model=alc274-eapd` via modprobe. The hda-jack-retask firmware patch approach does NOT work for this laptop (Pin Default remains unchanged after patch). Write to `/etc/modprobe.d/alsa-fix.conf` or overwrite the existing `hda-jack-retask.conf`:
```bash
echo "options snd-hda-intel model=alc274-eapd" | sudo tee /etc/modprobe.d/alsa-fix.conf
sudo reboot
```
If `alc274-eapd` doesn't work, try `alc274-dmic`, `alc274-sense-combo`, or `auto`.
