# JWT Filter & Frontend Deployment Fixes

## JWT Whitelist Filter Critical Fix

Whitelist paths must unconditionally permit without token validation. If browser has stale token in localStorage (from previous deployment with different JWT secret), the filter tries to validate the old token, fails, and returns 403 — even on whitelisted paths like `/api/admin/auth/login`.

```java
// CORRECT: whitelist paths always pass through
if (isWhitelisted(requestUri)) {
    filterChain.doFilter(request, response);
    return;
}
String jwt = extractTokenFromRequest(request);
```

## VITE_API_BASE_URL Double /api

If API paths already include `/api` prefix, `VITE_API_BASE_URL=/api` causes double path: `/api/api/...`.

**Rule**: If all API calls use absolute paths like `http.get('/api/front/projects/list')`, set `VITE_API_BASE_URL=` (empty) in `.env.production`.

## Admin nginx.conf Must Have API Proxy

Admin container's nginx.conf needs explicit `/api/` and `/ws/` proxy locations to the backend. Without them, direct access to admin container (port 3001) fails. The nginx-proxy handles this for domain access, but the config should be self-contained.

## nginx proxy_set_header Authorization (CRITICAL)

**Nginx does NOT auto-forward Authorization when you set ANY `proxy_set_header`.** Setting explicit `proxy_set_header` in a location block REPLACES ALL default forwarded headers. Only the explicitly listed headers are forwarded — Authorization is silently dropped.

**Multi-layer proxy chain**: When requests pass through nginx-proxy → app container nginx → backend, EACH layer needs explicit Authorization forwarding:

```nginx
# nginx-proxy.conf (layer 1)
location /api/ {
    proxy_pass http://bioplatform-backend:8080;
    proxy_set_header Authorization $http_authorization;  # REQUIRED
    ...
}

# bioplatform-admin/nginx.conf (layer 2)
location /api/ {
    proxy_pass http://backend:8080;
    proxy_set_header Authorization $http_authorization;  # REQUIRED
    ...
}
```

**Symptom**: Login works (whitelisted, no token needed), but ALL authenticated API calls return 403. The token is valid in localStorage, browser DevTools shows it in the request, but backend never receives it.

**Why it's hard to diagnose**: The 403 comes from Spring Security (not nginx), so backend logs show nothing. The token appears correct in browser. The config "looks fine" because other headers (Host, X-Real-IP) are forwarded correctly.

**Rule**: Every `location` block that proxies to a backend requiring JWT auth MUST include `proxy_set_header Authorization $http_authorization;`.

## Login Error Deduplication

Axios interceptor already shows backend error messages (e.g., "用户不存在", "密码错误"). LoginView should NOT add redundant "登录失败，请检查用户名和密码". Remove the `else` and `catch` error toasts from login handler.
