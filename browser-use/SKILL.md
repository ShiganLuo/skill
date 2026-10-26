---
name: browser-use
description: "Use when driving Chrome through the browser-use CLI harness."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [browser, cdp, automation, chrome, harness]
    related_skills: [bot-protected-scraping, visual-render-verification, dogfood]
---

# browser-use Harness

## When to Use

`browser_exec` returns `browser-harness: daemon didn't come up`, or a task
needs to drive Chrome (open a URL, click, extract, screenshot) through the
harness.

## Two facts that explain most failures

1. **The CLI starts the daemon BEFORE it execs your `code`.** Any env var you
   set inside `code` (`os.environ["BU_CDP_WS"] = ...`) is too late — the
   failure happens before your first line runs. Symptom: stderr contains only
   `browser-harness: daemon default didn't come up` and your prints never
   appear. Pre-configure via a `.env` file instead (the daemon's `_load_env()`
   reads these at import):
   - `<session workspace>/.env` — the `workspace` path reported in results
     (honors `BH_AGENT_WORKSPACE`)
   - `~/.config/browser-harness/agent-workspace/.env` — fallback when
     `BH_AGENT_WORKSPACE` is unset
   (`repo_root/.env` inside site-packages also works but pollutes the package
   cache — last resort only.)
2. **Helpers are pre-injected into globals**, not importable:
   `new_tab, goto_url, wait_for_load, page_info, js, capture_screenshot, cdp,
   fill_input, click_at_xy, scroll, list_tabs, ensure_real_tab, wait, ...`.
   Call them directly — `from browser_use import new_tab` raises ImportError.

## Connection recipe (dedicated automation Chrome)

```bash
# terminal(background=true) — never setsid/nohup, the wrapper is rejected
google-chrome --headless=new --remote-debugging-port=9222 \
  --user-data-dir=/home/<user>/.config/<dedicated-dir> \
  --no-first-run --no-default-browser-check about:blank
```

Then write into the session workspace `.env`:

```
BU_CDP_URL=http://127.0.0.1:9222
```

The daemon resolves the websocket itself by fetching `/json/version`
(`BU_CDP_URL` preferred over `BU_CDP_WS`: no need to track the per-launch
browser GUID). Verify with
`curl --noproxy '*' http://127.0.0.1:9222/json/version`.

