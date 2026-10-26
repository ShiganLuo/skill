# Headless Chrome + CDP: real-time verification for SPAs and live sites

Use when the browser-use harness is unavailable, or when you need MORE than a static
screenshot: computed styles, element rects, real clicks, hover states, or proof that an
interaction (collapse/toggle) actually works. All of this was validated in a live session
verifying a Vue3 blog on a production site.

## Launch (needs `--remote-allow-origins=*` or the WS handshake gets 403)

```bash
google-chrome --headless=new --disable-gpu --no-sandbox \
  --remote-debugging-port=9222 --remote-allow-origins=* --window-size=1400,1000 about:blank
```

Run via `terminal(background=true)` — it is a long-lived daemon. Kill/restart with
`process kill` if a session ends.

Before launching, confirm the port is free: `ps aux | grep remote-debugging-port`.
This machine often has ANOTHER headless Chrome already bound to 9222 (desktop/browser
session) — see the 403 pitfall below. In that case pick a fresh port (9223) and give
your instance its own `--user-data-dir=/tmp/...`.

## Drive it (python `websocket-client` is available in this environment)

```python
import json, urllib.request, time, websocket, base64
page = [t for t in json.load(urllib.request.urlopen("http://localhost:9222/json"))
        if t["type"] == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60)
_id = [0]
def send(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg
def ev(expr):  # evaluate JS, get value back
    return send("Runtime.evaluate", {"expression": expr, "returnByValue": True}) \
        ["result"]["result"].get("value")
def shot(path):
    r = send("Page.captureScreenshot", {"format": "png"})
    open(path, "wb").write(base64.b64decode(r["result"]["data"]))

send("Page.enable")
send("Page.navigate", {"url": "https://example.com/page"})
time.sleep(6)                      # real time — let async chunks land
print(ev("JSON.stringify({href: location.href})"))
shot("/tmp/x.png")
```

Useful probes: `getBoundingClientRect()`, `getComputedStyle()` (padding/color/bg —
settle "is there a gap / is the text visible" arguments with numbers, not eyes),
`document.querySelectorAll('button').find(b => b.textContent.includes('…')).click()`
for real interactions, `Input.dispatchMouseEvent` {type:"mouseMoved",x,y} for hover
states, `Emulation.setDeviceMetricsOverride` for viewport sizes.

## Pitfalls learned the hard way

- **`--virtual-time-budget` screenshots race async work**: route-level CSS chunks and
  data fetches may not have landed → screenshot shows unstyled/blank content while the
  live page is actually fine. This produced a false "content is flush against the edge"
  conclusion that the user then echoed back as a bug report. For SPAs / live sites,
  prefer real-time CDP waits (6–8 s) over virtual-time screenshots.
- **Never mix measurements across interaction states**: probing a "collapsed" state
  while eyeballing a screenshot of the "expanded" state yields contradictory nonsense
  (e.g. element "overlapping" its own sidebar). Take probe + screenshot atomically in
  ONE state, and label which state it is.
- **History-mode SPAs**: verify the canonical URL first (this site used
  `createWebHistory`; `/#/route` silently lands on the home route while still LOOKING
  like a valid URL in screenshots' address context).
- Screenshot frames can occasionally capture a blank paint even when the DOM has
  content — cross-check with a DOM probe (`textContent.length`, element rects) before
  declaring a rendering bug; re-shoot if DOM says content exists.
- **`Emulation.setDeviceMetricsOverride` resets BETWEEN separate tool calls** (it does
  NOT persist across invocations; viewport snaps back to the launch `--window-size`).
  A "mobile390" test that spanned two calls silently ran its second half at desktop
  width, where the element under test was `display:none` — producing a phantom "click
  doesn't work" bug. Rule: set metrics → navigate → interact → probe ALL inside ONE
  call, and re-assert `innerWidth` before each interaction block.
- **Vision is unreliable for sidedness (left/right) on rtl/overlay layouts**: two vision
  reads called a right-anchored drawer "on the left" (an rtl drawer puts its ✕ at the
  panel's inner-left, visually mimicking a left panel). Settle sidedness with
  `getBoundingClientRect()` (`Math.abs(rect.right - innerWidth) < 4` = right-anchored),
  or tint-and-measure: set `background: rgb(255,0,0)` on the target,
  `background: rgba(0,0,255,0.5)` on the overlay, screenshot, then bbox each color with
  PIL. Never conclude "wrong side" from vision alone.
- **Capture methods can disagree with each other — tie-break with the source asset**:
  one session produced three different stories about whether an `<img>` rendered —
  full-page capture said white, a clip-scaled capture of the same region said photo,
  PIL pixel sampling of the PNG said solid color, and vision confidently narrated all
  of them. Do NOT pick the most convenient one or re-shoot hoping for agreement.
  Ground truth lives OUTSIDE the browser: download the actual asset (its URL), crop it
  the way `object-fit` would (PIL resize + center-crop), and require **DOM probe +
  full screenshot + source asset** to agree 3-of-3 before concluding either "render
  bug" or "renders fine". A single capture flavor is never enough evidence to
  authorize a code change.
- **Page state can flip WITHOUT you (theme / auto-dark toggles)**: a site switched its
  `html.dark` class mid-session; screenshots minutes apart then "proved" a regression
  that never existed, and DOM probes from yet another moment contradicted both. Pair
  every screenshot with an atomic same-call probe of the state marker
  (`document.documentElement.className` / `getComputedStyle`), compare only
  same-state pairs, and when you need the other state, force it
  (`classList.add/remove('dark')`) and re-take BOTH probe and shot together.
- **Loopback HTTP from scripts needs the proxy env neutralized**: this machine sets
  `http_proxy`-style env vars, so `urllib.request.urlopen("http://localhost:92xx/json")`
  can hang or misroute — build the opener with
  `urllib.request.build_opener(urllib.request.ProxyHandler({}))` (curl: `--noproxy '*'`).
