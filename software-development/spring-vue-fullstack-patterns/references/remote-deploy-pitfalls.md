# Remote Deployment Pitfalls

Additional pitfalls for deploying Spring Boot + Vue3 projects to remote servers (Alibaba Cloud, university servers, etc.).

## Server http_proxy Causes curl Failures

Some servers have `http_proxy` / `https_proxy` env vars set (e.g., for a local clash/v2ray proxy). If the proxy process is not running, `curl` fails with `Connection refused` on the proxy port (e.g., port 7890).

**Diagnosis**: `curl -v http://localhost:8083` shows `Trying 127.0.0.1... port 7890`.

**Fix**: `curl --noproxy '*' http://localhost:8083/...` or `unset http_proxy https_proxy` before commands. For SSH: `ssh ... "unset http_proxy; curl --noproxy '*' http://localhost:8083/..."`.

## MySQL Container OOM on Low-Memory Servers

On servers with < 2GB RAM, importing large SQL files can OOM-kill MySQL. The `Lost connection to MySQL server during query` error means MySQL was killed mid-import.

**Recovery**:
1. `docker restart blog_mysql`
2. Wait 15-20 seconds for MySQL to be ready
3. Check readiness: `docker exec blog_mysql mysql -uroot -pPASS -e 'SELECT 1'`
4. Re-import SQL
5. If SQL is large, import table-by-table or increase `--max-allowed-packet=256M`

**Prevention**: Stop non-essential containers before large SQL imports. On a 1.8G server, stop blog_backend, blog_web, blog_admin, nginx-proxy before importing.

## Stopping Other Projects to Free Resources

When deploying a new project to a server already running other services:

```bash
# Stop non-essential containers (keep MySQL)
docker stop blog_backend blog_web blog_admin nginx-proxy blog_minio blog_minio_init

# Check memory freed
free -h | head -2

# Deploy new project
docker run -d --name bioplatform-backend ...

# Later: restart old project
docker start blog_backend blog_web blog_admin nginx-proxy blog_minio blog_minio_init
```

## host.docker.internal Unreliable on Linux

`host.docker.internal` does NOT work reliably on Linux Docker. Use `--network blog_net` to join the existing Docker network and use container names as hostnames (e.g., `blog_mysql:3306`).

## SSH Connection Instability

Long-running SSH commands may timeout or get blocked. Use shorter commands with explicit timeouts:
```bash
ssh -i key -p PORT -o ConnectTimeout=10 user@host "short command"
```

For multi-step operations, break into separate SSH calls rather than one long heredoc.
