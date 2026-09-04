# JWT Whitelist & Deployment Pitfalls

## Whitelist Over-Matching (BOTH admin and front)

Spring Security whitelist with `/api/front/**` matches `/api/front/auth/userInfo` which REQUIRES auth. The JwtAuthenticationFilter skips validation, `LoginUserHolder` is never set, `getUserInfo()` returns null userId → 404 "用户不存在".

**Symptom**: Login succeeds (token returned) but `fetchUserInfo()` immediately fails → user sees "登录成功" then "用户不存在" then logout.

**Fix**: Use explicit paths in BOTH `SecurityConfig.java` AND `application-*.yml`:
```yaml
whitelist:
  - /api/front/auth/login
  - /api/front/auth/register
  - /api/front/auth/sendEmailCode
  - /api/front/projects/**
  - /api/front/pipelines/**
  - /api/front/site-config
  - /api/admin/auth/login
  - /api/admin/auth/refreshToken
```

## JwtAuthenticationFilter Whitelist Behavior

Filter should ALWAYS skip validation for whitelisted paths, regardless of token presence. Old code only skipped when no token was sent — invalid token in localStorage caused 403 on whitelisted endpoints.

```java
// CORRECT: whitelist always skips
if (isWhitelisted(requestUri)) {
    filterChain.doFilter(request, response);
    return;
}
String jwt = extractTokenFromRequest(request);

// WRONG: only skips when no token
String jwt = extractTokenFromRequest(request);
if (isWhitelisted(requestUri) && !StringUtils.hasText(jwt)) {
    filterChain.doFilter(request, response);
    return;
}
```

## VITE_API_BASE_URL Double /api

If `.env.production` has `VITE_API_BASE_URL=/api` AND source code paths start with `/api/`, axios combines them into `/api/api/...` → 403. Fix: set `VITE_API_BASE_URL=` (empty).

## remote_publish.sh: docker-compose v1 vs v2

Remote server may have `docker-compose` (v1 standalone) not `docker compose` (v2 plugin). The script's remote commands must use `docker-compose` not `docker compose`.

## nginx-proxy DNS Caching

After `docker-compose up -d --force-recreate`, container IPs change. nginx caches old DNS → routes go to wrong containers (e.g., front shows admin content). Must `docker exec nginx-proxy nginx -s reload` after container recreation.

**Cascading failure**: If blog containers are down, nginx-proxy config references `blog_web` → nginx fails to start/reload → ALL domains return 000. Always start blog containers before reloading nginx.

## Duplicate Error Toasts

Axios interceptor shows backend error message. Component catch block also shows error → double toast. Fix: remove the catch block's ElMessage, keep only the interceptor's.
