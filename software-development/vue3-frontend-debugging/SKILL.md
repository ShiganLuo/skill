---
name: vue3-frontend-debugging
description: "Use when Vue3 buttons do nothing, modals won't open, or API data doesn't load."
tags: [vue3, frontend, debugging, events, props]
---

# Vue3 Frontend Debugging

Diagnose and fix Vue3 component interaction bugs — buttons that do nothing, events that fire into the void, modals that won't open.

See `references/sse-auth-token-fix.md` for a worked example of the raw `fetch` token bypass pattern (bioplatform agent API).

## Diagnosis Steps

### 1. Trace the click handler
Find the button's `@click` handler. Follow it to its implementation.

```bash
# Find the button
search_files pattern="免费注册|button.*click" file_glob="*.vue"
# Find the handler definition
search_files pattern="function showLogin" file_glob="*.vue"
```

### 2. Check if the handler actually does something
Common failure patterns:

- **Window event with no listener**: Component dispatches `window.dispatchEvent(new Event('show-login-modal'))` but NO component has `window.addEventListener('show-login-modal', ...)`. The event fires and nobody hears it.
- **Ref toggle with wrong parent**: Component sets `showModal.value = true` but the `<Modal>` is rendered in a DIFFERENT component (e.g., layout parent), not in this one.
- **Store action missing**: Handler calls `store.someAction()` but the action doesn't exist or is a no-op.
- **Router navigation to non-existent route**: `router.push('/some-path')` where the route isn't registered.

### 3. Verify the full chain end-to-end
For window events, the chain must be:
1. **Dispatcher**: `window.dispatchEvent(new CustomEvent('event-name', { detail: payload }))`
2. **Listener**: `window.addEventListener('event-name', handler)` — must be in the component that OWNS the target (e.g., layout owns the modal)
3. **Lifecycle cleanup**: Listener added in `onMounted`, removed in `onUnmounted`
4. **Data pass-through**: Parent passes received data as prop to child component
5. **Consumer**: Child component reads prop and reacts (via `watch` or computed)

### 4. Verify prop definitions match
Check that `defineProps` in the child accepts what the parent passes.

## Fix Patterns

### Window event bridge (cross-component communication)
When two sibling/distant components need to communicate and there's no shared store:

**Dispatcher component:**
```ts
// Use CustomEvent with detail for payload
window.dispatchEvent(new CustomEvent('show-login-modal', { detail: 'register' }))
```

**Parent that owns the target component:**
```ts
import { onMounted, onUnmounted } from 'vue'

const showModal = ref(false)
const modalMode = ref<'login' | 'register'>('login')

function handleEvent(e: Event) {
  const detail = (e as CustomEvent).detail
  modalMode.value = detail || 'login'
  showModal.value = true
}

onMounted(() => window.addEventListener('show-login-modal', handleEvent))
onUnmounted(() => window.removeEventListener('show-login-modal', handleEvent))
```

**Template passes both binding and mode:**
```vue
<LoginModal v-model:visible="showModal" :mode="modalMode" />
```

**Target component accepts mode prop:**
```ts
const props = defineProps<{
  visible: boolean
  mode?: 'login' | 'register'
}>()

const isLogin = ref(props.mode !== 'register')
watch(() => props.mode, (val) => {
  if (val) isLogin.value = val !== 'register'
})
```

### Alternative: Use a shared store (Pinia)
For complex cross-component state, a Pinia store is cleaner than window events:
```ts
// stores/modal.ts
export const useModalStore = defineStore('modal', () => {
  const visible = ref(false)
  const mode = ref<'login' | 'register'>('login')
  function open(m: 'login' | 'register' = 'login') {
    mode.value = m
    visible.value = true
  }
  return { visible, mode, open }
})
```

## Element Plus Programmatic Component CSS

`unplugin-vue-components` with `ElementPlusResolver` only auto-imports CSS for components used **in templates**. Programmatic calls like `ElMessageBox.confirm()` and `ElMessage()` create components dynamically — their CSS is NOT auto-imported.

**Symptom**: `ElMessageBox` dialog appears in top-left corner, unstyled, no overlay. User sees raw HTML buttons with no proper layout.

**Fix**: Manually import CSS in `main.ts`:
```typescript
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-message.css'
```

**Rule**: Any Element Plus component used ONLY via programmatic API (not in `<template>`) needs manual CSS import. Common ones: `ElMessageBox`, `ElMessage`, `ElNotification`, `ElLoading`.

## Double /api in Production (Blank Page + 403)

