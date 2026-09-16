---
name: spring-security-jwt
description: Use for JWT authentication and token refresh in Spring Boot.
tags: [java, spring-boot, security, jwt]
---

# Spring Security JWT Patterns

Patterns for Spring Security 6.x + JWT authentication in Spring Boot 3.x projects.

## Filter Chain Architecture

```
Request → JwtAuthenticationFilter → UsernamePasswordAuthenticationFilter → ... → FilterSecurityInterceptor → Controller
```

Key rules:
- `JwtAuthenticationFilter` extends `OncePerRequestFilter`, runs BEFORE `UsernamePasswordAuthenticationFilter`
- If the filter calls `filterChain.doFilter()`, the request continues to authorization and controller
- If the filter returns WITHOUT calling `filterChain.doFilter()`, the request is terminated — no authorization check runs
- `@RestControllerAdvice` / `@ExceptionHandler` only catches exceptions from the DispatcherServlet, NOT from the filter chain

## AuthenticationEntryPoint

Without a custom `AuthenticationEntryPoint`, Spring Security's default handler returns non-standard format (`{timestamp, status, error, path, message}`). Must wire explicitly:

```java
// SecurityConfig.java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http,
                                               JwtAuthenticationFilter jwtFilter,
                                               CustomAuthenticationEntryPoint entryPoint) throws Exception {
    http
        // ...
        .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
        .exceptionHandling(e -> e.authenticationEntryPoint(entryPoint));
    return http.build();
}
```

The entry point should return standard `ApiResponse` format with HTTP 200 (business code in body):

```java
@Component
public class CustomAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest req, HttpServletResponse res, AuthenticationException e) 
            throws IOException {
        res.setContentType("application/json; charset=UTF-8");
        ApiResponse<Void> body = ApiResponse.error(401, "认证令牌无效或已过期，请重新登录");
        res.getWriter().write(new ObjectMapper().writeValueAsString(body));
        res.getWriter().flush();
    }
}
```

**Why HTTP 200 with business code 401?** Frontend HTTP interceptors typically check `validateStatus` for 2xx. If the backend returns HTTP 401, the response goes to the error handler (which may lack refresh-token logic). Keeping HTTP 200 ensures the response reaches the success handler where the refresh-token flow lives.

## JWT Filter: Catch ALL Exceptions

Any uncaught exception in the JWT filter (e.g., `loadUserByUsername()` throwing `UsernameNotFoundException`) leaks past the filter to `ExceptionTranslationFilter`, which calls `AuthenticationEntryPoint`. This bypasses your standard error format.

**Fix**: Wrap the entire filter body in try-catch:

```java
@Override
protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
        throws ServletException, IOException {
    for (String uri : whiteListUris) {
        if (requestUri.startsWith(uri.replace("/**", ""))) {
            chain.doFilter(request, response);
            return;
        }
    }

    try {
        String authHeader = request.getHeader("Authorization");
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            // ... token parsing, validation, authentication
        } else {
            ResponseUtil.sendErrorResponse(response, ResultCodeEnum.UNAUTHORIZED, "请求未携带accessToken");
            return;
        }
    } catch (Exception e) {
        logger.error("JWT过滤器异常: {}", e.getMessage(), e);
        ResponseUtil.sendErrorResponse(response, ResultCodeEnum.UNAUTHORIZED, "认证令牌无效或已过期，请重新登录");
        return;
    }

    chain.doFilter(request, response);
}
```

**Common leak paths**:
- `loadUserByUsername()` throws `UsernameNotFoundException` (user deleted but token still valid)
- `validateToken()` throws unexpected runtime exception
- `claims.get("type", String.class)` returns null causing NPE

## ResponseUtil: HTTP Status vs Business Code

`ResponseUtil.sendErrorResponse()` intentionally does NOT set HTTP status (the `response.setStatus()` line is commented out). HTTP status stays 200; business error code (401/400/etc.) is in the JSON body. This is by design — keeps protocol layer (HTTP) separate from business layer (ApiResponse.code).

## Frontend Token Refresh: Both Success AND Error Handlers

The admin frontend's `validateStatus: (status) => status >= 200 && status < 300` means:
- HTTP 200 + business code 401 → **success handler** → refresh token logic runs ✓
- HTTP 401 → **error handler** → no refresh token logic → shows error ✗

If the backend might return HTTP 401 (nginx proxy, Spring Security default handler, load balancer), the error handler MUST also have refresh-token logic:

```typescript
(error) => {
    const status = error.response?.status
    const code = error.response?.data?.code
    if (status === 401 || code === 401) {
        if (!isRefreshing) {
            isRefreshing = true
            return axiosInstance.post('/admin/users/refreshToken', { refreshToken })
                .then(res => { /* retry original request */ })
                .catch(() => { /* logout */ })
        } else {
            return new Promise(/* queue request */)
        }
    }
    // ... normal error handling
}
```

## Pitfalls

1. **AuthenticationEntryPoint not wired**: `@Component` alone is NOT enough. Must be explicitly wired in `SecurityConfig` via `.exceptionHandling()`.
2. **Filter catches token errors but not user-load errors**: The `parseToken()` try-catch only catches token parsing. `loadUserByUsername()` throwing is a separate code path that needs its own catch (or the global catch-all).
3. **Whitelist bypass**: If `/api/admin/**` is in the whitelist, ALL admin endpoints skip JWT filter → `SecurityContext` is empty → `getCurrentUserId()` returns null → 401.
4. **`response.getWriter().flush()` doesn't commit**: `flush()` sends buffered data but doesn't commit the response (status code + headers). Use `response.flushBuffer()` to fully commit.
5. **Docker network hostname collision**: If nginx proxies to a generic name like `backend`, and multiple Compose projects share the same network, requests randomly go to the wrong backend. The wrong backend returns a different response format (with `path` field). Fix: use unique names like `blog_backend`. See `references/docker-network-hostname-collision.md`.
