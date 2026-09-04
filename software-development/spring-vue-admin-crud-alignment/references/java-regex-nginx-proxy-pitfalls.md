# Java Regex Escaping & Nginx Double-Proxy Pitfalls

## Java Regex Escaping in String Literals

In Java source code, regex patterns inside `Pattern.compile("...")` require careful backslash handling:

| Java Source | Actual String | Regex Meaning |
|-------------|---------------|---------------|
| `\\d` (2 backslashes) | `\d` | Digit ✓ |
| `\\\\d` (4 backslashes) | `\\d` | Literal backslash + `d` ✗ |
| `\\.` (2 backslashes) | `\.` | Literal dot ✓ |
| `\\\\.` (4 backslashes) | `\\.` | Literal backslash + `.` ✗ |

**Common symptom**: `UrlNormalizeUtil.stripUrlPrefix()` silently fails because the port regex doesn't match `:9007`. The full URL stays in the database. When `MinioResponseAdvice` prepends the prefix again, you get double URLs like:
```
http://127.0.0.1:9007http://localhost:9007/my-bucket/xxx.png
```

**Debug method**: Use `Pattern.compile(...)` with a test string:
```java
Pattern p = Pattern.compile("^(https?:)?//([a-zA-Z0-9.-]+|\\d{1,3}(\\.\\d{1,3}){3})(?::\\d{1,5})?");
Matcher m = p.matcher("http://localhost:9007/my-bucket/xxx.png");
System.out.println(m.find()); // should print true
System.out.println(m.group()); // should print http://localhost:9007
```

## Nginx Double-Proxy Authorization Header Loss

When requests flow through two nginx proxy layers:
```
nginx-proxy → app-nginx → backend
```

The Authorization header can be lost if the inner proxy doesn't explicitly forward it.

**Root cause**: When a proxy `location` block has explicit `proxy_set_header` directives, nginx only sends those specific headers (plus a few defaults). In double-proxy setups, the inner proxy may not forward the Authorization header.

**Fix**: Add to the inner proxy's `location` block:
```nginx
proxy_set_header Authorization $http_authorization;
```

**Symptom**: Backend logs "请求未携带accessToken" even though frontend is logged in and the outer proxy forwards correctly.

## Dev Whitelist `/api/admin/**` Breaks Authenticated Endpoints

Having `/api/admin/**` in the JWT whitelist causes ALL admin endpoints to skip JWT validation. The JWT filter passes the request through, but `SecurityContextHolder` has no authentication.

When service-layer code calls `getCurrentUserId()` (reads from `SecurityContextHolder`), it returns null → `ApiResponse.error(UNAUTHORIZED, "请先登录")`.

**Debug log shows**: "白名单匹配成功" but API still returns 401.

**Fix**: Remove the wildcard. Only whitelist specific public endpoints:
```yaml
whitelist:
  - /api/admin/users/login
  - /api/admin/users/register
  - /api/admin/users/captchaLogin
  - /api/admin/util/get-captcha
  - /api/front/**    # public frontend endpoints
  # NOT: /api/admin/**
```

**Why it happens**: Developers add `/api/admin/**` during development for convenience, then forget to remove it. The prod config usually has the correct whitelist.
