# Remote VPS Deployment Workflow

## Architecture

Local dev machine builds Docker images, exports as tar archives, SCPs to remote VPS, which loads and runs them.

```
[local] docker compose build
         ↓
[local] docker save → .tar files
         ↓
[local] cat .tar | ssh host "cat > /tmp/.tar"  (or scp if shell is clean)
         ↓
[remote] docker load ← .tar files
         ↓
[remote] docker-compose -f docker-compose-remote.yml up -d
         ↓
[remote] restart nginx-proxy (SSL termination)
```

## File Layout on Remote

```
~/app/
├── docker-compose-remote.yml   # no build: directives, image: only
├── remote_publish.sh           # load + up + restart nginx
├── blog_web.tar
├── blog_admin.tar
├── blog_backend.tar
├── blog.sql                    # DB init (first deploy only)
├── redis.conf
├── nginx-proxy.conf            # SSL termination + reverse proxy
└── database/                   # persistent volumes (mysql/, redis/data/, minio/data/)
```

## docker-compose-remote.yml Differences from Local

| Aspect | Local | Remote |
|--------|-------|--------|
| Image source | `build: ./path` | `image: blog_xxx` (loaded from tar) |
| Spring profile | `SPRING_PROFILES_ACTIVE=dev` | `SPRING_PROFILES_ACTIVE=prod` |
| MySQL password | dev password | prod password |
| Redis password | dev password | must match `redis.conf` requirepass |
| MinIO password | local password | must match `MINIO_ROOT_PASSWORD` |
| Port mapping | `80:80`, `8081:80` | may differ (e.g. `8081:80`, `8082:80`) |
| nginx-proxy | not present | separate container with SSL certs |

## Pitfalls

1. **No build in remote.sh** → stale images deployed. Always `docker compose build` before `docker save`.

2. **Config password drift** — 4 places to keep in sync for Redis alone:
   - `application-dev.yml` spring.data.redis.password
   - `application-prod.yml` spring.data.redis.password
   - `redis.conf` requirepass
   - (none needed in docker-compose env if Spring reads from YAML)

3. **MinIO 3-way sync** — MinIO container `MINIO_ROOT_PASSWORD` + backend env `MINIO_SECRET_KEY` + `application-prod.yml` minio.secretKey.

4. **nginx-proxy as separate container** — not part of docker-compose-remote.yml, managed manually with `docker run`. Must be on the same Docker network (`--network blog_net`). Must be restarted after compose changes if it depends on container DNS resolution.

5. **Browser favicon cache** — after deploying new favicon, users may see the old one. The `setFavicon()` function adds `?v=<timestamp>` for cache-busting on dynamic favicons, but the static `<link rel="icon">` in index.html has no cache-betting. Solution: browser hard-refresh (Ctrl+Shift+R) or wait for cache expiry.

## Selective Image Rebuild (One Service Changed)

When only ONE service changed (e.g., backend mapper XML fix, frontend CSS tweak), rebuild ONLY that service:

```bash
# 1. Build only the changed image locally
docker build -t bioplatform-backend ./bioplatform-springboot

# 2. Save + compress
docker save bioplatform-backend | gzip > /tmp/bioplatform-backend.tar.gz

# 3. Transfer via SSH pipe (NOT scp — remote .bashrc has output)
cat /tmp/bioplatform-backend.tar.gz | ssh aliyun "cat > /tmp/bioplatform-backend.tar.gz"

# 4. Load on remote
ssh aliyun "docker load < /tmp/bioplatform-backend.tar.gz && rm /tmp/bioplatform-backend.tar.gz"

# 5. Restart only that service
ssh aliyun "cd ~/bioplatform && docker-compose -f docker-compose-remote.yml up -d --force-recreate backend"
```

This is faster and lower-risk than rebuilding all images. Even for a single XML file change, ALWAYS rebuild the image — never try to patch the JAR in-place.

## Anti-Patterns (NEVER DO THESE)

1. **NEVER `git clone` on remote and `docker build` there.** The remote server doesn't have the same code state as local. Cloning pulls latest code which may have different dependencies/config than the running image. Result: container crash loop (missing beans, unresolved placeholders, etc.). ALWAYS build locally first.

