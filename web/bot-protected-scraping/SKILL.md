---
name: bot-protected-scraping
description: "Use when headless Chrome is blocked by anti-bot detection."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Web, Scraping, AntiBot, Chrome, xvfb]
    related_skills: [blocked-page-recovery]
---

# Bot-Protected Site Scraping

## When to Use

A site returns 403, empty shells, or "request abnormal" errors from both
curl and headless Chrome. The blocked-page-recovery ladder (archive.org,
Jina, API pivot) has been exhausted or is inapplicable. The user has a
Chrome session with valid cookies for the target site.

When a site blocks headless Chrome (Zhihu, many Chinese platforms, sites
behind DataDome/PerimeterX/Cloudflare Bot Management), the standard
blocked-page-recovery ladder fails at step 5. This skill covers what comes
after.

**Prerequisite check**: this skill applies when ALL of these are true:
- curl/wget returns a JS-only shell or challenge page (not real content)
- `web_extract` fails or returns empty/error
- Headless Chrome (puppeteer with `headless: true`) gets 403 or
  "request abnormal" JSON error
- The site is NOT a Wayback/archive candidate (live data needed, or
  never archived)

## Technique: xvfb-run + headed Chrome

Sites detect `headless` mode via `navigator.webdriver`, Chrome DevTools
protocol artifacts, and missing compositor. Running **headed** Chrome under
a virtual framebuffer (Xvfb) defeats all three — it's a real Chrome with a
real X display, just invisible to the user.

### Prerequisites

```bash
# xvfb-run (usually pre-installed on Linux desktops/servers)
sudo apt install xvfb   # if missing
# puppeteer-core (no bundled Chromium — uses system Chrome)
npm install -g puppeteer-core
```

### The script pattern

```js
// fetch_page.js
const puppeteer = require('puppeteer-core');

(async () => {
    const browser = await puppeteer.launch({
        executablePath: '/usr/bin/google-chrome',
        headless: false,           // CRITICAL: headed mode
        userDataDir: '/tmp/chrome-profile',  // copied profile with cookies
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--profile-directory=Default'
        ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: 25000 });
    await new Promise(r => setTimeout(r, 5000));  // let JS render

    const content = await page.evaluate(() => {
        // site-specific selectors here; fallback to body.innerText
        const el = document.querySelector('.RichText, .article-content, main');
        return el ? el.innerText.trim() : document.body.innerText.substring(0, 10000);
    });

    console.log(content);
    await browser.close();
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
```

Run it:

```bash
xvfb-run --auto-servernum --server-args='-screen 0 1920x1080x24' \
  timeout 45 node fetch_page.js
```

### Why not puppeteer-extra-plugin-stealth?

Stealth patches `navigator.webdriver` and a few other signals, but modern
anti-bot (Zhihu's zse-ck, DataDone, PerimeterX) goes deeper — checking
Chrome's internal DevTools protocol state, compositor availability, and
canvas rendering. Headed mode under Xvfb passes all of these because it IS
a real browser. Stealth is a patch; Xvfb is the real thing.

## Login-required sites: Chrome profile + cookies

Many sites (Zhihu, LinkedIn, Twitter/X) require authentication. If the user
has an active Chrome session with valid cookies, reuse them.

### Step 1: Copy the Chrome profile

Chrome locks its profile directory while running. Copy to a temp location:

```bash
mkdir -p /tmp/chrome-profile/Default
cp ~/.config/google-chrome/Default/Cookies /tmp/chrome-profile/Default/
cp ~/.config/google-chrome/Default/Preferences /tmp/chrome-profile/Default/
cp ~/.config/google-chrome/Default/"Secure Preferences" /tmp/chrome-profile/Default/
cp ~/.config/google-chrome/"Local State" /tmp/chrome-profile/
```

### Step 2: Use the copied profile

Set `userDataDir: '/tmp/chrome-profile'` in puppeteer launch options. The
headed Chrome instance will load cookies from the copied profile and
authenticate with the target site automatically.

### Step 3: If cookies are encrypted (manual extraction fallback)

Chrome v11 cookies on Linux use:
- **Key**: `PBKDF2HMAC(password=b'peanuts', salt=b'saltysalt', iterations=1, keylen=16, hash=SHA1)`
- **IV**: 16 zero bytes
- **Algorithm**: AES-128-CBC
- **Prefix**: `v11` (3 bytes before ciphertext)

Decrypt with openssl:
```bash
# Extract ciphertext (strip v11 prefix)
python3 -c "
import sqlite3, hashlib
conn = sqlite3.connect('/tmp/cookies_copy.db')
key = hashlib.pbkdf2_hmac('sha1', b'peanuts', b'saltysalt', 1, dklen=16)
row = conn.execute(\"SELECT encrypted_value FROM cookies WHERE name='z_c0' LIMIT 1\").fetchone()
open('/tmp/enc.bin','wb').write(row[0][3:])  # strip v11
print(f'Key: {key.hex()}')
"
openssl enc -aes-128-cbc -d -nopad -K <key_hex> -iv 00000000000000000000000000000000 -in /tmp/enc.bin
# Then strip PKCS7 padding (last byte = pad length)
```

**When this works**: headless servers without gnome-keyring. On desktop
sessions, the profile-copy approach (Step 1-2) is simpler and more reliable
because Chrome handles keyring decryption internally.

## Pitfalls

1. **Don't use `headless: 'new'`** — Chrome's "new headless" still exposes
   detection signals. Use `headless: false` with xvfb-run.
2. **Don't use the live profile directory** — Chrome locks it. Always copy
   first.
3. **Don't retry the same headless approach** — if headless Chrome gets
   blocked once, switch to xvfb immediately. The anti-bot fingerprint is
   already flagged.
4. **Timeout generously** — xvfb + headed Chrome is slower to start than
   headless. Use 35-45s timeout for the node script.
5. **puppeteer-core, not puppeteer** — puppeteer bundles its own Chromium
   which may lack system fonts/locale. puppeteer-core uses system Chrome
   which has the user's real fonts and locale.