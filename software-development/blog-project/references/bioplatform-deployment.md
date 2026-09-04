# Bioplatform Deployment (Aliyun)

**Server**: `aliyun` SSH config alias (`~/.ssh/aliyun` → `luosg@39.97.180.240:20225`)
**NOT `zhang_c2`** — that's the Worker c2 node (different purpose).

## Full Deploy

```bash
cd /home/luosg/Work/luosg/Code/bioplatform
bash remote_publish.sh
```

Builds backend JAR + all 3 Docker images locally, exports, uploads, deploys. Slow (~5min).

## Partial Deploy (admin/front only)

When only one frontend service changed, skip the full build. Use SSH config alias `aliyun` instead of full SSH command.

```bash
# 1. Build only the changed image
docker build -t bioplatform-front ./bioplatform-vue3/bioplatform-front

# 2. Export with gzip (faster transfer), upload via pipe (SCP broken)
docker save bioplatform-front | gzip > /tmp/bioplatform-front.tar.gz
cat /tmp/bioplatform-front.tar.gz | ssh aliyun "cat > /tmp/bioplatform-front.tar.gz"
rm -f /tmp/bioplatform-front.tar.gz

# 3. Load + restart on remote (decompress on the fly)
ssh aliyun "docker load < /tmp/bioplatform-front.tar.gz && rm /tmp/bioplatform-front.tar.gz && cd ~/bioplatform && docker-compose -f docker-compose-remote.yml up -d front"
```

Same pattern for `bioplatform-admin` or `bioplatform-backend`.

## SCP Workaround

Remote `.bashrc` outputs "proxy off" on every SSH session, which breaks `scp` (error: "Received message too long"). Use `cat file | ssh aliyun "cat > dest"` instead of `scp`. Always use SSH config aliases (e.g., `ssh aliyun`) not full `ssh -i ... -p ... user@host` commands.

## Container Architecture

| Container | Image | Port | Network |
|-----------|-------|------|---------|
| bioplatform-backend | bioplatform-backend | 8083→8080 | blog_net |
| bioplatform-admin | bioplatform-admin | 3001→80 | blog_net |
| bioplatform-front | bioplatform-front | 3000→80 | blog_net |

Shares `blog_net` with blog project (MySQL, Redis, nginx-proxy).

## Pitfalls

- Remote uses `docker-compose` (v1, hyphenated), not `docker compose` (v2).
- `curl --noproxy '*'` required for remote localhost checks.
- External access (port 3000/3001/8083) may timeout from host due to VPC/firewall; verify inside container with `docker exec bioplatform-front curl -s http://localhost/`.
- **Use gzip compression** for `docker save` — reduces transfer size significantly (e.g., 26MB vs 80MB+ uncompressed).
- **Upload to /tmp/ is fine for single deploy** — the file is deleted after `docker load`. Don't need persistent ~/bioplatform/ path for one-shot deploys.