Why a **dedicated** `--user-data-dir` (from the harness source's own comment):
Chrome 136+ refuses remote debugging on the default profile, and Chrome 144+
can raise a per-connection "Allow remote debugging" approval popup — a
dedicated non-default profile avoids both, and leaves the user's real browser
(and its tabs/cookies) untouched.

Minimal working call:

```python
new_tab("https://example.com/path")
wait_for_load()
print(page_info())            # {'url', 'title', 'w', 'h', ...}
print(capture_screenshot())   # returns {'screenshot_path': ...} — then vision it
```

## SPA item pages: recover the gated URL from page state

Symptom: the site's **list/search page loads fine** in the browser, but
direct item URLs land on a 404 / "sec" interstitial (小红书 `/404?...sec_xxx`),
and archives/extractors can't help — the page exists, only the navigation
is gated. Don't fight it with clicks; rebuild the URL the app itself would
use:

```python
# on the LIST page, in page context:
tok = js("""(()=>{const f=window.__INITIAL_STATE__?.search?.feeds;
  const a=f&&(f._rawValue||f._value||f); const it=(a||[]).find(x=>x.id==='NOTE_ID');
  return it?(it.xsecToken||it.xsec_token||''):''})()""")
goto_url(f"https://www.xiaohongshu.com/explore/NOTE_ID?xsec_token={tok}&xsec_source=pc_search")
```

- **Never URL-encode the token** — `quote()` turning `=` into `%3D` produces
  the same 404. Tokens are bound to the search context: harvest them right
  after loading that search page.
- **Search-result `displayTitle` may come back empty for ALL items**
  (2026-10 third-round: 4 keyword groups, every `title=''`). Not a failure —
  id+token is enough; dedupe by id and pull titles from the detail page's
  `noteDetailMap` note.title instead. Write detail fetches as jsonl
  append+flush per note so a mid-batch crash keeps earlier data.
- Click fallback: JS `.click()` is `isTrusted=false` and gets flagged;
  `click_at_xy` (real CDP input) works, but virtualized/transform lists make
  rect and `elementFromPoint()` disagree after scrolling — validate the
  point's owner before clicking, or skip clicks entirely (token route).
- **Content completeness on carousel platforms**: the caption is not the
  note — questions/JDs live in slide images. Collect
  `.swiper-slide:not(.swiper-slide-duplicate) img` srcs (already in DOM;
  `naturalWidth === 0` only means "not loaded", never filter on it), download
  with a `Referer: https://www.xiaohongshu.com/` header, OCR with
  `tesseract -l chi_sim+eng --psm 6`. Long screenshots (1080×4000+ phone
  captures) defeat tesseract even with chunking/binarization — call a vision
  model on the whole image instead (GLM `glm-4.5v` recipe in the reference).
  Full recipe: `references/xiaohongshu-scraping.md`.
- **Desktop-notification diagnostics** (user's Gmail case): verify the
  three-layer chain OS → browser permission → web-app setting, self-verify
  popups via screenshot, and never trust the automation profile's permission
  state. Recipe: `references/desktop-notifications.md`.

## User-owned login flows: launch the VISIBLE window when asked

If the user says「直接启动chrome窗口让我扫码」/「让我自己扫」, do NOT keep the
headless instance and hand them a saved QR PNG — they want the real window on
their desktop. Kill the headless Chrome first (profile lock: two Chromes can't
share one `--user-data-dir`), then relaunch **headed** with the same persistent
profile + desktop UA + CDP flags:

```bash
# terminal(background=true)
DISPLAY=:0 google-chrome --ozone-platform=x11 --remote-debugging-port=9222 \
  --remote-allow-origins=* --user-data-dir=~/.config/xhs-scraper \
  --no-first-run --no-default-browser-check --no-proxy-server --lang=zh-CN \
  --user-agent="Mozilla/5.0 ... Chrome/<ver> Safari/537.36" "https://www.xiaohongshu.com"
```

The user scans directly on screen; the same 9222 CDP setup keeps working for
your scraping code afterwards (verify login via `document.querySelector('.login-modal')`
gone / nav bar showing「我」). Session 2026-10-12: user corrected the
save-QR-PNG flow to this and it worked first try.

## Windows-driven tasks: you're on the Linux box, the target machine is remote

When the user reports an error from their **Windows** machine (installers,
PowerShell, 安全中心, 杀软), remember the agent's box is Linux — you cannot run
the fix yourself. Workflow that worked (2026-10 Hermes install failure):

1. **Diagnose from log files the user copies over** (e.g. they scp/copy
   `install.log` to the Linux box and give the path). Read it, count failure
   occurrences (N failures = systematic block, not random AV scan), decode
   mojibake: GBK Chinese read as UTF-8 (「绯荤粺鏃犳硶…」=「系统无法打开…」,
   os error -2147024786 = 0x8007006E ERROR_OPEN_FAILED).
2. **Give exact copy-paste PowerShell blocks**, one step per message, and
   require the output back before advancing. Beware terminal table borders
   corrupting pasted commands (`│` vs `|` broke a Select-Object call).
3. **Enterprise security clients (飞连/Zero-Trust) can't be beaten user-side.**
   Security-center entries persist after killing processes (registration in
   SecurityCenter2/WMI ≠ process state — "为什么杀掉了还显示已开启" is expected).
   When AV exclusions fail, offer: (a) ask company IT to whitelist the path,
   or (b) WSL2 bypass. Both beat more exclusion guessing.
4. **Known-good diagnosis**: uv's `Failed to update Windows PE resources` on
   trampoline exes = AV/EDR locking the file (astral-sh/uv#20567); 6/6 retry
   failure across AVs = systematic interception by the enterprise client, not
   probabilistic scanning.

## Pitfalls

- **`daemon ... didn't come up` + no output from your code** = connection
  problem, not a code problem. Read
  `~/.config/browser-harness/tmp/bu-default.log` for the real reason
  (`DevToolsActivePort not found in [...]` = no browser matched → recipe above).
- **A headed Chrome that exits right after printing `DevTools listening on
  ws://127.0.0.1:9222`** — relaunch with `--headless=new`; don't debug further.
- **Clean up when done**: delete the `.env` you wrote. A stale `BU_CDP_URL`
  makes every later session attach to a dead port instead of launching a
  browser of its own.
- **Site-level blocks are not harness failures.** If `page_info()` returns a
  real URL — even a risk/verify page (e.g. XHS `error_code 300012 "IP at
  risk"`) — the connection worked; the site is judging the network or
  fingerprint. **First fix the fingerprint: the headless UA string
  (`HeadlessChrome`) is the usual root cause** — relaunch Chrome with a
  desktop UA (`--user-agent="Mozilla/5.0 (X11; Linux x86_64)
  AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<ver> Safari/537.36"`,
  version-matched to the installed Chrome). This alone cleared 300012 on
  XHS where both direct and proxy retries had failed. **Second, a login
  wall after the risk page is progress**: XHS search now requires login —
  relaunch headed (`DISPLAY=:0 --ozone-platform=x11`) with a persistent
  dedicated profile (e.g. `~/.config/xhs-scraper`), let the user scan the
  QR (save it with `capture_screenshot()` or dump `img.qrcode-img` base64),
  keep the profile afterwards so later sessions skip the scan. Only
  escalate to the user (their network, their browser, links/screenshots)
  if UA spoof + login both fail. For deeper anti-bot walls,
  `bot-protected-scraping` is the next ladder.
- **Daemon wedged mid-session: `_IPCResponseTimeout` / `TimeoutError: timed
  out` / `Page.navigate timed out after 5s waiting for the daemon`.** Common
  after relaunching Chrome (the daemon still holds the dead websocket) or
  after a heavy call. Fix: `restart_daemon()` must be the **last statement
  of its own `browser_exec` call** — the socket dies instantly, so anything
  after it in the same call fails with `FileNotFoundError: ...`; the *next*
  call re-creates the daemon. Don't retry the failed call in-place.
- **Your automation Chrome is NOT the user's Chrome.** Reading
  `Notification.permission`, cookies, or site settings from the harness
  instance tells you nothing about the user's daily-browser state — different
  profile entirely. (2026-10: concluded Gmail notifications were "denied"
  from the automation instance; the user's real profile had them allowed.
  User called it out:「google邮箱本来就是允许的，你是怎么查询的」.) To inspect
  the user's real browser state, read their profile files on disk
  (`~/.config/google-chrome/Default/Preferences` — content_settings exceptions,
  setting 1=allow/2=block) instead of trusting harness-session reads.
- **One browser per session**: pass `session=<name>` on related calls for an
  isolated daemon; the default daemon is shared.
