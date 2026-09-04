# WebSocket and Spring Boot Pitfalls

## WebSocket Reconnect Death Spiral (CRITICAL)

When implementing WebSocket reconnection, NEVER use `delay=0` for immediate reconnect. The pattern:
```
onclose → scheduleReconnect(immediate=true) → new WebSocket → fails → onclose → scheduleReconnect(true) → ...
```
creates an **infinite tight loop** that freezes the browser and causes white screen.

**Fix**: Always use exponential backoff starting from 500ms, with a max retry count:
```typescript
let reconnectDelay = 500
let reconnectCount = 0
const MAX_RECONNECT = 10

function scheduleReconnect() {
  if (reconnectCount >= MAX_RECONNECT) return
  reconnectCount++
  setTimeout(() => {
    connectWebSocket()
    reconnectDelay = Math.min(reconnectDelay * 2, 10000)
  }, reconnectDelay)
}

ws.onopen = () => {
  reconnectDelay = 500
  reconnectCount = 0
}
```

**Better alternative**: Don't auto-reconnect at all. Show a "连接已断开" bar with a manual reconnect button. Eliminates all reconnect complexity.

## WebSocket Heartbeat / Ping-Pong

WebSocket connections silently dropped by proxies/load balancers/firewalls. Implement heartbeat:
```typescript
ws.onopen = () => {
  heartbeatTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
  }, 25000)
}
```

Backend must respond:
```java
if ("ping".equals(type)) {
    session.sendMessage(new TextMessage("{\"type\":\"pong\"}"));
    return;
}
```

## WebSocket Token Storage Mismatch

WebSocket can't use HTTP Authorization header. Token must go in URL query param.

**Pitfall**: Admin and Front store tokens differently:
- Admin: `localStorage.getItem('access_token')`
- Front: `JSON.parse(localStorage.getItem('bio_user')).token`

Using the wrong key → token always empty → WebSocket silently fails.

## Spring Boot Bean Naming: `@EnableScheduling`

Spring Boot auto-configures a bean named `taskScheduler` when `@EnableScheduling` is present. Custom class `TaskScheduler` → same bean name → `BeanDefinitionOverrideException`.

**Fix**: Use unique name: `PipelineTaskDispatcher`, `WorkflowScheduler`, etc.

**Common collisions**: `taskScheduler` (@EnableScheduling), `taskExecutor` (@EnableAsync), `objectMapper` (Jackson).

## `@ConditionalOnProperty` Import Path

In `org.springframework.boot.autoconfigure.condition`, NOT `org.springframework.context.annotation`.

## Java `Map.of()` Null Values

`Map.of()` does NOT allow null → NPE. Use `HashMap` when values might be null.

## JWT Secret Format Mismatch Between Profiles (CRITICAL)

Different Spring profiles can use different JWT secret formats. If `application-prod.yml` uses Base64-encoded secrets while `application-docker.yml` uses plaintext, switching profiles causes **signature mismatch** — tokens generated with one profile fail validation in another.

**Symptom**: Login succeeds (returns token), but ALL subsequent authenticated requests return 403. Backend logs show: `Invalid JWT signature: JWT signature does not match locally computed signature`.

**Root cause**: `JwtTokenProviderUtil` tries Base64 decode first, falls back to UTF-8 bytes. A Base64 string decodes to different bytes than the same string treated as plaintext. Different bytes → different HMAC key → different signatures.

**Fix**: Use the SAME format in ALL profiles. Prefer plaintext:
```yaml
# application-prod.yml AND application-docker.yml
jwt:
  secret: "bioplatform-prod-secret-key-2024-at-least-32-chars"
```

**Verification**: After deploying, login AND then call an authenticated endpoint:
```bash
TOKEN=$(curl --noproxy '*' -sk -X POST .../api/admin/auth/login -d '...' | jq -r .result.accessToken)
curl --noproxy '*' -sk .../api/admin/auth/userInfo -H "Authorization: Bearer $TOKEN"
# 200 = OK, 403 = secret mismatch
```

