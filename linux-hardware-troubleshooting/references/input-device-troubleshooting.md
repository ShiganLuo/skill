# Input Device Troubleshooting

## Touchpad Tap-to-Click Not Working

**Common after:** Ubuntu version upgrades, fresh installs, or desktop environment changes.

**Symptom:** Touchpad moves the cursor but tapping (finger click) doesn't register as a mouse click.

### Diagnosis

```bash
# Identify touchpad device
xinput list | grep -i -E "touch|synap|elan"

# Check if tapping is enabled (replace X with device id)
xinput list-props X | grep -i tap
```

Key property: `libinput Tapping Enabled` — if value is `0`, tapping is disabled.

### Fix (runtime, immediate)

```bash
xinput set-prop <device-id> "libinput Tapping Enabled" 1
```

### Fix (persistent, survives reboot)

```bash
sudo mkdir -p /etc/X11/xorg.conf.d
sudo tee /etc/X11/xorg.conf.d/40-touchpad.conf << 'EOF'
Section "InputClass"
    Identifier "touchpad"
    MatchIsTouchpad "on"
    Driver "libinput"
    Option "Tapping" "on"
EndSection
EOF
```

### Other common touchpad properties

```bash
# Natural scrolling
xinput set-prop <id> "libinput Natural Scrolling Enabled" 1

# Disable-while-typing
xinput set-prop <id> "libinput Disable While Typing Enabled" 1

# Tap-and-drag
xinput set-prop <id> "libinput Tapping Drag Enabled" 1
```

**Pitfall:** `xinput set-prop` changes are lost on reboot. Always create the xorg.conf.d file for persistence.