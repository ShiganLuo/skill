# Spring Security AuthenticationEntryPoint Pattern

## Problem

Spring Security's default behavior for unauthenticated requests returns HTTP 403 with HTML content. Frontend axios interceptors expect JSON, so the error handler can't parse the response properly — the user sees a generic "请求失败" with no useful diagnostic info.

## Solution: Custom AuthenticationEntryPoint

Add a bean that returns structured JSON with diagnostic info:

```java
@Bean
public AuthenticationEntryPoint authenticationEntryPoint() {
    return (HttpServletRequest request, HttpServletResponse response,
            AuthenticationException authException) -> {
        response.setContentType("application/json;charset=UTF-8");
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);

        String tokenHeader = request.getHeader("Authorization");
        String message;
        if (tokenHeader == null || tokenHeader.isBlank()) {
            message = "未提供认证令牌，请先登录";
        } else if (!tokenHeader.startsWith("Bearer ")) {
            message = "认证头格式错误，应为: Bearer <token>";
        } else {
            message = "认证令牌无效或已过期，请重新登录";
        }

        Map<String, Object> body = new HashMap<>();
        body.put("code", 401);
        body.put("message", message);
        body.put("path", request.getRequestURI());

        new ObjectMapper().writeValue(response.getOutputStream(), body);
    };
}
```

Configure in SecurityFilterChain:
```java
.exceptionHandling(ex -> ex.authenticationEntryPoint(authenticationEntryPoint()))
```

## Why This Matters for Debugging

Without this, when JWT auth fails:
- Browser shows `403 Forbidden` (HTML) — no useful info
- Backend logs show nothing (Spring Security handles it silently)
- User can't tell if token is missing, expired, or malformed

With this:
- Browser shows `{"code":401,"message":"认证令牌无效或已过期，请重新登录","path":"/api/admin/projects/create"}`
- Frontend axios interceptor can parse and display the message
- Immediately tells you the root cause

## Required Imports

```java
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
```

## Related Pitfall: nginx Authorization Header

If the 401 says "未提供认证令牌" but the browser shows the token in the request header, the issue is likely nginx stripping the Authorization header. See `jwt-filter-and-frontend-deploy.md` for the `proxy_set_header Authorization` pattern.