2. **NEVER patch a JAR in-place with `zip -f`.** Extracting a fat JAR, modifying a file, and `zip -f`-ing it back corrupts the archive (CRC mismatch in central directory). ALL backend requests fail. Even for a single XML mapper change, rebuild the full image.

3. **NEVER add environment variables to "fix" issues caused by a bad rebuild.** If the old image worked with the existing `docker-compose-remote.yml` but the new image doesn't, the problem is the new image (different code), not missing env vars. Roll back to the old image instead of patching the compose file.

## Single-Container Deploy (No docker-compose on Remote)

When the remote server doesn't need a full compose stack (e.g., MySQL is shared or external), deploy as a single container:

```bash
# Local: build image
docker build -t bioplatform-backend:latest .

# Local: export (compress with gzip for faster transfer)
docker save bioplatform-backend:latest | gzip > /tmp/bioplatform-backend.tar.gz

# Local: upload (use SSH pipe if remote shell has output)
cat /tmp/bioplatform-backend.tar.gz | ssh -i ~/.ssh/key -p PORT user@host "cat > /tmp/bioplatform-backend.tar.gz"

# Remote: load (decompress on the fly)
gunzip -c /tmp/bioplatform-backend.tar.gz | docker load
docker run -d --name bioplatform-backend \
    --restart unless-stopped \
    -p 8083:8080 \
    --add-host=host.docker.internal:host-gateway \
    -v bioplatform-uploads:/app/uploads \
    bioplatform-backend:latest
```

Key points:
- `--add-host=host.docker.internal:host-gateway` lets container reach host services (MySQL, Redis)
- Application YAML uses `host.docker.internal:PORT` for DB/Redis connections
- Use `host.docker.internal:3308` when MySQL runs in another Docker container on the host with port mapping
- `-v bioplatform-uploads:/app/uploads` persists uploaded files across container restarts
- Pick a port not in use (e.g., 8083) — check `docker ps` and `ss -tlnp` first

## One-Click Deploy Script Pattern

For projects with single-container deploy, create a `deploy.sh` at project root:

```bash
#!/bin/bash
# Commands: build, deploy, restart, logs, status
set -e

SERVER_USER="user"
SERVER_IP="1.2.3.4"
SERVER_PORT="22"
SSH_KEY="$HOME/.ssh/key"
SSH_CMD="ssh -i $SSH_KEY -p $SERVER_PORT ${SERVER_USER}@${SERVER_IP}"
SCP_CMD="scp -i $SSH_KEY -P $SERVER_PORT"
IMAGE_NAME="project-backend"
CONTAINER_NAME="project-backend"

build_jar() {
    cd bioplatform-springboot && mvn clean package -q -DskipTests && cd ..
}
build_image() {
    build_jar && docker build -t ${IMAGE_NAME}:latest .
}
export_upload() {
    docker save ${IMAGE_NAME}:latest | gzip > /tmp/${IMAGE_NAME}.tar.gz
    cat /tmp/${IMAGE_NAME}.tar.gz | ssh -i $SSH_KEY -p $SERVER_PORT ${SERVER_USER}@${SERVER_IP} "cat > /tmp/${IMAGE_NAME}.tar.gz"
}
remote_deploy() {
    ${SSH_CMD} bash -s << 'EOF'
gunzip -c /tmp/bioplatform-backend.tar.gz | docker load
docker stop bioplatform-backend 2>/dev/null; docker rm bioplatform-backend 2>/dev/null
docker run -d --name bioplatform-backend --restart unless-stopped \
    -p 8083:8080 --add-host=host.docker.internal:host-gateway \
    -v bioplatform-uploads:/app/uploads bioplatform-backend:latest
EOF
}
deploy_all() { build_image && export_upload && remote_deploy; }

case "${1:-help}" in
    build) build_image ;;
    deploy) deploy_all ;;
    restart) ${SSH_CMD} "docker restart ${CONTAINER_NAME}" ;;
    logs) ${SSH_CMD} "docker logs -f --tail 50 ${CONTAINER_NAME}" ;;
    status) ${SSH_CMD} "docker ps --filter name=${CONTAINER_NAME}" ;;
esac
```

