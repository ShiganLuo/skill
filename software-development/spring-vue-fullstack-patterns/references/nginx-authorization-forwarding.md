# nginx Authorization Header Forwarding

## The Problem

When using nginx as a reverse proxy for Spring Boot + Vue3 apps, authenticated API requests return 403/401 even though the browser sends a valid JWT token.

## Root Cause

nginx's `proxy_set_header` directive **overrides ALL default headers** when set. Only explicitly listed headers are forwarded. The `Authorization` header is silently dropped.

```nginx
# This config drops Authorization!
location /api/ {
    proxy_pass http://backend:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    # Authorization is NOT forwarded — it's not listed
}
```

## Fix

Always add `proxy_set_header Authorization $http_authorization;`:

```nginx
location /api/ {
    proxy_pass http://backend:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;  # REQUIRED
    proxy_read_timeout 300s;
}
```

## Multi-Layer Proxy Pitfall

When requests pass through multiple nginx proxies, EACH layer needs the Authorization forwarding:

```
Browser → nginx-proxy → container-nginx → backend
         ^ needs it    ^ needs it
```

Example: `bioadmin.shiganluo.top` → nginx-proxy → bioplatform-admin container nginx → bioplatform-backend. Both the nginx-proxy config AND the container's nginx.conf need `proxy_set_header Authorization $http_authorization;`.

## Debugging

If authenticated requests fail but unauthenticated (whitelisted) ones work:
1. Check if there's a proxy chain (nginx-proxy → container nginx → backend)
2. Verify `proxy_set_header Authorization` is present at EVERY layer
3. Test from inside the container: `docker exec <container> curl -H "Authorization: Bearer <token>" http://backend:8080/api/...`
4. If curl works inside but browser fails, the issue is in an outer proxy layer
