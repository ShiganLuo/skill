# JWT Proactive Token Refresh

## Problem

Reactive token refresh (waiting for HTTP 401 then refreshing) causes every expired token to produce a failed request. The user sees a brief error flash, or in worst case, the request silently fails.

## Solution: Proactive Refresh in Request Interceptor

Parse the JWT payload on the frontend **before** sending each request. If the token will expire within 5 minutes, refresh it proactively.

### Frontend: JWT Payload Parser

```ts
/** Parse JWT payload without signature verification (client-side only) */
function parseJwtPayload(token: string): { exp?: number } | null {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

/** Check if token will expire within the given milliseconds (default 5 min) */
function isTokenExpiringSoon(token: string, withinMs: number = 5 * 60 * 1000): boolean {
  const payload = parseJwtPayload(token)
  if (!payload?.exp) return true  // can't parse = treat as expired
  return payload.exp * 1000 - Date.now() < withinMs
}
```

### Frontend: Request Interceptor with Proactive Refresh

```ts
axiosInstance.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      // Proactive refresh: refresh before token expires
      if (isTokenExpiringSoon(token) && !config.url?.includes('/refreshToken')) {
        if (!isRefreshing) {
          isRefreshing = true
          try {
            const refreshToken = localStorage.getItem('refresh_token')
            if (refreshToken) {
              const refreshRes = await axios.post(`${baseURL}/api/admin/auth/refreshToken`, {
                refreshToken
              })
              const data = refreshRes.data
              if (data.code === 200) {
                localStorage.setItem('access_token', data.result.accessToken)
                localStorage.setItem('refresh_token', data.result.refreshToken)
                config.headers.Authorization = `Bearer ${data.result.accessToken}`
                // Release queued requests
                requests.forEach((cb) => cb(data.result.accessToken))
                requests = []
              }
            }
          } catch (e) {
            console.warn('Proactive token refresh failed, will retry on 401')
          } finally {
            isRefreshing = false
          }
        }
      }
      // Always use the latest token
      const latestToken = localStorage.getItem('access_token')
      if (latestToken) {
        config.headers.Authorization = `Bearer ${latestToken}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)
```

### Backend: Log Level for Expired Tokens

```java
public boolean validateToken(String token) {
    try {
        parseClaims(token);
        return true;
    } catch (ExpiredJwtException e) {
        log.debug("JWT token expired: {}", e.getMessage());  // DEBUG, not ERROR
        // ...
    }
}
```

Token expiration is **normal business flow**, not an error. Logging at ERROR clutters logs and alarms operators.

### Backend: isTokenExpiringSoon Utility (Optional)

For server-side proactive checks:

```java
public boolean isTokenExpiringSoon(String token, long withinMs) {
    try {
        Claims claims = parseClaims(token);
        Date expiration = claims.getExpiration();
        return expiration.getTime() - System.currentTimeMillis() < withinMs;
    } catch (ExpiredJwtException e) {
        return true;
    } catch (Exception e) {
        return true;
    }
}
```

## How It Works

1. **Before each request**, the interceptor parses the JWT payload (base64 decode, no signature check)
2. Checks `exp` claim against current time
3. If token expires within 5 minutes → refresh proactively
4. If proactive refresh fails → silently fall back to reactive refresh (401 handler)
5. The `isRefreshing` flag prevents multiple simultaneous refresh calls

## Two-Layer Defense

- **Layer 1 (Proactive)**: Request interceptor checks `exp` before sending → refreshes early
- **Layer 2 (Reactive)**: Response interceptor catches 401 → refreshes on failure

This ensures zero user-visible 401 errors in normal usage.

## Pitfalls

- **`isRefreshing` flag is critical**: Without it, N concurrent requests each trigger a refresh call.
- **Refresh token must be valid**: If the refresh token is also expired (7-day default), proactive refresh fails silently, and the next request triggers the reactive path which logs the user out.
- **Clock skew**: JWT `exp` is set by the server. If the client clock is off by more than the 5-minute window, proactive refresh may not trigger. The 5-minute buffer handles typical clock skew.
- **Don't parse JWT for every request if token is fresh**: The `isTokenExpiringSoon` check is cheap (one base64 decode), but you could cache the result with a TTL if performance is a concern.
