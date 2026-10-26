# Cloudflare Turnstile Bot Protection

UCSC Genome Browser uses Cloudflare Turnstile bot protection. This blocks
headless Chrome, curl, and any automated access to the UCSC web interface.

## Symptoms

- UCSC pages show "The Genome Browser is protecting itself from bots" message
- `curl` returns 813-byte captcha HTML instead of page content
- Headless Chrome (even with xvfb + non-headless mode) gets stuck on
  "Verifying..." forever — Turnstile iframe never renders
- `BU_CDP_WS` browser harness cannot navigate to UCSC pages

## What Does NOT Work

- `curl` with browser User-Agent headers → captcha page
- `google-chrome --headless=new` with `--user-agent=` flag → captcha page
- `xvfb-run google-chrome` (real display, non-headless) → captcha page
- Injecting Turnstile script manually via CDP → script loads but widget
  doesn't render (no iframe created)
- Waiting for auto-resolution → never resolves in headless/xvfb

## What Works

- **Ask the user to share the content** — screenshot, URL parameters, or
  describe what they see
- **UCSC API endpoints** (`api.genome.ucsc.edu/...`) do NOT have Turnstile
  protection for most read-only queries
- **hgdownload.soe.ucsc.edu** (file download server) has no Turnstile

## Recommendation

When debugging UCSC issues, rely on:
1. User-provided screenshots or descriptions
2. `pyBigWig` local file analysis (no UCSC access needed)
3. UCSC API for metadata queries
4. Asking user to check F12 → Console for JS errors

Do NOT attempt to automate UCSC web page access — it will fail silently
after consuming significant time.