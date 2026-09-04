# Shared MySQL & Multi-Project Docker Networking

## Sharing MySQL Between Projects (blog_net pattern)

When multiple projects share one MySQL instance on the same server, join the existing Docker network:

```bash
# MySQL is in blog_net (from blog project's docker-compose)
docker run -d --name bioplatform-backend \
    --network blog_net \
    -p 8083:8080 \
    -e SPRING_DATASOURCE_URL='jdbc:mysql://blog_mysql:3306/bioplatform?...' \
    -e SPRING_DATASOURCE_USERNAME=root \
    -e SPRING_DATASOURCE_PASSWORD=<password> \
    bioplatform-backend:latest
```

Advantages over `host.docker.internal`:
- Container name DNS resolution works (`blog_mysql:3306`)
- No need for `--add-host` workaround
- No port mapping dependency (container-to-container uses internal ports)
- Environment variables override Spring YAML config at runtime

## Nginx-Proxy Pattern for Multi-Project SSL

When multiple projects share one server with SSL, use a single nginx-proxy container:

1. Create `nginx-proxy.conf` at **project root** (NOT in a `deploy/` subdirectory)
2. Append to the existing nginx-proxy.conf on the server
3. Restart nginx-proxy container

The nginx-proxy container must be on the same Docker network as all service containers.

## Deploy File Structure Convention

**Dockerfiles go in each sub-project directory, NOT in a central `deploy/` folder.** The user explicitly rejected a `deploy/` directory as redundant — each project already has its own Dockerfile.

```
project-root/
├── bioplatform-springboot/Dockerfile   # Backend: eclipse-temurin:17-jre-alpine
├── bioplatform-vue3/bioplatform-front/Dockerfile  # Front: nginx:alpine + dist
├── bioplatform-vue3/bioplatform-admin/Dockerfile  # Admin: nginx:alpine + dist
├── docker-compose.yml                  # Local orchestration
├── docker-deploy.sh                    # Local deploy script
├── nginx-proxy.conf                    # Nginx reverse proxy (root level, NOT deploy/)
├── remote_publish.sh                   # Remote deploy (build+save+upload+load+run)
└── database/bioplatform.sql            # DB init script
```

## remote_publish.sh Pattern

For servers without CI/CD, use a single script at root that does the full cycle:

```bash
#!/bin/bash
set -e
SSH="ssh -i $SSH_KEY -p $PORT user@host"
SCP="scp -i $SSH_KEY -P $PORT"

# 1. Build
cd bioplatform-springboot && mvn clean package -q -DskipTests && cd ..
docker compose build

# 2. Export all images into one tar (gzip for faster transfer)
docker save bioplatform-backend bioplatform-front bioplatform-admin | gzip > /tmp/images.tar.gz

# 3. Upload (use SSH pipe — scp fails if remote shell has output)
cat /tmp/images.tar.gz | ssh -i $SSH_KEY -p $PORT user@host "cat > /tmp/images.tar.gz"

# 4. Remote deploy
$SSH bash -s << 'REMOTE'
gunzip -c /tmp/images.tar.gz | docker load
docker rm -f old-containers
docker run -d --name backend --network blog_net -p 8083:8080 \
    -e SPRING_DATASOURCE_URL='jdbc:mysql://blog_mysql:3306/db?...' \
    -e SPRING_DATASOURCE_PASSWORD=<pass> \
    bioplatform-backend
docker run -d --name front --network blog_net -p 3000:80 bioplatform-front
docker run -d --name admin --network blog_net -p 3001:80 bioplatform-admin
REMOTE
```

## OOM on Memory-Constrained Servers

On servers with <2G RAM running multiple containers:
- `docker exec mysql ... < large.sql` can OOM-kill MySQL
- **Fix**: Stop non-essential containers first (`docker stop blog_backend blog_web ...`), then import SQL
- **Fallback**: Import tables incrementally (one CREATE TABLE at a time)
- Always wait for MySQL readiness after restart: loop check `SELECT 1` before any DB operation
- Check memory with `free -h` before deploying
- `docker stats` shows per-container memory usage

## Nginx-Proxy Integration Pitfalls

When adding a new project to an existing nginx-proxy:

1. **Append server blocks to the EXISTING nginx-proxy.conf** on the server. Do NOT create a separate config file — nginx loads all `.conf` files in `conf.d/` and duplicate server blocks cause routing conflicts.

2. **Add new domains to the HTTP→HTTPS redirect server block's `server_name` list**. If you forget this, HTTP requests to the new domain won't redirect to HTTPS — they'll hit the default nginx page or 404.

3. **Wildcard SSL cert limitation**: `*.shiganluo.top` only matches ONE level of subdomain. `bio.shiganluo.top` works, but `admin.bio.shiganluo.top` does NOT. Use `bioadmin.shiganluo.top` instead of `admin.bio.shiganluo.top` to stay within the wildcard scope.

4. **After modifying nginx-proxy.conf**, restart the container: `docker restart nginx-proxy`. Verify with `docker exec nginx-proxy nginx -t` before restarting.

5. **Nginx-proxy must be on the same Docker network** as all service containers (`--network blog_net`). Check with `docker network inspect blog_net --format '{{range .Containers}}{{.Name}} {{end}}'`.

## Pitfall: Don't Create a `deploy/` Directory

Users expect Dockerfiles alongside their source code, not centralized. The blog project convention is: Dockerfile in each sub-project, nginx-proxy.conf and deploy scripts at root. Creating `deploy/dockerfiles/` and `deploy/nginx/` is over-engineering that breaks the expected layout.
