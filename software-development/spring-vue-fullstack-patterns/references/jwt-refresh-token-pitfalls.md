# JWT Refresh Token Pitfalls

## Refresh Token Not Stored (Front-end)

**Bug**: Login response returns `{accessToken, refreshToken, userInfo}`. If the front-end only stores `accessToken` (e.g., `token.value = data.accessToken`) and discards `refreshToken`, then when the interceptor refreshes, it sends the ACCESS token as the refresh token. The backend validates it (it's a valid JWT), but it has1-hour expiry instead of7-day. Result: user gets logged out every hour.

**Fix**: Store refreshToken separately in Pinia store AND localStorage:

```typescript
// In store login():
token.value = data.accessToken
refreshToken.value = data.refreshToken || ''

// In persist config:
persist: { key: 'bio_user', paths: ['token', 'refreshToken', 'userInfo'] }

// Add getStoredRefreshToken() to axios.ts:
function getStoredRefreshToken(): string {
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) { return JSON.parse(stored).refreshToken || '' }
  } catch { }
  return ''
}

// In handleUnauthorized and proactive refresh:
const storedRefreshToken = getStoredRefreshToken()
const refreshRes = await axiosInstance.post('/api/admin/auth/refreshToken', {
  refreshToken: storedRefreshToken  // NOT getStoredToken()
})
```

**Note**: Admin front-end (`bioplatform-admin`) already stores refresh token correctly as `localStorage.getItem('refresh_token')`. Only the public front-end (`bioplatform-front`) had this bug.

## Token Expiry Auto-Logout

If the user stays on the page without making API requests, the token can expire silently. There's no timer to proactively log out.

**Fix**: Parse JWT `exp` claim on login and set a `setTimeout`:

```typescript
let _logoutTimer: ReturnType<typeof setTimeout> | null = null

function _startExpiryCheck() {
  _stopExpiryCheck()
  if (!token.value) return
  try {
    const payload = JSON.parse(atob(token.value.split('.')[1]))
    if (payload.exp) {
      const msLeft = payload.exp * 1000 - Date.now()
      if (msLeft <= 0) { logout(); return }
      _logoutTimer = setTimeout(() => logout(), msLeft + 10000)
    }
  } catch {}
}

// Call on login and on store initialization (if token exists)
```

## Logout Deduplication

Multiple concurrent401 responses can trigger multiple `userStore.logout()` calls, each sending a logout API request.

**Fix**: Use a `_loggingOut` flag:

```typescript
let _loggingOut = false
async function logout() {
  if (_loggingOut) return
  _loggingOut = true
  // ... clear token, call logout API ...
  _loggingOut = false
}
```
