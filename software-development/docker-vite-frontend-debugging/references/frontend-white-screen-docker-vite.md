# Frontend white-screen in Docker/Vite

Session notes:
- Both `/` (front) and `:8081` (admin) rendered a blank page with only `#app` in the DOM.
- Nginx served HTML successfully; issue was in client-side JS/runtime, not HTTP availability.
- Browser/console checks showed module-load/runtime errors, including stale hashed asset references and module-evaluation exceptions.

Useful probes:
- `curl -I http://localhost` and `curl -s http://localhost | sed -n '1,40p'`
- Browser console: inspect `document.body.innerHTML`, `performance.getEntriesByType('resource')`, and unhandled errors
- Verify actual asset names in container HTML match built assets in `/usr/share/nginx/html/index.html`

Common causes observed:
- Old `index.html` cached by browser or stale container image pointing at removed hashed assets
- Vite chunking/manualChunks producing circular chunk/runtime import issues
- Runtime exception during module evaluation before `app.mount()`
- Missing favicon or other 404s are usually noise unless they stop JS execution

Fix pattern:
1. Confirm HTML is served and find the exact JS entry the browser is loading.
2. Compare browser-requested asset filenames with container `index.html`.
3. Read browser console errors and module import failures before touching API/backend code.
4. Rebuild/recreate the frontend container after asset/hash changes.
5. Re-test with a hard refresh / cache-busting query string only after the new image is running.