## Database Schema Migration

When adding columns: update SQL file AND run ALTER TABLE on running database. Just updating the file does NOT apply to existing DBs.

## application-prod.yml Must Include Security Whitelist

When creating `application-prod.yml`, it's easy to forget the `security.jwt.whitelist` block that exists in `application-dev.yml`. Without it, ALL `/api/admin/**` endpoints require JWT — including `/api/admin/auth/login`. Result: login returns 403.

**Always copy the whitelist block from dev to prod:**
```yaml
security:
  jwt:
    whitelist:
      - /api/front/**
      - /api/admin/auth/login
      - /api/admin/auth/refreshToken
      - /api/admin/users/register
      - /swagger-ui.html
      - /swagger-ui/**
      - /v3/api-docs/**
      - /doc.html
```

**Verification**: After deploying, test login immediately:
```bash
curl -X POST https://host/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```
Empty response or 403 = missing whitelist.

## Git: Never Rewrite History

User explicitly forbids `git filter-branch` / `git rebase -i` / `BFG` to remove files from history. Use only `git rm` + commit, push. Rewriting history causes force-push issues and lost untracked files. If a file needs removing: `git rm <file>`, commit, push.

## Never Commit Sensitive Config Files

`application-prod.yml` contains DB passwords, JWT secrets. **Always add it to `.gitignore`** before committing. Use environment variables (`${DB_PASS:default}`) so the file only has defaults, not real credentials.

User correction: "你不提交不就行了吗" — when sensitive data is in a file, don't rewrite history or overcomplicate. Just gitignore it:
```bash
echo "path/to/application-prod.yml" >> .gitignore
git rm --cached path/to/application-prod.yml
git commit -m "chore: gitignore sensitive config"
```

Also applies to: database passwords in SQL seed files, API keys in any config.

## Test Things Yourself — Don't Ask User to Test

When deploying or debugging, always test endpoints yourself via `curl` before asking the user to check. User explicitly said "你自己实际测试一下不就知道了吗".

Test the full chain yourself:
```bash
# Page loads
curl -sf --max-time 5 https://domain/ | grep "<title>"
# Static assets
curl -sf --max-time 5 -o /dev/null -w "%{http_code}" "https://domain/assets/xxx.js"
# API
curl -sf --max-time 5 https://domain/api/front/site-config
# Login
curl -sf --max-time 5 -X POST https://domain/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

On remote servers, always use `--noproxy '*'` to bypass server-side proxy misconfiguration.

## Respect User's Environment

Never re-specify what the user has already configured. If the system JDK is set to 17, don't add `JAVA_HOME` overrides or `maven.compiler.release` workarounds. If the user says "no sudo", don't suggest `apt install` or `docker run`. Constraints stated by the user are absolute.

## Deploy Scripts: Use PATH, Not JAVA_HOME

Never hardcode `$JAVA_HOME/bin/java` in deploy scripts. Users universally have `java` in PATH but JAVA_HOME is often unset. Use `JAVA="java"` and `mvn` directly. If JAVA_HOME is needed (rare), detect it: `java -XshowSettings:properties 2>&1 | grep java.home`.

## Docker Multi-Project Network Sharing

When deploying multiple projects to one server sharing MySQL:
- **Join the existing Docker network** (`--network blog_net`) and use container name as hostname (`blog_mysql:3306`)
- `host.docker.internal` does NOT work reliably on Linux Docker — avoid it
- Use environment variables (`SPRING_DATASOURCE_URL`) to override config without baking credentials into the image
- Wait for MySQL readiness before importing SQL — check with `docker exec blog_mysql mysql -uroot -pPASS -e 'SELECT 1'`
- **Dockerfiles go in each sub-project directory** (NOT in a central `deploy/` folder). nginx-proxy.conf goes at project root.
- Full deployment workflow: see `references/docker-compose-remote-deploy.md`

### Never Use Individual `docker run` Commands

User explicitly corrected this. Always use `docker-compose-remote.yml` for server deployment, matching the blog project pattern. Individual `docker run` commands are:
- Hard to reproduce
- Can't express dependencies
- Diverge from the project's compose-based workflow

### `docker-compose` vs `docker compose`

Older servers use `docker-compose` (hyphenated, standalone binary). Newer Docker uses `docker compose` (plugin). Check which is available:
```bash
docker-compose version 2>&1 || docker compose version 2>&1
```
The `remote_publish.sh` script should handle both with fallback.

### Server Proxy Misconfiguration

Many servers have `http_proxy`/`https_proxy` env vars pointing to a dead proxy (e.g., `127.0.0.1:7890`). This causes `curl` to fail silently. Always use `--noproxy '*'` for localhost/container requests:
```bash
curl --noproxy '*' -sf http://localhost:8083/api/...
```

### BCrypt Password Hash Pitfalls

SQL seed files often contain placeholder hashes. Never trust them — verify:
```bash
# Check what password the hash actually represents
python3 -c "import bcrypt; print(bcrypt.checkpw(b'admin123', b'\$2a\$10\$...'))"
```
- `$2a$` and `$2b$` are both valid BCrypt prefixes, Spring's `BCryptPasswordEncoder` handles both
- Generate correct hash: `python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(10)).decode())"`
- After deploying, ALWAYS test login immediately: `curl -X POST .../api/admin/auth/login -d '{"username":"admin","password":"admin123"}'`

