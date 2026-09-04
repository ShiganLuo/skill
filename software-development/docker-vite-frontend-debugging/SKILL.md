---
name: docker-vite-frontend-debugging
description: Use when Docker Vite frontends show a blank page.
tags: [vue, vite, docker, nginx, blank-page, runtime, debugging]
related_skills: [systematic-debugging, safe-file-editing]
---

# Docker + Vite Frontend Debugging

Use when a Docker-served Vue/Vite app reaches HTTP but renders white/blank.

## First checks
1. **Check container logs FIRST, not source code.** The user explicitly corrected this: "遇见问题你不查日志,为什么在源码里面大海捞针". Run `docker logs <container> --tail 50` for all relevant containers (backend, frontend, nginx-proxy) before reading any source files. Logs reveal the actual runtime errors; source code reading is speculative.
2. **Check nginx-proxy health first** if using a shared reverse proxy: `docker exec nginx-proxy nginx -t`. If the config test fails (e.g., "host not found in upstream"), the entire proxy is broken — ALL domains return 000, not just yours. This looks like a "blank page" but is actually a complete infrastructure failure. Fix the missing upstream containers before debugging the frontend. See `vue3-deployment` skill for the cascading failure pattern.
2. Confirm HTML is served: `curl -I` and `curl -s` the root URL. Use `curl --noproxy '*'` if the server has an HTTP proxy configured.
3. Inspect the DOM: if `#app` exists but stays empty, the app likely failed before mount.
4. Read browser console/runtime errors, including dynamic import failures.
5. Compare the HTML entry script and preloads against the actual files in the container image.

## Common root causes
- **`VITE_API_BASE_URL` double-prefix (CRITICAL)**: In `.env.production`, if `VITE_API_BASE_URL=/api` AND the API call paths in source code already start with `/api/` (e.g., `http.get('/api/front/projects/list')`), the resulting request URL becomes `/api/api/front/projects/list` → 403 from backend (no matching controller). This is invisible in dev mode because the vite dev server proxy intercepts `/api` directly. Fix: set `VITE_API_BASE_URL=` (empty) in `.env.production` when API paths already include `/api`. Verify with puppeteer: `page.on('response', resp => console.log(new URL(resp.url()).pathname))` — look for double `/api/api/`.
- **Vue Router missing route for `/home`**: If the home page is defined as `path: ''` (matches `/` only), visiting `/home` renders blank — the SPA loads but no route matches. Fix: add `{ path: '/home', redirect: '/' }` to the routes array.
- Stale hashed asset names in `index.html` after rebuilds
- Browser cache or an old container image still serving removed assets
- Runtime exception during module evaluation before `app.mount()`
- Circular or invalid manual chunking causing module init errors
- Over-fine `manualChunks()` rules for Element Plus creating runtime init/circular-order failures; if you see blank pages after aggressive per-component splitting, revert to a coarser stable split (`element-plus`, `ep-icons`, `vue`, `pinia`, `axios`, `vendor`) before chasing backend issues
- Asset 404s that are harmless unless they block JS evaluation
- Pinia plugin declaration/usage mismatch: some setups expose `pinia-plugin-persistedstate` as a plugin value, not a plugin factory. A wrong ambient declaration or calling it with `()` can produce runtime errors before mount even if TypeScript was previously silenced

## Debug flow
1. Capture the exact script URL the browser loads.
2. Fetch that script URL directly and verify it exists in the container.
3. If the page is blank, inspect `document.body.innerHTML` and `performance.getEntriesByType('resource')`.
4. Rebuild the frontend image and recreate the container after any Vite config or chunking change.
5. If browser/runtime errors show missing modules or initialization cycles, inspect the chunk graph before blaming the backend.
6. For Element Plus blank pages after chunk optimization, temporarily collapse `manualChunks()` back to a coarse package-level split to rule out runtime chunk-order bugs.
7. Check plugin ambient declarations (`src/env.d.ts`) against the library's real runtime shape; fix the declaration before “typing around” the problem in app code.
8. If Pinia/plugin issues are suspected, confirm the store exports the exact properties consumed by templates/guards (e.g. computed auth flags) so mount does not fail during initial render.
9. If asset filenames changed, hard refresh or use a cache-busting query string to verify the new bundle.

## Verification
- The page shows mounted Vue content, not just `#app`
- The console is free of module-import/runtime errors
- The browser requests match the current `index.html` asset filenames
- **Use headless Chrome + Puppeteer for automated verification.** Install `puppeteer-core` and use system Chrome: `puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox','--disable-gpu','--ignore-certificate-errors'] })`. Capture `page.on('response')` for API status codes and `page.on('console')`/`page.on('pageerror')` for JS errors. The user expects actual browser testing, not just curl: "不要活在自己的幻想里,实际测试浏览器".

## Notes
- Backend outages do not normally cause a pure white page by themselves; treat blank pages as a frontend/runtime problem first.
- Keep nginx 404s for favicon/vite.svg separate from JS-breaking failures.
- SpringDoc/Knife4j pages that render only a shell can also be broken by global Jackson default-typing bleeding into `/v3/api-docs/swagger-config`. If the endpoint returns `@class` wrappers or non-plain collections/maps, Swagger UI may show "Unable to render this definition" or an empty shell even though `/v3/api-docs` itself contains valid OpenAPI JSON.
- In Spring Boot apps with a Redis-specific `ObjectMapper`, do NOT expose that mapper as a global `@Bean` unless you truly want it used everywhere. Keep the Redis mapper private/local and wire it only into the Redis serializer to avoid corrupting SpringDoc/Swagger config JSON.
- If Swagger UI still receives both `url` and `urls` in swagger-config, prefer simplifying to a single stable `url: /v3/api-docs` path and verify `swagger-config` no longer carries framework-specific metadata wrappers.
- See `references/element-plus-chunking-and-pinia-runtime.md` for the runtime signatures and the stable rollback pattern that fixed two Docker Vite apps in this session.
- See `references/swagger-ui-empty-shell-from-jackson-typing.md` for the SpringDoc/Redis/Jackson interaction discovered in this session.

See `references/frontend-white-screen-docker-vite.md` for the session-specific transcript and probes.
