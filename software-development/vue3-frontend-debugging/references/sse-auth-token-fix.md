# SSE Auth Token Fix — bioplatform Agent API

## Problem

`chatStream()` in `agentApi.ts` used raw `fetch` and read token from `localStorage.getItem('bio_user')` directly. After login, Pinia store had the token but `pinia-plugin-persistedstate` hadn't flushed to localStorage yet → empty Authorization header → backend returns "请先登录后再使用 AI 助手".

After page refresh, localStorage was hydrated from persistent storage → token present → works.

## Key Files

- `bioplatform-front/src/api/agentApi.ts` — SSE chat stream function
- `bioplatform-front/src/stores/user.ts` — Pinia store with `persist: { key: 'bio_user', paths: ['token', 'refreshToken', 'userInfo'] }`
- `bioplatform-front/src/utils/http/axios.ts` — Axios interceptor with `getStoredToken()` + 401 refresh logic
- `bioplatform-springboot/.../controller/front/FrontAgentController.java` — checks `LoginUserHolder.getCurrentUserId()`
- `bioplatform-springboot/.../filter/JwtAuthenticationFilter.java` — sets `LoginUserHolder` from Bearer token

## Fix Applied

```typescript
// Added to agentApi.ts
import { useUserStore } from '@/stores/user'

function getAccessToken(): string {
  try {
    const store = useUserStore()
    if (store.token) return store.token
  } catch {}
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).token || ''
  } catch {}
  return ''
}

// chatStream wrapped in doFetch(retryOn401) for retry on 401/403
```

## Why Pinia Store First

- Pinia store `token.value` is updated synchronously in `userStore.login()`
- `pinia-plugin-persistedstate` uses a watcher that fires asynchronously (next tick)
- Axios interceptor also reads from localStorage via `getStoredToken()`, but it works because:
  - Other API calls happen after login completes and persistence flushes
  - The interceptor has 401→refresh→retry logic that compensates
- Raw `fetch` has no such retry → must read from store directly
