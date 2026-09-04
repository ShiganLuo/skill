# Testing Deployed Sites & Blank Page Diagnosis

## Headless Chrome Testing

When `browser_navigate` is unavailable or broken, use headless Chrome directly via terminal:

```bash
# Check rendered DOM (Vue components present?)
google-chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=10000 \
  --dump-dom "https://site/" 2>/dev/null | grep -c "el-"

# Check page title and body text
google-chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=10000 \
  --dump-dom "https://site/" 2>/dev/null | grep "<title>"

# Check if Vue rendered anything meaningful
google-chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=10000 \
  --dump-dom "https://site/" 2>/dev/null | grep 'id="app"'
# Empty <div id="app"></div> = Vue failed to render

# Full API chain test (no headless needed)
curl -sf --max-time 5 -o /dev/null -w "%{http_code}" https://site/
curl -sf --max-time 5 -o /dev/null -w "%{http_code}" "https://site/assets/index-xxx.js"
curl -sf --max-time 5 https://site/api/front/site-config
curl -sf --max-time 5 -X POST https://site/api/admin/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
```

**Key**: `--virtual-time-budget=10000` makes Chrome wait for JS execution before dumping DOM. Without it, you get the pre-render HTML only (empty `<div id="app">`).

## Blank Page Diagnosis Order

When a Vue3 page loads (200 status) but shows blank:

1. **Element Plus not registered** — `app.use(ElementPlus)` missing in main.ts. Check with headless Chrome for `el-` classes.
2. **API returning 500** — Check `curl` against all APIs the page calls on mount. Even with try/catch in Vue, a failing API can prevent component initialization.
3. **Router guard blocking** — Check for `beforeEach` guards that redirect unauthenticated users.
4. **JS runtime error** — Use `google-chrome --headless --enable-logging --v=0` to capture console errors.

## Server Proxy Bypass

Servers often have `http_proxy`/`https_proxy` env vars pointing to a dead proxy. Always use `--noproxy '*'` for localhost/container requests:

```bash
curl --noproxy '*' -sf http://localhost:8083/api/...
```
