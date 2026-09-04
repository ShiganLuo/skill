# Bioplatform Remote Deployment Patterns

## Architecture Overview

Bioplatform deploys to Aliyun server (39.97.180.240:20225) sharing infrastructure with the blog project:
- **Shared**: MySQL (blog_mysql:3306), Redis (blog_redis:6379), nginx-proxy (ports 80/443)
- **Network**: `blog_net` (Docker bridge, gateway 172.19.0.1)
- **Containers**: bioplatform-backend (8083:8080), bioplatform-front (3000:80), bioplatform-admin (3001:80)
- **Domains**: bio.shiganluo.top → front, bioadmin.shiganluo.top → admin

## nginx-proxy Shared Routing

nginx-proxy.conf routes HTTPS to containers by domain. Critical behaviors:

1. **Blog containers MUST be running** — nginx-proxy.conf references `blog_web`, `blog_backend` etc. If blog containers are down, `nginx -t` fails with `host not found in upstream "blog_web"` and the entire nginx-proxy stops working, taking bioplatform down too.

2. **DNS caching after container recreation** — After `docker-compose up -d --force-recreate`, container IPs change but nginx caches old DNS. **Must reload**: `docker exec nginx-proxy nginx -s reload`. This fails if blog containers are down (see #1).

3. **nginx-proxy also proxies `/api/`** — Both `bio.shiganluo.top` and `bioadmin.shiganluo.top` have `/api/` locations in nginx-proxy that go directly to `bioplatform-backend:8080`. This means API requests bypass the front/admin container nginx.

4. **Authorization header MUST be forwarded at EVERY layer** — When requests pass through nginx-proxy → app container nginx → backend, each layer needs `proxy_set_header Authorization $http_authorization;`. Without it, JWT tokens are silently dropped and all authenticated API calls return 403. This is because setting ANY `proxy_set_header` directive replaces ALL default forwarded headers. See `jwt-filter-and-frontend-deploy.md` for the full pattern.

## VITE_API_BASE_URL Double Path (CRITICAL)

When API paths already include `/api` prefix (e.g. `/api/front/projects/list`), setting `VITE_API_BASE_URL=/api` in `.env.production` causes axios to prepend it → `/api/api/front/projects/list` → 403.

**Fix**: `VITE_API_BASE_URL=` (empty) in `.env.production` for both front and admin.

## JwtAuthenticationFilter Whitelist Bug

Original code validated tokens on whitelisted paths if a token was present:
```java
if (isWhitelisted(requestUri) && !StringUtils.hasText(jwt)) { ... }
```
This means if the browser has a stale JWT in localStorage, even whitelisted paths (like login) fail with 403.

**Fix**: Whitelist paths should unconditionally permit:
```java
if (isWhitelisted(requestUri)) { filterChain.doFilter(request, response); return; }
```

## MySQL/Redis Port Binding

For security, bind MySQL and Redis to localhost only in docker-compose:
```yaml
ports:
  - "127.0.0.1:3308:3306"
  - "127.0.0.1:6380:6379"
```
Docker containers still reach each other via container names on `blog_net`.

## SSH Reverse Tunnels for Worker Nodes

Workers run on internal servers (e.g. c2: 120.26.95.112:20226). To expose to the gateway:

```bash
# On worker node
ssh -R 28081:127.0.0.1:18081 -p 20225 luosg@39.97.180.240 -N
```

**Limitation**: `-R` binds to 127.0.0.1 by default (GatewayPorts=no). Docker containers can't reach 127.0.0.1 on host.

**Workaround**: Use socat on the gateway to relay:
```bash
socat TCP-LISTEN:18081,bind=0.0.0.0,fork,reuseaddr TCP:127.0.0.1:28081 &
```

Then backend uses `http://172.19.0.1:18081` (Docker gateway IP = host).

**Note**: socat can't bind to a port already in use by the SSH tunnel. Use different ports for tunnel (28081) and socat (18081).

## Worker Health: JVM vs System Memory

`Runtime.getRuntime().freeMemory()` reports JVM heap, not system memory. For a 192-core machine with 500GB RAM, it reports ~88MB free.

**Fix**: Use `OperatingSystemMXBean`:
```java
com.sun.management.OperatingSystemMXBean os = 
    (com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
long totalMemGB = os.getTotalPhysicalMemorySize() / 1024 / 1024 / 1024;
long freeMemGB = os.getFreePhysicalMemorySize() / 1024 / 1024 / 1024;
```

## Server http_proxy Gotcha

The Aliyun server has `http_proxy=http://127.0.0.1:7890` set globally. All curl commands need `--noproxy '*'`:
```bash
curl --noproxy '*' -sf http://localhost:8083/api/...
```

## Deployment Script (remote_publish.sh)

Key points:
- Uses `docker-compose` (v1, hyphenated) on remote — NOT `docker compose`
- Uploads to `/home/luosg/bioplatform/` (not /tmp)
- Images exported as single .tar: `docker save backend front admin -o images.tar`
- After deployment: `docker exec nginx-proxy nginx -s reload`

## Database Schema Pitfalls

### operation_logs.method column too short

The `method` column in `operation_logs` stores the full class.method name (e.g. `com.bioplatform.controller.admin.AdminSystemController.updateConfig`). Default VARCHAR(16) is way too short.

**Error**: `Data truncation: Data too long for column 'method' at row 1`

**Fix**: `ALTER TABLE operation_logs MODIFY COLUMN method VARCHAR(500);`
Also update `database/bioplatform.sql` to match.

### Redis password must be in YAML, not just env var

Spring Boot environment variables like `SPRING_DATA_REDIS_PASSWORD` do NOT work for Redis password unless the `password` field exists in `application-prod.yml`. Without the YAML field, the env var is silently ignored and Lettuce tries to connect without authentication → connection hangs forever.

**Fix**: Add `password: "8978654"` directly in `application-prod.yml` under `spring.data.redis`:
```yaml
spring:
  data:
    redis:
      host: blog_redis
      port: 6379
      password: "8978654"
      timeout: 3000ms
```

The `timeout: 3000ms` prevents infinite hang on connection failure.

## SSH Command Pitfalls

- `nohup ... &` in SSH causes exit code 255 — use separate SSH calls or `background=true` in terminal tool
- `!` in bash triggers history expansion — use `set +H` or escape with `\\!`
- `scp` fails with "Received message too long" — use `cat file | ssh "cat > remote_file"` instead
- docker-compose v1 on remote: use `docker-compose` (hyphen), not `docker compose`
- Long heredocs in SSH can fail silently — use base64 encoding: `echo $B64 | base64 -d > file`
- `sed -i` on Docker-mounted files fails with "Device or resource busy" — edit the file on the host instead

## Selective Image Deployment (Skip Full Rebuild)

When only one service changed (e.g., admin frontend), skip the full `remote_publish.sh` which rebuilds ALL images including the slow Maven backend build.

### Steps (admin-only example)

```bash
# 1. Build only the changed image
docker build -t bioplatform-admin ./bioplatform-vue3/bioplatform-admin

# 2. Export only that image
docker save bioplatform-admin -o /tmp/bioplatform-admin.tar

# 3. Upload (pipe through SSH to avoid SCP "Received message too long")
cat /tmp/bioplatform-admin.tar | ssh -i ~/.ssh/aliyun -p 20225 luosg@39.97.180.240 \
  "cat > /home/luosg/bioplatform/bioplatform-admin.tar"

# 4. Remote: load, restart, verify
ssh -i ~/.ssh/aliyun -p 20225 luosg@39.97.180.240 "
  cd /home/luosg/bioplatform &&
  docker load -i bioplatform-admin.tar &&
  rm -f bioplatform-admin.tar &&
  docker-compose -f docker-compose-remote.yml up -d admin &&
  sleep 3 && docker-compose -f docker-compose-remote.yml ps
"

# 5. Clean up local
rm -f /tmp/bioplatform-admin.tar
```

### When to use
- Only frontend (admin/front) changed → build just that image (~26MB, fast)
- Only backend changed → build backend image (Maven build, slower)
- Multiple services changed → use full `remote_publish.sh`

### Time savings
- Full build: ~3-5 min (Maven + 3 Docker images)
- Admin-only: ~30s (npm build inside Docker + 26MB transfer)
- Front-only: ~30s (same)
- Backend-only: ~2-3 min (Maven + Docker)
