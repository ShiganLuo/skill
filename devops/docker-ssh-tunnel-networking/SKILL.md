---
name: docker-ssh-tunnel-networking
description: "Use when Docker containers reach SSH tunnels on the host."
version: "1.1"
author: "luosg"
tags: [docker, ssh, tunnel, autossh, networking, host.docker.internal, GatewayPorts, socat]
metadata:
  hermes:
    tags: [docker, ssh, tunnel, autossh, networking]
    related_skills: [docker-container-host-access, docker-networking-on-cloud]
---

# Docker Container → Host SSH Tunnel Networking

## When to Use

A Docker container needs to connect to a service exposed via SSH reverse tunnel on the same host. Common in multi-server deployments where internal compute nodes connect to a public gateway via autossh.

## The Problem

```
Host machine
├── SSH tunnel listening on 127.0.0.1:18081  ← only host can reach
└── Docker network
    └── backend container
        └── tries localhost:18081  ← points to container itself, FAILS
```

`localhost` inside a Docker container = the container, NOT the host. Even `172.19.0.1` (Docker bridge gateway) won't work if the tunnel only binds to `127.0.0.1`.

## Solution: socat forwarding (RECOMMENDED)

Safer approach — no sshd_config changes, tunnel stays on 127.0.0.1.

### Step 1: extra_hosts in docker-compose

```yaml
services:
  backend:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Step 2: Find what host.docker.internal resolves to

```bash
docker exec <container> cat /etc/hosts | grep host.docker
# Output: 192.168.100.1  host.docker.internal
```

**CRITICAL**: This is typically the `docker0` bridge IP, NOT the custom network bridge IP. On the same host, `blog_net` might be `172.19.0.1` while `host.docker.internal` is `192.168.100.1`. Always verify before binding socat.

### Step 3: Start socat (bind to host.docker.internal's actual IP)

```bash
nohup socat TCP-LISTEN:18081,bind=192.168.100.1,fork,reuseaddr TCP:127.0.0.1:18081 &
```

### Step 4: Register service URL

```
http://host.docker.internal:18081
```

NOT `http://localhost:18081` and NOT `http://172.19.0.1:18081`.

### systemd persistence

```ini
# /etc/systemd/system/socat-tunnel.service (on public server)
[Unit]
Description=Socat port forward for Docker to SSH tunnel
After=network.target docker.service

[Service]
Type=simple
ExecStart=/usr/bin/socat TCP-LISTEN:18081,bind=192.168.100.1,fork,reuseaddr TCP:127.0.0.1:18081
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Multiple tunnels: separate services with different ports.

## Traffic path

```
Container app → host.docker.internal:18081
    ↓ (resolves to docker0 bridge, e.g., 192.168.100.1)
socat: 192.168.100.1:18081 → 127.0.0.1:18081
    ↓
SSH tunnel 127.0.0.1:18081
    ↓
Internal server localhost:8081 (Worker)
```

## Alternative: GatewayPorts (NOT recommended)

Modifying sshd_config to allow 0.0.0.0 bind. Security risk — tunnel port exposed to all interfaces.

```bash
sudo bash -c 'echo "GatewayPorts clientspecified" >> /etc/ssh/sshd_config'
sudo systemctl restart sshd

autossh -M 0 -N -R 0.0.0.0:18081:localhost:8081 user@public -p 22
```

Risk: Worker endpoints like `/worker/shell/execute` publicly accessible. Requires iptables rules to limit access.

## Verification

```bash
# Host: tunnel works
curl http://127.0.0.1:18081/worker/health

# Container: socat works
docker exec <container> wget -q -O- --timeout=3 http://host.docker.internal:18081/worker/health

# Check socat is listening
ss -tlnp | grep 18081
# Should show both 127.0.0.1:18081 (tunnel) and 192.168.100.1:18081 (socat)
```

## Diagnostic Script (save as diagnose-tunnel.sh on public server)

```bash
#!/bin/bash
echo "=== 1. SSH tunnel port ==="
ss -tlnp | grep 18081 || echo "❌ Port 18081 not listening"

echo ""
echo "=== 2. socat process ==="
ps aux | grep socat | grep -v grep || echo "❌ socat not running"

echo ""
echo "=== 3. Host test tunnel ==="
curl -s --max-time 3 http://127.0.0.1:18081/worker/health || echo "❌ Tunnel unreachable"

echo ""
echo "=== 4. host.docker.internal resolves to ==="
docker exec bioplatform-backend cat /etc/hosts | grep host.docker

echo ""
echo "=== 5. Container test ==="
docker exec bioplatform-backend wget -q -O- --timeout=3 http://host.docker.internal:18081/worker/health 2>&1 || echo "❌ Container unreachable"

echo ""
echo "=== 6. Backend logs (last 5 health checks) ==="
docker logs bioplatform-backend 2>&1 | grep -E "健康检查|测试连接" | tail -5
```

## Pitfalls

- **host.docker.internal ≠ custom network bridge**: `host-gateway` maps to `docker0` IP (e.g., `192.168.100.1`), not custom network IP (e.g., `172.19.0.1`). Always check with `docker exec ... cat /etc/hosts`.
- **socat binds to wrong IP**: if you hard-code `172.19.0.1` but host.docker.internal resolves to `192.168.100.1`, container connections time out.
- **sshd_config not updated (GatewayPorts approach)**: defaults to `no`, silently forces `127.0.0.1` regardless of client `-R 0.0.0.0`.
- **autossh without ExitOnForwardFailure**: if port already in use, autossh connects but tunnel silently fails.
- **loginctl enable-linger forgotten**: systemd user service stops ~10s after SSH session ends.
- **Health checks with empty catch blocks**: always add `log.error` in catch blocks of periodic health checks. Silent failures make debugging impossible.
- **In-memory cache stale after DB update**: if you update a node URL directly in the database, the backend's in-memory `WorkerRegistry` cache won't reflect it until restart. Use the API (`PUT /api/admin/workers/{nodeId}`) which updates both DB and cache.
- **Test connection doesn't update health status**: the test endpoint should also update the node's `healthy` field in DB + memory cache, so the frontend list refreshes immediately. Otherwise user sees stale "离线" status after a successful test.
- **Frontend list not refreshed after test**: always call `await loadWorkers()` after test connection in Vue3.