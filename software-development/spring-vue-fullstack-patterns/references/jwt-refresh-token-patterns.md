# JWT Refresh Token Patterns (Vue3 Frontend)

## Refresh Token vs Access Token (CRITICAL)

The frontend must store BOTH tokens separately. A common bug: only storing `accessToken` and sending it as the refresh token.

**Symptom**: Token "expires" every hour even though refresh token should last 7+ days.

**Root cause**: Login returns `{accessToken, refreshToken}` but frontend only saves `accessToken`. When refreshing, the frontend sends `accessToken` as `refreshToken`. The backend validates it (it's a valid JWT), but after 1 hour the access token expires → refresh fails.

**Fix** — Store both tokens:
```typescript
// stores/user.ts
const token = ref<string>('')        // access token
const refreshToken = ref<string>('')  // refresh token — SEPARATE!

async function login(params) {
  const data = await loginApi(params)
  token.value = data.accessToken
  refreshToken.value = data.refreshToken || ''  // ← MUST store this
}

// persist both
persist: {
  key: 'bio_user',
  paths: ['token', 'refreshToken', 'userInfo'],
}
```

```typescript
// utils/http/axios.ts — use refreshToken for refresh requests
function getStoredRefreshToken(): string {
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).refreshToken || ''
  } catch {}
  return ''
}

// In handleUnauthorized:
const storedRefreshToken = getStoredRefreshToken()
const refreshRes = await axios.post('/api/auth/refreshToken', {
  refreshToken: storedRefreshToken  // ← NOT the access token
})
```

## Token Expiry Auto-Logout

JWT tokens have an `exp` claim. Parse it client-side and set a timer to auto-logout. Without this, the user stays "logged in" on the page until they make an API request that returns 401.

```typescript
let _logoutTimer: ReturnType<typeof setTimeout> | null = null

function _startExpiryCheck() {
  _stopExpiryCheck()
  if (!token.value) return
  try {
    const base64Url = token.value.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(base64))
    if (payload.exp) {
      const msLeft = payload.exp * 1000 - Date.now()
      if (msLeft <= 0) { logout(); return }
      _logoutTimer = setTimeout(() => logout(), msLeft + 10000)  // +10s buffer
    }
  } catch {}
}

function _stopExpiryCheck() {
  if (_logoutTimer) { clearTimeout(_logoutTimer); _logoutTimer = null }
}
```

Call `_startExpiryCheck()`:
- After successful login
- On store initialization if token already exists (page refresh with persisted token)

## Logout Deduplication

Multiple concurrent 401 responses can trigger multiple logout API calls. Each calls `userStore.logout()`, which calls `logoutApi()`. Result: 3+ logout requests to the server.

```typescript
let _loggingOut = false

async function logout() {
  if (_loggingOut) return  // ← dedup guard
  _loggingOut = true
  _stopExpiryCheck()
  try {
    await logoutApi()
  } catch { /* ignore */ }
  token.value = ''
  refreshToken.value = ''
  userInfo.value = null
  localStorage.removeItem('bio_user')
  _loggingOut = false
}
```

## Admin vs Front Token Storage

| Aspect | Admin (bioplatform-admin) | Front (bioplatform-front) |
|--------|--------------------------|---------------------------|
| Storage | `localStorage('access_token')` + `localStorage('refresh_token')` | `localStorage('bio_user')` JSON (pinia-plugin-persistedstate) |
| Token read | `localStorage.getItem('access_token')` | `JSON.parse(localStorage.getItem('bio_user')).token` |
| Refresh token read | `localStorage.getItem('refresh_token')` | `JSON.parse(localStorage.getItem('bio_user')).refreshToken` |

The admin frontend already had correct refresh token handling. The bug was only in the front frontend.

## Request Interceptor Proactive Refresh — RACE CONDITION (CRITICAL)

**NEVER put proactive token refresh logic in the request interceptor.** It causes concurrent requests to each trigger independent refresh attempts.

### The Bug Pattern

```typescript
// DANGEROUS — request interceptor with proactive refresh
axiosInstance.interceptors.request.use(
  async (config) => {
    const token = getToken()
    if (token && isTokenExpiringSoon(token)) {
      if (!isRefreshing) {
        isRefreshing = true
        const res = await axios.post('/api/refreshToken', { refreshToken })
        // update tokens...
        isRefreshing = false
      }
    }
    config.headers.Authorization = `Bearer ${getToken()}`
    return config
  }
)
```

**Why it fails:** The request interceptor has NO queue mechanism. When multiple requests fire concurrently (e.g., page refresh with multiple `onMounted` hooks):
1. Request A's interceptor sees token expiring → sets `isRefreshing = true` → starts refresh (async)
2. Request B's interceptor runs immediately (JS is single-threaded but the `await` in A suspends it)
3. Request B checks `isRefreshing` — if A's `await` hasn't resolved yet, B sees `true` and skips (good)
4. BUT if A's refresh completes before B's interceptor runs, `isRefreshing` is back to `false` → B starts ANOTHER refresh
5. Worse: Request B may proceed with the OLD token (before A's refresh stored the new one), get a 401, then the response interceptor ALSO tries to refresh → duplicate refresh attempts

### The Fix

**Remove all proactive refresh logic from the request interceptor.** The request interceptor should ONLY attach the token:

```typescript
// CORRECT — request interceptor only attaches token
axiosInstance.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  }
)
```

**All token refresh goes through the response interceptor's 401 handler**, which HAS proper queueing:

```typescript
// Response interceptor — has isRefreshing + requests queue
if (code === 401 && !originalRequest._retry) {
  originalRequest._retry = true
  return doRefreshToken(originalRequest)  // queue-based, deduplicates
}
```

`doRefreshToken()` uses `isRefreshing` flag + `requests` array to queue concurrent 401s. Only the first 401 triggers the actual refresh; all others wait in the queue and retry with the new token.

### Symptom

"Every time I refresh the page after being idle for a while, I see exactly two failed requests." — Two concurrent onMounted API calls both trigger independent refresh attempts.

### Rule

- Request interceptor: attach token only, never refresh
- Response interceptor: handle 401 with queue-based `doRefreshToken()`
- Remove `isTokenExpiringSoon()` / `parseJwtPayload()` helper functions if they're only used by the request interceptor's proactive refresh
