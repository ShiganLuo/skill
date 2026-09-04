# Docker Compose Remote Deployment Pattern

When deploying to a server that already runs other projects (e.g., a blog), use `docker-compose-remote.yml` to share infrastructure.

## File Structure (at project root)

```
project/
├── docker-compose.yml           # Local dev (own MySQL/Redis)
├── docker-compose-remote.yml    # Server deploy (shared MySQL)
├── nginx-proxy.conf             # nginx reverse proxy config (append to existing)
├── remote_publish.sh            # One-click deploy script
├── bioplatform-springboot/Dockerfile
├── bioplatform-vue3/bioplatform-front/Dockerfile
└── bioplatform-vue3/bioplatform-admin/Dockerfile
```

**NEVER create a `deploy/` subdirectory** for these files. User explicitly corrected this — it's redundant when each sub-project already has its Dockerfile.

## docker-compose-remote.yml Template

```yaml
services:
  backend:
    image: bioplatform-backend
    container_name: bioplatform-backend
    restart: always
    ports:
      - "8083:8080"
    environment:
      SPRING_PROFILES_ACTIVE: prod
      SPRING_DATASOURCE_URL: jdbc:mysql://blog_mysql:3306/bioplatform?useUnicode=true&characterEncoding=utf-8&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false
      SPRING_DATASOURCE_USERNAME: root
      SPRING_DATASOURCE_PASSWORD: <password>
      TZ: Asia/Shanghai
    volumes:
      - bioplatform-uploads:/app/uploads
    networks:
      - blog_net

  front:
    image: bioplatform-front
    container_name: bioplatform-front
    restart: always
    ports:
      - "3000:80"
    depends_on:
      - backend
    networks:
      - blog_net

  admin:
    image: bioplatform-admin
    container_name: bioplatform-admin
    restart: always
    ports:
      - "3001:80"
    depends_on:
      - backend
    networks:
      - blog_net

networks:
  blog_net:
    external: true

volumes:
  bioplatform-uploads:
    name: bioplatform-uploads
```

Key points:
- `external: true` for the shared network — created by the other project's compose
- Environment variables override application-prod.yml without baking credentials into the image
- Port mapping avoids conflicts: 8083 (backend), 3000 (front), 3001 (admin)

## nginx-proxy Shared Configuration

When the server has an existing nginx-proxy container:
1. **Append** bioplatform server blocks to the existing nginx-proxy.conf
2. **Never create a separate config** — it conflicts
3. Add bio domains to the HTTP->HTTPS redirect server_name list
4. SSL wildcard *.domain.top matches blog.domain.top but NOT admin.bio.domain.top (two levels). Use bioadmin.domain.top instead.
5. After updating: `docker exec nginx-proxy nginx -t && docker restart nginx-proxy`

## remote_publish.sh Pattern

1. Build JAR locally
2. Build Docker images locally
3. docker save | gzip -> tar.gz
4. Transfer to server via SSH pipe (NOT scp — see pitfall below)
5. Upload docker-compose-remote.yml
6. SSH: gunzip -> docker load -> docker-compose -f docker-compose-remote.yml up -d

### CRITICAL: SCP Fails When Remote Shell Prints Output

If the remote shell produces any output on non-interactive sessions (e.g., `proxy off` from .bashrc, motd, etc.), SCP's protocol breaks:
```
scp: Received message too long 1886547832
scp: Ensure the remote shell produces no output for non-interactive sessions.
```

**Fix**: Use SSH pipe instead of scp:
```bash
# WRONG — breaks if remote shell prints anything
scp -P 20225 /tmp/image.tar.gz user@host:/tmp/

# CORRECT — pipe through SSH, works regardless of shell output
cat /tmp/image.tar.gz | ssh -p 20225 user@host "cat > /tmp/image.tar.gz"

# One-liner: save, compress, transfer, load, deploy
docker save bioplatform-admin:latest | gzip | ssh -p 20225 user@host \
  "gunzip -c | docker load && cd ~/bioplatform && docker-compose -f docker-compose-remote.yml up -d admin"
```

The one-liner avoids writing the tar.gz to disk on the remote server entirely.

### CRITICAL: NEVER Clone Repo or Build on Remote Server

**Always build locally, then upload the image.** Never:
- `git clone` the repo on the remote server
- Build Docker images on the remote server
- Pull new code on the remote server

Why: the remote server's running image may be from an older code state that works with its `docker-compose-remote.yml` config. Pulling latest code and rebuilding can introduce config mismatches (missing env vars, new dependencies, changed profiles) that break the running service. The user was extremely frustrated when this happened — the service went down for no reason related to the actual change.

**Correct workflow for any backend/frontend change:**
1. Make changes locally
2. `docker build` locally
3. `docker save | gzip | ssh ... "gunzip -c | docker load && docker-compose ... up -d <service>"`
4. Verify the service started: `ssh aliyun "docker logs <container> --tail 5"`

### CRITICAL: NEVER Patch JARs Inside Running Containers

Never try to `docker cp` a JAR out, modify it with `zip`/`sed`, and copy it back. The `zip -f` (freshen) command can corrupt the JAR's central directory, causing Spring Boot to fail silently or throw cryptic errors. This approach is fragile and error-prone.

**Even for a single XML file change**, rebuild the full image locally and upload. The build is fast (cached layers) and reliable.

### Transferring Only Changed Images

Don't transfer all images every time. If only the admin frontend changed:
```bash
docker save bioplatform-admin:latest | gzip | ssh ... "gunzip -c | docker load && docker-compose ... up -d admin"
```
This saves significant transfer time (26MB admin vs 733MB backend).

## Docker Compose Command Compatibility

Older servers: `docker-compose` (hyphenated, standalone binary)
Newer Docker: `docker compose` (plugin, no hyphen)
Check with: `docker-compose version 2>&1 || docker compose version 2>&1`

## Backend Search Params Must Be Wired End-to-End

When adding search/filter fields to a Vue3 admin form, verify the full chain:
1. **Frontend** sends params via `listProjects({ page, size, ...searchForm })`
2. **Controller** must have `@RequestParam(required = false)` for each search field
3. **Service** must pass them through to the mapper
4. **Mapper XML** must have `<if test="...">` blocks for optional filters

Common bug: frontend sends `name` and `organism` but controller only accepts `page`/`size` → search silently ignored, returns unfiltered results.

When modifying a mapper method signature (adding params), grep for ALL callers — service impl, tests, other controllers — to avoid compile errors.

## MySQL Readiness

Always wait for MySQL before importing SQL or starting backend:
```bash
for i in $(seq 1 20); do
    docker exec blog_mysql mysql -uroot -pPASS -e 'SELECT 1' >/dev/null 2>&1 && break
    sleep 2
done
```

On low-memory servers, MySQL gets OOM-killed frequently. Always check it's alive first.
