# Canon imageCLASS LBP6230dn

Session findings:
- User asked whether the office Canon imageCLASS LBP6230dn can print over USB.
- Confirmed via web results that the model supports USB direct printing.
- The printer is also network-capable, so network URI is preferred when the office network is reachable.

Practical implications:
- If the user is away from the office network, remote network printing cannot be added without the printer's address.
- USB is only usable if the printer is physically connected to the user's Linux machine or to the machine acting as the print host.

Working CUPS checklist:
- `systemctl is-active cups`
- `lpinfo -v`
- `lpinfo -m | grep -iE 'canon|lbp|ufr|cjet'`
- `lpadmin -p <queue> -E -v <uri> -m <model>`

Notes:
- Do not guess the printer URI.
- If the exact Canon PPD is unavailable, try the closest generic PCL/PostScript driver.