# Remote Server Disk Cleanup Guide

Server: `ssh -p 20225 luosg@39.97.180.240` — 40G disk, no NOPASSWD sudo.

## Symptom

MinIO upload fails with:
```
io.minio.errors.ErrorResponseException: Storage backend has reached its minimum free drive threshold.
```
This is a **disk-full** error, NOT a MinIO configuration issue.

## Diagnostic Workflow

```bash
# 1. Check disk usage
ssh -p 20225 39.97.180.240 "df -h /"

# 2. Check Docker resource consumption
ssh -p 20225 39.97.180.240 "docker system df"

# 3. Check blog data directory (usually small)
ssh -p 20225 39.97.180.240 "du -sh /home/luosg/blog/"
```

## Common Space Hogs

| Source | Typical Size | Reclaimable? |
|--------|-------------|--------------|
| Docker unused volumes | 10-20 GB | Yes — running containers use bind mounts, not named volumes |
| Docker unused images | 1-3 GB | Yes — old build images accumulate |
| `/var/log/` | ~1 GB | Partially (need sudo for most) |
| `/home/luosg/*.zip` backups | Variable | Yes, if backed up elsewhere |

## Critical Check Before Pruning

Verify running containers use **bind mounts**, not named volumes:
```bash
for c in nginx-proxy blog_web blog_admin blog_backend blog_minio blog_mysql blog_redis; do
  echo "--- $c ---"
  docker inspect $c --format '{{range .Mounts}}{{.Name}} {{.Source}} {{end}}' 2>/dev/null
done
```
If `Name` is empty and `Source` shows host paths → bind mounts → safe to prune volumes.

## Cleanup Commands

```bash
# Remove unused Docker volumes (biggest win, ~10GB)
docker volume prune -f

# Remove unused Docker images (~2GB)
docker image prune -a -f

# Verify
df -h /
docker system df
```

## Pitfalls

- `du -sh /*` on 40G disk **times out over SSH** (30s default). Be targeted: check specific dirs.
- `sudo` over SSH **requires password** (no NOPASSWD configured). Avoid sudo commands; use `docker` commands which work as regular user.
- `docker system df` sometimes times out on slow connections — use 20s+ timeout.
- After cleanup, verify all containers are still running: `docker ps --format 'table {{.Names}}\t{{.Status}}'`
