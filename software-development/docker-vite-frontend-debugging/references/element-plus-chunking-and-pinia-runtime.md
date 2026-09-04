# Element Plus chunking + Pinia persistedstate runtime notes

Session summary:
- Two Docker-served Vue/Vite apps (admin + front) returned HTTP 200 but rendered a white page.
- Backend being down was a red herring for the white screen; the frontend failed before mount.

Confirmed failure signatures:
- Admin runtime import of the built entry surfaced `ReferenceError: Cannot access 'j' before initialization` inside an aggressively split Element Plus chunk (`ep-affix...`).
- Front runtime import surfaced `TypeError: Cannot destructure property 'options' of 's' as it is undefined` from the Pinia/persistedstate path before mount.
- Browser snapshots showed `#app` remaining empty even though `index.html` and the entry JS were served successfully.

Working fixes:
1. Revert Element Plus `manualChunks()` from per-component splitting back to a coarse stable split:
   - `element-plus`
   - `ep-icons`
   - `vue`
   - `pinia`
   - `axios`
   - `vue-router`
   - `vendor`
2. For the front app, fix `src/env.d.ts` for `pinia-plugin-persistedstate` to export a plugin value:
   - `const piniaPluginPersistedstate: PiniaPlugin`
   - `export default piniaPluginPersistedstate`
3. Mount persistedstate as a plugin value in `src/main.ts`:
   - `pinia.use(piniaPluginPersistedstate)`
4. Ensure any computed auth alias consumed elsewhere is actually returned from the store.

Verification pattern:
- `docker compose build <frontend>`
- `docker compose up -d --force-recreate <frontend>`
- `curl` confirms the current hashed entry in `index.html`
- browser snapshot confirms actual visible content (not just empty `#app`)

Interpretation rule:
- A pure white page with served HTML/JS usually means frontend runtime failure before `app.mount()`, not an API outage.
