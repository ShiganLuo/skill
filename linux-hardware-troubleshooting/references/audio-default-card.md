# Setting the Default ALSA Sound Card

When multiple sound cards exist (e.g. NVidia HDMI + Realtek onboard), `alsamixer` defaults to card 0. If card 0 has no capture controls, the user sees "no capture devices" even though another card has working mic input.

## Diagnostic

```bash
# List all cards and their numbers
cat /proc/asound/cards

# Check which card has capture controls
amixer -c <N> contents | grep -i capture

# List capture hardware devices
arecord -l
```

## Fix: ~/.asoundrc

Create `~/.asoundrc` (user-level, no sudo):

```
defaults.pcm.card 2
defaults.pcm.device 0
defaults.ctl.card 2
```

- `defaults.pcm.card` — default playback/capture card
- `defaults.pcm.device` — default device number (usually 0)
- `defaults.ctl.card` — default mixer control card (what alsamixer shows)

After this, `alsamixer` without `-c` flag opens the specified card.

**Pitfall on PipeWire systems:** `~/.asoundrc` can confuse PipeWire's device enumeration. After adding it, PipeWire may fail to create the input source. If `pactl list sources short` drops the mic source after adding `.asoundrc`, remove it and use WirePlumber profile config instead (see below).

## PipeWire/WirePlumber Default Source

PipeWire uses WirePlumber for node routing. Setting the default source via `pactl` may not persist or may show unexpected results.

### Check actual defaults

```bash
wpctl status
# Look at "Settings > Default Configured Node Names"
# Also shows which sink/source is active (*)
```

### Set default source (temporary)

```bash
pactl set-default-source <name-or-index>
```

**Pitfall:** `pactl get-default-source` may show a `.monitor` source (e.g. bluetooth sink monitor) even when WirePlumber has the correct source configured. Check `wpctl status` for ground truth.

### Set default source (persistent across reboots)

Use `wpctl set-default <id>` — this persists in WirePlumber's state.

Or create `~/.config/wireplumber/wireplumber.conf.d/50-defaults.conf`:

```ini
monitor.alsa.rules = [
  {
    matches = [
      { node.name = "alsa_input.*" }
    ]
    actions = {
      update-props = {
        node.name = "alsa_input.pci-0000_05_00.6.analog-stereo"
        priority.driver = 1000
      }
    }
  }
]
```

### Verify

```bash
wpctl status                              # Check Settings section
pactl list sources short                  # Should show desired source
amixer                                    # Should show correct card's mixer
```

## WirePlumber Profile Selection (Source Missing Entirely)

**Symptom:** `wpctl status` Sources section is empty for the card, even though `arecord -l` shows capture hardware and `amixer -c <N>` shows capture controls.

**Root cause:** WirePlumber auto-selects `output:analog-stereo` (output-only) profile instead of `output:analog-stereo+input:analog-stereo` (duplex). This happens when:
- Jack detection reports the mic port as "not available" (common for internal DMICs that have no jack)
- `api.acp.auto-profile` is `false`

**Diagnosis:**
```bash
pactl list cards | grep -A 30 "<card-name>"
# Look for:
#   Active Profile: output:analog-stereo     ← THIS IS THE PROBLEM
#   Should be:      output:analog-stereo+input:analog-stereo
#
# Also check:
#   analog-input-mic: ... availability: not available  ← jack detection says no mic
```

**Fix:** Create a WirePlumber lua rule to force duplex profile:

```bash
mkdir -p ~/.config/wireplumber/main.lua.d
```

Create `~/.config/wireplumber/main.lua.d/51-<cardname>-duplex.lua`:

```lua
-- Force card to use duplex profile (mic + speaker)
rule = {
  matches = {
    {
      { "device.name", "equals", "alsa_card.pci-0000_05_00.6" },
    },
  },
  apply_properties = {
    ["device.profile"] = "output:analog-stereo+input:analog-stereo",
  },
}

table.insert(alsa_monitor.rules, rule)
```

Then restart PipeWire:
```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

**Verify:**
```bash
pactl list cards | grep "Active Profile"
# Should show: Active Profile: output:analog-stereo+input:analog-stereo

pactl list sources short
# Should show alsa_input.* source

wpctl status | grep -A 5 "Sources:"
# Should list the card's source
```

**Finding the device.name:** Run `pactl list cards` and look for `device.name = "alsa_card.pci-..."` under the target card.

**Pitfall:** `pactl set-card-profile` can switch profile at runtime but does NOT persist across WirePlumber restarts. The lua config file is required for persistence.

## Multi-card Setup Common Pattern

Typical Linux laptop with HDMI audio + onboard codec:

| Card | Name | Typical Use |
|------|------|-------------|
| 0 | HDA NVidia / HDA ATI HDMI | HDMI/DisplayPort audio output only |
| 1 | HD-Audio Generic | Secondary codec (sometimes second Realtek) |
| 2 | HD-Audio Generic | Main onboard codec (speakers + mic) |

If the user says "alsamixer shows no capture devices" — they're probably looking at the HDMI card. Check `cat /proc/asound/cards` first.