**THE most common cause of "page blank + all API 403" after deployment.**

When `VITE_API_BASE_URL=/api` in `.env.production` AND API call paths already include `/api` (e.g., `http.get('/api/front/projects/list')`), the request URL becomes `/api/api/front/projects/list` — nginx proxies it to the backend, which has no controller for that path → 403.

**Diagnosis — MUST use real browser, not curl:**
```javascript
// puppeteer test — captures actual request URLs
page.on('response', resp => {
  if (resp.url().includes('/api/'))
    console.log(`${resp.status()} ${new URL(resp.url()).pathname}`);
});
```
If you see `/api/api/...` in the output, that's the bug.

**Fix:** Set `VITE_API_BASE_URL=` (empty string) in `.env.production` when nginx handles `/api/` proxying:
```
# .env.production
VITE_API_BASE_URL=
```

**Why curl misses it:** curl doesn't use the frontend's axios config. Only a real browser (or puppeteer) shows the actual request URLs constructed by the JS code.

**Rule:** After any production build, verify with puppeteer that API request paths have NO double prefix. One test catches this permanently.

## Duplicate Error Messages on Login Failure

When the axios interceptor shows `ElMessage.error(backendMessage)` AND the login component also shows `ElMessage.error('登录失败')`, the user sees TWO toasts. The fix: remove the component's error toast — the interceptor already handles it:

```vue
<script setup>
const handleLogin = async () => {
  try {
    const success = await userStore.login(loginForm)
    if (success) {
      ElMessage.success('登录成功')
      router.push(redirect)
    }
    // DON'T add else { ElMessage.error(...) } — interceptor already showed it
  } catch {
    // DON'T add ElMessage.error(...) — interceptor already showed it
  }
}
</script>
```

## API Data Not Loading (Empty Lists/Pages)

When a Vue3 page shows empty despite the backend returning data, the problem is often in the axios interceptor chain.

### Double-unwrap Pattern

The most subtle cause: **response interceptor already unwraps, then `request()` tries to unwrap again**.

**How it happens:**
1. Response interceptor returns `Promise.resolve(response.data.result)` — this changes what `axiosInstance.request()` resolves to
2. `request()` helper does `const res = await axiosInstance.request(config); return res.data` — but `res` is already the unwrapped result (not an AxiosResponse), so `res.data` is `undefined`
3. Component receives `undefined`, `data.records` throws, catch block swallows it → empty list

**Diagnosis:**
```bash
# Check if interceptor unwraps
grep 'response.data.result' src/utils/http/axios.ts
# Check if request() also accesses .data
grep 'res\.data' src/utils/http/axios.ts
# If BOTH exist, you have the double-unwrap bug
```

**Fix:** When the interceptor returns `response.data.result`, the `request()` helper must return `res as any` (not `res.data as T`):
```typescript
async function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  const res = await axiosInstance.request<T>(config)
  return res as any  // interceptor already unwrapped
}
```

**Verification:** Compare admin and front axios configs — they should use the same pattern. If one does `return res as any` and the other does `return res.data as T`, one is wrong.

### Token Refresh Double-Unwrap

The same double-unwrap bug also affects **token refresh logic**. When the interceptor calls `axiosInstance.post('/api/admin/auth/refreshToken', ...)`, the response goes through the interceptor chain and gets unwrapped. So `refreshRes` is already the result object (not an AxiosResponse).

**Symptom:** User is logged in but suddenly gets "请先登录" errors. Token was silently cleared.

**Bug pattern (two errors at once):**
```typescript
// WRONG — two bugs:
const refreshRes = await axiosInstance.post('/api/admin/auth/refreshToken', {
  token: currentToken           // BUG 1: wrong field name (backend expects 'refreshToken')
})
const newAccessToken = refreshRes.data.result  // BUG 2: double-unwrap → undefined
userStore.token = newAccessToken  // Sets token to undefined → clears localStorage!
```

**Fix:**
```typescript
const refreshRes: any = await axiosInstance.post('/api/admin/auth/refreshToken', {
  refreshToken: currentToken    // match backend DTO field name
})
const newAccessToken = refreshRes?.accessToken  // access correct property on unwrapped result
userStore.token = newAccessToken
```

**Why it's devastating:** `userStore.token = undefined` persists to localStorage via pinia-plugin-persistedstate. ALL subsequent requests lose their Authorization header.