Pitfalls:
- Always `docker compose build` or `docker build` BEFORE `docker save` — stale images get deployed otherwise
- `chmod +x deploy.sh` after creation
- Docker build pulling base images can be very slow in China (~200KB/s). Use domestic mirrors in `/etc/docker/daemon.json`
- The script should NOT hardcode `JAVA_HOME` — use `java` and `mvn` from PATH directly

## Spring Environment Variable Override

When sharing a Docker image between environments (dev server vs prod server), use Spring Boot environment variables to override YAML config at `docker run` time:

```bash
docker run -d --name backend \
    -e SPRING_PROFILES_ACTIVE=prod \
    -e SPRING_DATASOURCE_URL='jdbc:mysql://blog_mysql:3306/bioplatform?...' \
    -e SPRING_DATASOURCE_USERNAME=root \
    -e SPRING_DATASOURCE_PASSWORD=secret \
    image-name:latest
```

Spring Boot converts `SPRING_DATASOURCE_URL` → `spring.datasource.url` automatically. This avoids baking credentials into the image.

## Server `http_proxy` Pitfall

Some servers have `http_proxy` environment variable set (e.g., `http://127.0.0.1:7890` for a local proxy). If the proxy isn't running, `curl` commands fail with "Connection refused". Fix: use `curl --noproxy '*'` for local requests, or unset the proxy.

**Detection**: `curl -v http://localhost:8083/` — if it shows "Trying 127.0.0.1... port 7890", the proxy is active.

## SCP "Received message too long" Pitfall (CRITICAL)

When the remote shell produces output on non-interactive sessions (e.g., `proxy off` from `.bashrc`, motd, conda init, etc.), `scp` fails with:
```
scp: Received message too long 1886547832
scp: Ensure the remote shell produces no output for non-interactive sessions.
```

**Root cause**: SCP uses the shell's stdout for its protocol. Any unexpected output (greeting, proxy message, conda banner) corrupts the protocol stream.

**Workaround — pipe through SSH instead of using scp directly**:
```bash
# Instead of: scp -P PORT file.tar.gz user@host:/tmp/
# Use:
cat /tmp/file.tar.gz | ssh -p PORT user@host "cat > /tmp/file.tar.gz"
```

This works because SSH handles the shell output gracefully, while the `cat` pipe is clean.

**Alternative fix**: Clean up the remote `.bashrc` to suppress output for non-interactive sessions:
```bash
# Wrap greeting/proxy messages in interactive check
[[ $- == *i* ]] && echo "proxy off"
```

**Why this is critical for deploy workflows**: The `remote_publish.sh` pattern uses `scp` to upload images. If the remote `.bashrc` has any echo/print statements, the entire deploy pipeline breaks. Always test with `ssh user@host 'echo ok'` first — if you see anything besides "ok", SCP will fail.

## SSH Timeout Pitfall

SSH commands via `ssh -p PORT user@host 'long command'` frequently timeout on slow/unstable connections. For file operations:
- Split long SSH commands into smaller focused ones
- Use `-o ConnectTimeout=10 -o ServerAliveInterval=5` for stability
- For multi-step remote operations, upload a shell script and execute it: `cat script.sh | ssh host "cat > /tmp/script.sh && bash /tmp/script.sh"`
- **Always use SSH config aliases** (from `~/.ssh/config`) instead of hardcoded host/port/key paths. Reference as `ssh aliyun`, `ssh zhang_c2`, etc. — cleaner and easier to maintain.
- **Use gzip compression** for `docker save` — `docker save image | gzip > /tmp/image.tar.gz` reduces transfer size significantly. Decompress on load: `docker load < /tmp/image.tar.gz` or `gunzip -c /tmp/image.tar.gz | docker load`.
- **Selective image rebuild**: When only one service changed (e.g., frontend only), build/save/upload/restart only that image instead of running full `remote_publish.sh`. Pattern: `docker build -t image-name ./path && docker save image-name | gzip > /tmp/image-name.tar.gz && cat /tmp/image-name.tar.gz | ssh host "cat > /tmp/image-name.tar.gz" && ssh host "docker load < /tmp/image-name.tar.gz && rm /tmp/image-name.tar.gz && docker-compose -f docker-compose-remote.yml up -d service-name"`
