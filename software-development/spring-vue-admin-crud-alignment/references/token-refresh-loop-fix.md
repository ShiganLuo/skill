# Token Refresh Loop Fix — Vue3 Axios Interceptor

## Problem
Infinite token refresh loop in Vue3 admin panel. The interceptor's401 handler triggers `refreshToken`, which fails, calls `logOut()`, but `logOut()` uses `setTimeout(300ms)` to clear the token. During those 300ms, new requests fire with the stale token, get 401, and trigger another refresh.

## Root Cause Chain
1. Initial request returns business code 401 (not HTTP 401)
2. Interceptor calls `/admin/users/refreshToken`
3. Refresh fails → `catch` block calls `logOut()` → `logOut()` schedules token clearing for 300ms later
4. `finally { isRefreshing = false }` runs synchronously
5. New request fires (component `onMounted`, watcher, etc.) with old token still in memory
6. Gets 401 again → `isRefreshing` is false → starts new refresh cycle
7. Repeat forever

## Fix: `refreshFailed` Flag Pattern

### Step 1: Add flag alongside isRefreshing
```ts
let isRefreshing = false
let refreshFailed = false   // NEW
let requests: ((token: string | null) => void)[] = []
```

### Step 2: Block re-entry at top of 401 handler
```ts
} else if (code === ApiStatus.unauthorized) {
    const userStore = useUserStore()
    // NEW: refresh already failed, reject immediately
    if (refreshFailed) {
        return Promise.reject(new Error('登录已失效'))
    }
    const originalRequest = response.config
```

### Step 3: Set flag in refreshToken-401 handler
```ts
if (originalRequest.url?.includes('/admin/users/refreshToken')) {
    refreshFailed = true    // NEW — must be BEFORE logOut
    isRefreshing = false
    requests.forEach(cb => cb(null))  // drain queue
    requests = []
    userStore.logOut()
    return Promise.reject(new Error('Refresh Token 失效'))
}
```

### Step 4: Set flag in catch block, remove finally
```ts
} catch (err) {
    refreshFailed = true    // NEW — must be BEFORE logOut
    isRefreshing = false
    requests.forEach(cb => cb(null))  // drain queue
    requests = []
    userStore.logOut()
    ElMessageBox.alert('登录状态已过期，请重新登录', '系统提示', { type: 'warning' })
    return Promise.reject(err)
}
// NO finally block — isRefreshing is set explicitly in each branch
```

### Step 5: Reset flag on successful login (request interceptor)
```ts
(request: InternalAxiosRequestConfig) => {
    const { accessToken } = useUserStore()
    if (accessToken) {
        if (refreshFailed) refreshFailed = false  // NEW: reset on re-login
        request.headers.set({
            Authorization: `Bearer ${accessToken}`
        })
    }
    return request
}
```

## Key Ordering Constraints
- `refreshFailed = true` MUST come BEFORE `logOut()` — otherwise the 300ms window allows re-entry
- `requests.forEach(cb => null)` MUST come BEFORE `logOut()` — drain the queue to reject pending requests
- `isRefreshing = false` MUST NOT be in a `finally` block — it must be set AFTER the queue is drained and flag is set

## Related Pitfall
The `Authorization` header line in the request interceptor can get corrupted by `write_file` on .ts files — backticks become `***`. If you see `Authorization: *** ${accessToken}` in the file, use Python byte-level replacement to fix:
```python
with open(path, "rb") as f:
    raw = f.read()
raw = raw.replace(b'Authorization: *** ${accessToken}`', b"Authorization: `Bearer ${accessToken}`")
with open(path, "wb") as f:
    f.write(raw)
```
