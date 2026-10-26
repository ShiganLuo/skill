# Docker Network Hostname Collision

When multiple Docker Compose projects share the same network, generic service names create DNS ambiguity.

## Symptom

JWT authentication returns **non-standard response format** with `path` field:
```json
{"path":"/api/admin/users/refreshToken","code":401,"message":"未提供认证令牌，请先登录"}
```

But direct calls to the correct backend return standard format:
```json
{"code":400,"message":"Token解析失败","result":null}
```

Key diagnostic: the message "未提供认证令牌" doesn't exist in YOUR codebase — it's from the OTHER backend.

## Root Cause

```bash
# Two containers resolve to the same hostname:
docker exec blog_admin getent hosts backend
# 172.19.0.4  backend  ← bioplatform-backend (WRONG)
# 172.19.0.7  backend  ← blog_backend (CORRECT)
```

nginx `proxy_pass http://backend:8080` randomly picks one IP → half the requests go to the wrong backend.

## Detection

```bash
# Check if hostname resolves to multiple IPs
docker exec <container> getent hosts <hostname>

# Check what's in the shared network
docker network inspect blog_net --format '{{range .Containers}}{{.Name}} {{end}}'
```

## Fix

Use unique container names instead of generic service names:

```nginx
# Before (ambiguous):
proxy_pass http://backend:8080;

# After (unambiguous):
proxy_pass http://blog_backend:8080;
```

## Prevention

When adding a new Docker Compose project to an existing network:
1. **Never reuse generic service names** like `backend`, `frontend`, `db`, `redis`
2. **Prefix all service names** with the project name: `blog_backend`, `bio_backend`
3. **Verify DNS resolution** after deployment: `getent hosts <service_name>`
4. **Check for shared networks** before deploying: `docker network ls` and `docker network inspect`
