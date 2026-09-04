# Deployment Pitfalls

## nginx-proxy DNS Caching (Critical)

After `docker-compose up -d --force-recreate`, container IPs change but nginx caches old DNS. Routes become swapped (front→admin, admin→front).

**Fix**: After any container recreation, always reload nginx:
```bash
# First ensure all upstream hosts exist (blog containers must be running)
docker exec nginx-proxy nginx -s reload
```

If blog containers are down, `nginx -s reload` fails with `host not found in upstream "blog_web"`. Start blog containers first.

## Remote Server docker-compose v1 vs v2

Aliyun server uses `docker-compose` (standalone v1), not `docker compose` (Docker plugin v2). Scripts must use the hyphenated form for remote commands.

## SSH Reverse Tunnel + Docker

SSH reverse tunnel `-R 18081:127.0.0.1:18081` binds to `127.0.0.1:18081` on the server. Docker containers cannot reach `127.0.0.1` on the host (it resolves to the container's own loopback).

**Solutions** (in order of preference):
1. `GatewayPorts yes` in sshd_config → allows `-R 0.0.0.0:18081:127.0.0.1:18081` (needs sudo)
2. socat relay: `socat TCP-LISTEN:18081,bind=0.0.0.0,fork,reuseaddr TCP:127.0.0.1:18081 &`
   - Port conflict: SSH tunnel already on 127.0.0.1:18081, socat can't bind 0.0.0.0:18081
   - Use different tunnel port: `-R 28081:127.0.0.1:18081`, then socat on 18081→28081
3. Use Docker network gateway: containers access host via `172.19.0.1` (blog_net gateway)

**Container URL for worker**: `http://172.19.0.1:18081` (not `localhost`)

## http_proxy on Servers

Aliyun server has `http_proxy=http://127.0.0.1:7890` set globally. curl and other tools try to use this non-existent proxy. Always use `--noproxy '*'` or `unset http_proxy`.

## JAR Java Version Mismatch

Spring Boot 3.x requires Java 17. If target server only has Java 11, `UnsupportedClassVersionError`. Check with `java -version` before deploying. Use jenv to switch versions.