### application-prod.yml Must Include Security Whitelist

When creating `application-prod.yml`, it's easy to forget the `security.jwt.whitelist` block that exists in `application-dev.yml`. Without it, ALL `/api/admin/**` endpoints require JWT — including `/api/admin/auth/login`. Result: login returns 403.

**Always copy the whitelist block from dev to prod:**
```yaml
security:
  jwt:
    whitelist:
      - /api/front/**
      - /api/admin/auth/login
      - /api/admin/auth/refreshToken
      - /api/admin/users/register
      - /swagger-ui.html
      - /swagger-ui/**
      - /v3/api-docs/**
      - /doc.html
```

**Verification**: After deploying, test login immediately:
```bash
curl -X POST https://host/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```
Empty response or 403 = missing whitelist.

## `sed` Insert Pitfall

Using `sed -i 'Na\\...'` for multi-line inserts often corrupts syntax (misplaced braces, wrong indentation). Prefer Python script or `write_file` for inserting blocks into structured files (TypeScript, Vue SFC). `sed` is fine for single-line replacements only.

## Documentation Style Preferences

- **Don't compare obvious alternatives**. If the choice is clear (e.g., SSE vs WebSocket for LLM streaming), just state the reason. Don't create comparison tables or dedicated "vs" sections — the user considers this redundant.
- **Use project-appropriate naming**. Don't name directories `blog/` for a bioinformatics platform. Use names that reflect the project identity (e.g., `docs/tech/` not `docs/blog/`).
- **Keep docs concise**. Focus on "why we chose this" not "why not the other options".

## Low-Memory Server Deployment

When deploying to servers with < 2GB RAM:
- **Docker overhead matters** — each container adds ~50-100MB overhead. On a 1.8G server running blog + MySQL + nginx, there's no room for another container.
- **Check `free -h` before deploying** — if available memory < 300MB, Docker deployment will OOM.
- **Solutions**: (1) Upgrade RAM, (2) Run JAR directly without Docker, (3) Stop non-essential services.
- **MySQL OOM**: On low-memory servers, importing large SQL files can OOM MySQL. Import table-by-table or use `--max-allowed-packet=256M`.
- **Always wait for MySQL readiness** after container restart — `sleep 15` + loop check `SELECT 1` before any DB operation.
