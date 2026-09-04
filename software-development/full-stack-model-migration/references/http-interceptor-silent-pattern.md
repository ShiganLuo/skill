# HTTP Interceptor Silent Pattern

## Problem

When a backend returns a business error (e.g., 404 "博客设置不存在"), the Axios response interceptor shows an `ElMessage` toast BEFORE rejecting the promise. Calling `.catch()` on the API call catches the rejection but the toast has already appeared.

## Root Cause

```javascript
// Interceptor fires first, THEN rejects
else {
  ElMessage({ message: msg, type: 'warning' })  // ← Toast shown here
  return Promise.reject(new Error(msg))          // ← .catch() handles this
}
```

## Solution: Two-Layer Fix

### Layer 1: Extend AxiosRequestConfig (utils/http/index.ts)

```typescript
// Add after imports
declare module 'axios' {
  interface AxiosRequestConfig {
    silent?: boolean
  }
}
```

### Layer 2: Check silent flag in interceptor

```javascript
// In response interceptor, before showing ElMessage
else if (code === ApiStatus.SERVER_ERROR) {
  if (!response.config.silent) {
    ElMessage({ message: msg, type: 'error' })
  }
  return Promise.reject(new Error(msg))
} else {
  if (!response.config.silent) {
    ElMessage({ message: msg, type: 'warning' })
  }
  return Promise.reject(new Error(msg))
}
```

### Layer 3: Use in API methods

```typescript
// In API file (e.g., configApi.ts)
static getFrontBackground(userId: number | string) {
  return request.get<FrontBackground>({
    url: `/front/settings/getFrontBackground/${userId}`,
    silent: true  // ← Suppress interceptor toast
  }).catch(() => {
    // Graceful fallback on rejection
    return { code: 404, result: null } as any;
  })
}
```

## When to Use

- Blog settings APIs that return 404 when user hasn't initialized (expected state)
- Public-facing APIs that gracefully handle missing data
- Any API where "not found" is a valid, non-error response

## When NOT to Use

- Authentication/authorization errors (user should see these)
- Server errors (500) that indicate real problems
- Validation errors (400) that the user needs to fix
