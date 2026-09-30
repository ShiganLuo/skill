# Bluetooth Microphone Setup on PipeWire

When the built-in microphone doesn't work (hardware/driver issue), a bluetooth headset with mic is the practical workaround. Bluetooth audio uses a completely different path (BT controller → BlueZ → PipeWire) that bypasses HDA driver issues entirely.

## How Bluetooth Audio Profiles Work

| Profile | Direction | Quality | Mic? |
|---------|-----------|---------|------|
| `a2dp-sink` | BT → PC (playback only) | High (SBC/AAC/LDAC, stereo 48kHz) | ❌ |
| `a2dp-sink-sbc_xq` | BT → PC (playback only) | Higher (SBC-XQ) | ❌ |
| `headset-head-unit` | BT ↔ PC (bidirectional) | Phone (8kHz mono) | ✅ |
| `headset-head-unit-cvsd` | BT ↔ PC (bidirectional) | Phone (8kHz mono, CVSD codec) | ✅ |
| `headset-head-unit-msbc` | BT ↔ PC (bidirectional) | Wideband (16kHz mono, mSBC codec) | ✅ |

**Key insight:** A2DP is high-quality playback-only. HFP/HSP profiles add microphone but at reduced audio quality. This is a Bluetooth protocol limitation, not a device limitation.

## Diagnostic

```bash
# Check bluetooth device connection
bluetoothctl info <MAC>

# List available profiles
pactl list cards | grep -A 60 "bluez_card"

# Check current active profile
pactl list cards | grep "Active Profile"

# List audio sources (should show bluetooth input when HFP active)
pactl list sources short

# Check WirePlumber view
wpctl status
```

## Manual Profile Switch (Temporary)

```bash
# Switch to HFP profile with microphone
pactl set-card-profile bluez_card.<MAC> headset-head-unit

# Or for better quality (if supported)
pactl set-card-profile bluez_card.<MAC> headset-head-unit-msbc

# Set as default source
wpctl set-default <source_id>
```

**Pitfall:** `pactl set-card-profile` does NOT persist across disconnections. Use WirePlumber rules for persistence.

## Auto-Switch on Connect (WirePlumber Rule, Recommended)

Create `~/.config/wireplumber/bluetooth.lua.d/51-<device-name>.lua`:

```lua
-- Auto-switch bluetooth device to headset profile (enables microphone)
rule = {
  matches = {
    {
      { "device.name", "equals", "bluez_card.XX_XX_XX_XX_XX_XX" },
    },
  },
  apply_properties = {
    ["device.profile"] = "headset-head-unit",
  },
}

table.insert(bluez_monitor.rules, rule)
```

Replace `XX_XX_XX_XX_XX_XX` with the device's MAC address (underscores, not colons).

To use mSBC (wideband) instead:
```lua
["device.profile"] = "headset-head-unit-msbc",
```

Restart to apply:
```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

## Finding the Device Name

```bash
# Method 1: wpctl status — look for bluez5 device
wpctl status

# Method 2: pactl list cards
pactl list cards | grep "device.name" | grep bluez

# Method 3: bluetoothctl
bluetoothctl devices
```

## Verification

```bash
# Confirm profile switched
pactl list cards | grep -A 3 "Active Profile"
# Should show: headset-head-unit or headset-head-unit-msbc

# Confirm source exists
pactl list sources short
# Should show bluez_input.* source

# Confirm default source
wpctl status | grep -A 3 "Sources:"
# Should show bluetooth source with * marker

# Check Wemeet/Zoom is using it
wpctl status | grep -A 5 "Streams:"
# Should show app input connected to bluetooth capture
```

## Pitfalls

### Audio quality drops when mic is active
HFP/HSP profiles are bidirectional but low-bandwidth. Audio quality for playback drops to phone level when the mic is in use. This is normal — switch back to A2DP when not needing the mic:
```bash
pactl set-card-profile bluez_card.<MAC> a2dp-sink
```

### pactl set-default-source doesn't stick
`pactl get-default-source` may show a bluetooth sink `.monitor` instead of the expected source. Use `wpctl status` to verify the actual default. The WirePlumber rule handles persistence correctly.

### Device reconnects with A2DP by default
Without a WirePlumber rule, bluetooth devices reconnect in A2DP (playback-only) mode. The lua rule is required to auto-enable the microphone on every connection.

### Bluetooth mic not detected by apps
Some apps (especially Wemeet/Zoom) only detect sources that exist when they start. If you connect the bluetooth mic after launching the app, restart the app. WirePlumber rules help by activating the mic profile before the app checks.

### Multiple bluetooth devices
Each device needs its own rule file. WirePlumber matches `device.name` which includes the MAC address, so rules are device-specific.
