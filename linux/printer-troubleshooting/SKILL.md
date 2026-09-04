---
name: printer-troubleshooting
description: "Use when configuring printers on Linux."
tags: [linux, printing, cups, usb, ipp, lpd, smb, canon]
related_skills: []
---

# Printer Troubleshooting

Use this skill when the user needs a printer added, repaired, or verified on Linux.

## Core workflow
1. Identify the connection type: USB, IPP/IPPS, LPD, SMB, or JetDirect/9100.
2. Check CUPS: `systemctl is-active cups` and `lpstat -t`.
3. List backends: `lpinfo -v`.
4. List candidate drivers/PPDs: `lpinfo -m`.
5. Add the queue with `lpadmin`, then print a test page.

## Canon laser printers
- Canon imageCLASS LBP6230dn supports USB direct printing.
- If the printer is shared on the office network, prefer the network URI over USB.
- If the user is offline from the office network, only USB direct attach works, and only when the printer is physically connected.

## Driver selection
- Prefer the manufacturer driver or the closest matching PPD when available.
- For older Canon laser printers, generic PCL/PostScript may work if the exact model is missing.
- Confirm the exact URI before adding a network queue; do not guess.

## Verification
- `lpstat -p -d`
- `lpoptions -p <queue> -l`
- print a CUPS test page or a tiny text file

## Pitfalls
- Network printers need the real address; model name alone is not enough.
- USB printers do not appear until the cable is connected and the device is powered on.
- Some printers expose both USB and Ethernet; pick one path and verify it end-to-end.

## See also
- `references/canon-lbp6230dn.md` for session notes and model-specific findings.
