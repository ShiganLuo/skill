# JWT Refresh Token vs Access Token Pitfall

## Symptom
User gets logged out every hour instead of every week.

## Root Cause
Front-end sends `accessToken` (1h expiry) as `refreshToken` for refresh requests. After 1 hour the accessToken expires → refresh fails → user must re-login.

## The Bug Pattern

```typescript
// WRONG — stores only accessToken, sends it as refreshToken
const token = ref('')
// Login:
token.value = data.accessToken
// Refresh:
const refreshRes = await axios.post('/api/auth/refreshToken', {
  refreshToken: currentToken  // This IS the accessToken!
})
```

## The Fix

```typescript
// CORRECT — store both tokens separately
const token = ref('')        // access token (1h)
const refreshToken = ref('') // refresh token (7d+)

// Login handler:
token.value = data.accessToken
refreshToken.value = data.refreshToken || ''

// Persist both:
persist: {
  key: 'bio_user',
  paths: ['token', 'refreshToken', 'userInfo'],
}

// Read refreshToken from localStorage:
function getStoredRefreshToken(): string {
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) {
      const parsed = JSON.parse(stored)
      return parsed.refreshToken || ''
    }
  } catch { /* ignore */ }
  return ''
}

// Axios interceptor — use refreshToken for refresh:
const storedRefreshToken = getStoredRefreshToken()
if (!storedRefreshToken) {
  throw new Error('No refresh token')
}
const refreshRes = await axios.post('/api/auth/refreshToken', {
  refreshToken: storedRefreshToken  // NOT the accessToken
})
```

## Backend Behavior
- Refresh endpoint (`POST /api/auth/refreshToken`) validates the token
- Returns a NEW accessToken but the SAME refreshToken
- RefreshToken expiry is fixed at login time (never refreshed)

## Diagnostic
Check localStorage `bio_user`:
```javascript
JSON.parse(localStorage.getItem('bio_user'))
// Should have: { token: "eyJ...", refreshToken: "eyJ...", userInfo: {...} }
// If refreshToken is missing or same as token → bug
```

## Key Difference from Blog Project
The blog project stores tokens differently:
- Admin: `localStorage('access_token')` and `localStorage('refresh_token')` separately
- Front: `localStorage('bio_user')` with pinia-plugin-persistedstate

The bioplatform front-end initially only stored `token` (accessToken) in the persisted state, missing `refreshToken` entirely.