**Checklist when debugging "user is logged in but API returns 401":**
1. `grep 'refreshRes\.data\.result' src/utils/http/axios.ts` — if found, that's the bug
2. Check refresh request body field name matches backend DTO (`refreshToken` not `token`)
3. Check localStorage: `JSON.parse(localStorage.getItem('bio_user'))?.token`
4. Check BOTH locations: response interceptor's `handleUnauthorized` AND request interceptor's proactive refresh

### Request Body Field Name Mismatch

When frontend sends `{message: text}` but backend reads `params.get("content")`, backend gets null → NPE or "内容不能为空".

**Diagnosis:** Compare frontend API call request body keys with backend `@RequestBody Map<String, Object>` field reads or DTO field names.

**Fix options:**
1. Fix frontend to match backend (preferred if backend has other consumers)
2. Fix backend to accept both: `params.get("content") != null ? ... : params.get("message")`
3. Use a typed DTO instead of `Map<String, Object>` — catches mismatches at compile time

### Direct API Test

When the page is empty but you suspect the backend is fine, test from the browser console:
```javascript
fetch('/api/front/projects/list?page=1&size=12').then(r => r.json()).then(d => console.log(d))
```
If this returns data but the page is empty, the bug is in the frontend data handling chain.

### Cross-Origin API Base URL

Check `.env.development` for `VITE_API_BASE_URL`. If it's `http://localhost:8080` (absolute), requests bypass the Vite proxy and may hit CORS issues. If it's `/api` (relative), the Vite proxy handles it.

### Suppressing ElMessage on Specific API Calls

When you want to handle errors in the component (e.g., show in a chat bubble instead of a toast), pass `silent: true` in the request config:

```typescript
// agentApi.ts
export function chat(data: ChatRequest) {
  return http.post<ChatResponse>('/api/front/agent/chat', data, { silent: true } as any)
}
```

The `silent` flag is checked in the response interceptor:
```typescript
if (!response.config.silent) {
  ElMessage.error(msg || '请求失败')
}
return Promise.reject(new Error(msg || '请求失败'))
```

The promise still rejects — the component's `catch` block handles the error display. Without `silent: true`, both the interceptor's toast AND the component's error message appear simultaneously.

### HMR Doesn't Reload Interceptor Changes

Vite HMR does NOT hot-reload changes to `axios.ts` interceptors. After modifying the request/response interceptor logic or token refresh code, the user must manually refresh (F5). The page will appear to use stale code — old bugs persist despite the file being saved.

**Rule**: After any edit to `src/utils/http/axios.ts`, tell the user to hard-refresh the page.

## Missing Dynamic Route — Blank Page on Card Click

**THE most common cause of "clicking a card/item shows a completely blank page".**

A `ProjectCard`, `PipelineCard`, or similar list-item component navigates on click:
```ts
function goToDetail() {
  router.push(`/projects/${props.project.id}`)
}
```
But the router only defines the LIST route (`/projects`), not the detail route (`/projects/:id`). Vue Router renders nothing for the unmatched path → blank page.

**Diagnosis:**
```bash
# 1. Find the click handler
grep -rn 'router.push.*\$\{' src/components/*Card*.vue
# 2. Check if the target route exists
grep -n "path: 'projects/" src/router/index.ts
# If only 'projects' exists but not 'projects/:id', that's the bug
```

**Fix — 2 parts (both required):**
1. Create the detail view (e.g., `views/project/ProjectDetailView.vue`)
2. Add the dynamic route in `router/index.ts`:
```ts
{
  path: 'projects/:id',
  name: 'ProjectDetail',
  component: () => import('@/views/project/ProjectDetailView.vue'),
  meta: { title: '项目详情' },
},
```

**Pitfall — route ordering:** The dynamic route `projects/:id` MUST come AFTER the static `projects` route. If placed before, Vue Router matches `/projects` as `:id = "projects"`. Vue Router v4 resolves static routes first, but explicit ordering prevents confusion.

**Pitfall — missing `v-if` guards:** The detail view must handle loading and not-found states. Without them, the template renders with `null` data → errors or empty content:
```vue
<template>
  <div v-loading="loading">
    <template v-if="project">
      <!-- detail content -->
    </template>
    <el-empty v-if="!loading && !project" description="项目不存在" />
  </div>
</template>
```

**Verification:** After fix, click a card from both the list page AND the home page (if both use the card component). Both paths must work.

## Vue Router Component Reuse — Stale Route Params

**THE most common cause of "clicking project A shows project B's data".**

Vue Router reuses the same component instance when navigating between routes that share the same component (e.g., `/projects/1` → `/projects/2`). A one-time assignment at setup like:

```ts
const projectId = Number(route.params.id)  // STALE after navigation!
```

captures the FIRST id and never updates. All API calls use the old id.

**Diagnosis:**
```bash
grep -n 'route\.params\.' <DetailView>.vue | grep -v computed | grep -v watch
# If you see bare `const x = route.params.xxx` (not computed/watch), that's the bug
```

**Fix — 3 parts:**
1. Make the param reactive:
```ts
const projectId = computed(() => Number(route.params.id))
```
2. Update ALL references to use `.value`:
```ts
await getProject(projectId.value)       // not projectId
await listFiles({ projectId: projectId.value })  // object shorthand breaks too
```
3. Add a `watch` to reload data on param change:
```ts
watch(() => route.params.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    // reset pagination
    pagination.page = 1
    // reload all data
    loadProject()
    loadAnalyses()
    // ... etc
  }
})
```

**Object shorthand trap:** `{ projectId }` in an object literal becomes `{ projectId: <stale-value> }`. Must change to `{ projectId: projectId.value }`.

**Pitfall — `reactive` captures value, not ref:** If you assign a computed ref into a reactive object:
```ts
const metaForm = reactive({ projectId, name: '' })  // projectId evaluated ONCE
```
The reactive captures the current VALUE, not the ref. Fix: use `projectId.value` in the reactive definition and sync it in the watch, or use a computed getter.

## SSE / Raw Fetch — Token Not Sent (Bypasses Axios Interceptor)

**THE most common cause of "用户已登录但 SSE/流式接口返回401".**

When an API call uses raw `fetch` (common for SSE/streaming endpoints like AI chat), it bypasses the Axios request interceptor that automatically attaches the `Authorization` header. The token must be read and attached manually.

### Root Cause Pattern

```typescript
// ❌ BAD — reads token once at call time, no refresh, stale read possible
export function chatStream(data, onToken, onDone, onError) {
  let token = ''
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) token = JSON.parse(stored).token || ''
  } catch {}
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  fetch('/api/front/agent/chat/stream', { method: 'POST', headers, body: JSON.stringify(data) })
    .then(...)
}
```

**Why it fails:**
1. **Pinia persistence timing**: `pinia-plugin-persistedstate` writes to localStorage asynchronously. After login, the Pinia store has the token immediately, but localStorage may lag by a microtask. If `chatStream` reads localStorage before the plugin flushes, it gets an empty token.
2. **No token refresh**: Axios interceptor transparently refreshes expired tokens on 401. Raw `fetch` has no such mechanism — it just fails.
3. **Stale token**: If the Axios interceptor refreshed the token (updating Pinia store), but localStorage hasn't synced yet, raw `fetch` reads the old token.

### Fix: Read from Pinia Store + Retry on 401

