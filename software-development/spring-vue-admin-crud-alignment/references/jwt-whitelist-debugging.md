# JWT Whitelist Debugging

Session: 2026-08-19. Token refresh failed silently because refresh endpoint wasn't whitelisted.

## Problem

User reported "auto-refresh token mechanism is broken". The frontend interceptor correctly detected 401 responses and attempted token refresh, but the refresh request itself was blocked by Spring Security.

## Root Cause

In `application-docker.yml`, the whitelist had wrong paths:

```yaml
# WRONG - these paths don't match any controller
- /api/admin/users/login
- /api/admin/users/refreshToken

# CORRECT - actual controller paths
- /api/admin/auth/login
- /api/admin/auth/refreshToken
```

The refresh endpoint `/api/admin/auth/refreshToken` was NOT in the whitelist, so Spring Security returned HTTP 401 for the refresh request. The frontend interceptor detected this as "refresh token failed" and logged the user out.

## How to Diagnose

1. Check which Spring profile is active: `SPRING_PROFILES_ACTIVE` in docker-compose.yml
2. Read the whitelist in that profile's `application-*.yml`
3. Compare whitelist paths against actual controller `@RequestMapping` paths
4. Common mismatch: `/api/admin/users/...` vs `/api/admin/auth/...`

## How to Fix

Update the whitelist in the active profile to match actual controller paths:

```yaml
security:
  jwt:
    whitelist:
      - /api/front/**
      - /api/admin/auth/login
      - /api/admin/auth/refreshToken
      - /api/admin/users/register
      # ... other paths
```

## Verification

After fixing, verify:
1. `mvn compile` passes
2. Restart the backend container
3. Login and wait for token to expire (or manually expire it)
4. Verify the refresh request succeeds (check browser Network tab)
5. Verify user stays logged in

## Prevention

When adding new auth endpoints, always add them to the whitelist in ALL active profiles (dev, docker, prod). The whitelist paths must match the controller's `@RequestMapping` exactly.
