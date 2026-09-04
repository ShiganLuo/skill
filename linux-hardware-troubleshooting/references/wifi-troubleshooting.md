# Linux WiFi Troubleshooting

## Diagnostic Workflow

Run these in order to gather evidence before proposing fixes:

```bash
# 1. Identify WiFi hardware
lspci | grep -i -E "network|wifi|wireless|wlan"

# 2. Check current connection state
nmcli device status

# 3. Check regulatory domain (CRITICAL for missing networks)
iw reg get

# 4. Check per-PHY regulatory (self-managed vs kernel-managed)
iw phy phy0 info | grep -A2 -i "freq\|band\|channel" | head -60

# 5. Scan available networks
nmcli device wifi rescan; sleep 1; nmcli device wifi list

# 6. Check firmware and driver errors
dmesg | grep -i -E "ath12k|ath11k|iwlwifi|wifi|wlan|firmware" | tail -20

# 7. Check kernel and firmware versions
uname -r; dpkg -l | grep -i -E "linux-firmware|wireless-regdb"
```

## Key Indicator: Regulatory Domain Mismatch

The most common cause of "can't see certain WiFi networks" (especially 5GHz) is a **regulatory domain mismatch**.

Check `iw reg get` output. You'll see two sections:
- **global**: The kernel's configured regulatory domain
- **phy#N (self-managed)**: The firmware's own regulatory domain

If `global` shows `country CN` (or your country) but `phy#0 (self-managed)` shows `country 00`, the firmware is NOT reading the kernel's regdb. This causes:
- 5GHz channels marked `(no IR)` — no Initiation of Radiation
- 5GHz channels marked `PASSIVE-SCAN` — adapter only passively listens, misses most networks
- 2.4GHz may work fine (lower regulatory restrictions)

**This is the #1 cause of "phone sees WiFi but laptop doesn't" scenarios.**

## Common WiFi Drivers and Their Behavior

### ath12k (Qualcomm WCN785x / Wi-Fi 7)
- **Self-managed regulatory** — firmware controls reg domain, ignores kernel regdb
- Symptom: only 2.4GHz visible, 5GHz completely missing
- Fix: see "Fix: cfg80211 ieee80211_regdom" below

### ath11k (Qualcomm QCA6390 / Wi-Fi 6)
- Also self-managed regulatory on newer firmware
- Same symptoms and fix as ath12k

### iwlwifi (Intel AX200/AX210/BE200)
- Usually kernel-managed regulatory — respects `iw reg set`
- If misbehaving: check `dmesg` for firmware errors, try updating `linux-firmware`

### rtw88/rtw89 (Realtek)
- Mixed behavior — some chipsets are self-managed
- Check per-PHY reg domain in `iw phy phy0 info`

## Fix: cfg80211 ieee80211_regdom (ath12k/ath11k self-managed)

The `cfg80211` kernel module has an `ieee80211_regdom` parameter that can override the firmware's self-managed regulatory domain:

```bash
# Set CN (China) or your country code
echo "options cfg80211 ieee80211_regdom=CN" | sudo tee /etc/modprobe.d/cfg80211.conf

# Also set via iw for the current session
sudo iw reg set CN

# REBOOT REQUIRED — this parameter is read at module load time
sudo reboot
```

After reboot, verify:
```bash
iw reg get
# Both global and phy#0 should show "country CN"
```

### Supported country codes
Use ISO 3166-1 alpha-2: CN (China), US (United States), JP (Japan), DE (Germany), etc.

## Fix: Updating wireless-regdb and linux-firmware

If the modprobe fix doesn't work, the firmware itself may need updating:

```bash
# Check current versions
dpkg -l | grep -E "linux-firmware|wireless-regdb"

# Update from upstream (Ubuntu)
sudo apt update && sudo apt install --only-upgrade linux-firmware wireless-regdb

# Or install latest from git (more up-to-date)
cd /tmp
git clone --depth 1 https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git
sudo cp linux-firmware/ath12k/* /lib/firmware/ath12k/
sudo cp linux-firmware/regulatory.db /lib/firmware/regulatory.db
sudo update-initramfs -u
sudo reboot
```

## Pitfalls

### NEVER disconnect user's active WiFi during debugging
Running `nmcli device disconnect` or `modprobe -r` during diagnosis will drop the user's connection. If you need to reload a module, warn the user first and confirm they're OK with brief disconnection. Better yet: gather diagnostic info without disconnecting.

### modprobe -r may fail with "Device or resource busy"
Some WiFi drivers (ath12k, ath11k) depend on `qcom_scm` which cannot be unloaded. `modprobe -r ath12k` will fail with:
```
modprobe: ERROR: ../libkmod/libkmod-module.c:856 kmod_module_remove_module() could not remove 'qcom_scm': Device or resource busy
```
**Workaround:** Module reload requires a full reboot. Don't attempt module unloading unless the user agrees to reboot.

### iw dev <dev> set country doesn't exist
The `iw` command does NOT support `set country` on a specific device. You can only use `iw reg set <CC>` globally. For self-managed phys, even this doesn't affect the firmware — use the modprobe fix instead.

### cfg80211 ieee80211_regdom is read-only at runtime
You cannot change it via sysfs after module load. The modprobe config file must be set BEFORE the module loads (i.e., before boot). No runtime workaround exists — reboot is mandatory.

### sudo password may be unknown
If the agent doesn't know the sudo password, provide the full command block for the user to execute manually. Don't attempt password guessing.

### Passive scanning on 5GHz is unreliable
When regulatory domain is `country 00` or unset, 5GHz channels are often marked `PASSIVE-SCAN`. This means the adapter only listens for beacon frames — it does NOT send probe requests. Networks that don't broadcast beacons frequently (or use shorter beacon intervals) will be missed entirely. This is why the laptop sees fewer networks than a phone (which typically has proper CN regulatory configured).

## Quick Diagnosis Decision Tree

```
Can't see WiFi networks that phone/laptop can see?
│
├── Check iw reg get
│   ├── phy#0 shows "country 00" → Self-managed reg domain issue
│   │   └── Fix: cfg80211 ieee80211_regdom=<CC> + reboot
│   └── phy#0 shows correct country → Not a reg issue
│       └── Check dmesg for firmware errors
│           └── Update linux-firmware
│
├── Can see networks but can't connect?
│   └── Check nmcli device wifi list for security mismatch
│       └── WPA3 vs WPA2, enterprise vs personal
│
└── WiFi adapter not detected at all?
    └── lspci shows no network controller
        └── Hardware issue or BIOS disable
```

## Known Issue: MSI Alpha 17 C7VG (Qualcomm WCN785x)

This laptop uses the ath12k driver with WCN785x Wi-Fi 7 chipset. The firmware uses self-managed regulatory with `country 00` by default. 5GHz is completely invisible until the cfg80211 regdom fix is applied.

**Hardware info:**
- PCI: Qualcomm Technologies, Inc WCN785x Wi-Fi 7(802.11be) 320MHz 2x2 [FastConnect 7800]
- Driver: ath12k (kernel 6.17.0-35-generic)
- Firmware path: `/lib/firmware/ath12k/WCN7850/hw2.0/`
- Interface: wlp4s0