```typescript
import { useUserStore } from '@/stores/user'

function getAccessToken(): string {
  // Priority 1: Pinia store (real-time, always current)
  try {
    const store = useUserStore()
    if (store.token) return store.token
  } catch { /* store not initialized yet, fallback */ }
  // Priority 2: localStorage (persistent, may lag behind store)
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).token || ''
  } catch {}
  return ''
}

export function chatStream(data, onToken, onDone, onError) {
  const abortController = new AbortController()

  function doFetch(retryOn401 = true) {
    const accessToken = getAccessToken()
    const headers = { 'Content-Type': 'application/json' }
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`

    fetch('/api/front/agent/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal: abortController.signal,
    }).then(async (response) => {
      if (!response.ok) {
        // Retry once with fresh token on auth failure
        if ((response.status === 401 || response.status === 403) && retryOn401) {
          doFetch(false)  // re-read token from store (may have been refreshed by another request)
          return
        }
        onError(`HTTP ${response.status}`)
        return
      }
      // ... SSE stream parsing ...
    })
  }

  doFetch()
  return abortController
}
```

**Key points:**
- `getAccessToken()` reads from Pinia store FIRST (real-time), falls back to localStorage
- `doFetch(retryOn401)` retries once on 401/403 — handles the case where another Axios request triggered a token refresh between the first and second attempt
- The retry re-reads the token, so it picks up any refresh that happened in the meantime

### Diagnosis Checklist

When a user reports "logged in but SSE/agent/chat says 请先登录":

1. Check if the endpoint uses raw `fetch` vs Axios: `grep -rn 'fetch(' src/api/`
2. Check token source: does it read from localStorage only, or also from Pinia store?
3. Check if there's a 401 retry mechanism
4. Compare with Axios interceptor token reading logic in `src/utils/http/axios.ts`

### Also Applies To

- WebSocket connections with auth tokens
- `EventSource` (SSE GET) connections
- Any raw `XMLHttpRequest` or `fetch` call that needs authentication

## Pitfalls

- **`new Event()` vs `new CustomEvent()`**: Plain `Event` cannot carry payload. Use `CustomEvent` with `{ detail }` when you need to pass data (like mode, id, etc.).
- **Missing cleanup**: Always pair `addEventListener` with `removeEventListener` in `onUnmounted`. Without it, you get duplicate listeners on component re-mount (e.g., route changes).
- **TypeScript cast**: The `e: Event` parameter needs `(e as CustomEvent).detail` cast. No way around this.
- **write_file corrupts .vue files**: ALWAYS use `patch` tool for Vue SFC edits. `write_file` silently corrupts them.
- **md-editor-v3: extending built-in toolbar dropdowns.** The md-editor-v3 library's image button has a built-in dropdown with options like "上传图片", "添加链接", "裁剪上传". These are internal and not extensible via props. To add a custom option (e.g., "从素材库选择"), use DOM injection: after the editor renders, find the image dropdown's `<li>` list and append a new `<li>` element. Use `onMounted` + `nextTick` + `setTimeout` to ensure the DOM is ready. The injected `<li>` should match the existing items' class structure for consistent styling. This is fragile — if the library updates its DOM structure, the injection breaks. Prefer the library's official extension points (like `defToolbars` slot for custom toolbar buttons) when available.
- **`art-table` `selection` prop + manual `<el-table-column type="selection" />` = duplicate checkbox columns.** The custom `art-table` component accepts a `selection` boolean prop that automatically renders a checkbox column via `<el-table-column v-if="selection" type="selection" />` inside its template. If the consuming view ALSO includes `<el-table-column type="selection" />` inside its `<template #default>`, two identical checkbox columns appear. Fix: remove the manual column from the view — the prop handles it.
- **`watch(dialogVisible)` race condition with state cleanup.** When using `watch(dialogVisible)` to save/clear state on dialog close, a subtle race can occur: code that clears state (e.g., `clearDraft()`) runs synchronously, then `dialogVisible.value = false` triggers the watch which re-saves the state from the still-populated form. Even a `submitSuccess` flag pattern (`clearDraft(); submitSuccess = true; dialogVisible = false`) can fail because Vue's `flush: 'pre'` watch is asynchronous — the flag may or may not be visible depending on microtask ordering. **Reliable fix: remove the watch entirely.** Use explicit handlers: cancel button calls `handleCancel()` which saves then closes; submit success calls `clearDraft()` then closes. No watch, no race. This pattern applies to any "do X when dialog closes, but not if it closes because of Y" scenario.
- **el-image preview-src-list blocks click selection.** When using `<el-image>` inside a selectable grid (like an image picker), adding `:preview-src-list` makes clicking the image open the preview modal instead of triggering the parent's `@click` handler. Remove `preview-src-list` and `preview-teleported` to make clicks pass through to the parent element's click handler for selection behavior.
- **SSE/raw fetch missing Authorization header.** Any endpoint using raw `fetch` (not Axios) bypasses the request interceptor's automatic token attachment. The token must be read manually — and must be read from the Pinia store (real-time), not just localStorage (may lag behind due to `pinia-plugin-persistedstate` async flush). Also add a 401 retry: re-read token and retry once, since another Axios request may have refreshed it in the meantime. See the "SSE / Raw Fetch" section above for the full pattern.
- **WebSocket token storage key mismatch between admin and front.** Admin stores token as `localStorage.getItem('access_token')`, Front stores it inside `localStorage.getItem('bio_user')` as `{ token: "..." }`. When writing WebSocket code that reads token from localStorage, using the wrong key → token is always empty → WebSocket silently fails → "重新连接" button does nothing. Always check which key the current app uses by reading `stores/user.ts` or `utils/http/axios.ts`.

## Verification

After fixing, run:
```bash
cd <frontend-dir>
npx vue-tsc --noEmit   # TypeScript check
npm run build           # Full build
```

Also verify the event chain with a targeted script:
```bash
# Check dispatcher uses CustomEvent with detail
grep -q "new CustomEvent" <dispatcher>.vue
# Check listener exists in layout/parent
grep -q "addEventListener('event-name'" <parent>.vue
# Check cleanup
grep -q "removeEventListener" <parent>.vue
# Check prop passed to child
grep -q ':mode=' <parent>.vue
```
