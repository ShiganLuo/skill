# SSH Reverse Tunnel + Docker Container Port Access

## Problem
SSH reverse tunnel (`ssh -R 18081:127.0.0.1:18081`) binds to `127.0.0.1:18081` on the gateway server. Docker containers cannot reach this — `127.0.0.1` inside a container is the container's own loopback, not the host's.

## Diagnosis
```bash
# Check tunnel binding
ss -tlnp | grep 18081
# 127.0.0.1:18081 = only localhost (Docker can't reach)
# 0.0.0.0:18081 = all interfaces (Docker can reach)

# Test from container
docker exec <container> curl -s http://172.19.0.1:18081/health
# 172.19.0.1 = blog_net gateway (host IP from container perspective)
```

## Solutions (in order of preference)

### 1. socat relay (no sudo needed)
```bash
# Use a DIFFERENT port for the tunnel to avoid conflict with socat
# On node: ssh -R 28081:127.0.0.1:18081 -p 20225 user@gateway -N
# On gateway:
socat TCP-LISTEN:18081,bind=0.0.0.0,fork,reuseaddr TCP:127.0.0.1:28081 &
```
Container URL: `http://172.19.0.1:18081`

### 2. GatewayPorts yes (needs sudo)
```bash
# On gateway server
sudo sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
sudo systemctl restart sshd
# Then: ssh -R 0.0.0.0:18081:127.0.0.1:18081 ...
```

### 3. Add port to docker-compose (if tunnel is on gateway)
Not applicable for dynamic tunnels from external nodes.

## Pitfalls
- `ssh -R 0.0.0.0:18081:...` silently falls back to `127.0.0.1` if `GatewayPorts no` (default). No error message.
- socat can't bind `0.0.0.0:18081` if SSH tunnel already occupies `127.0.0.1:18081` (Linux treats them as overlapping). Use different ports.
- Worker health endpoint must return `{"status":"UP",...}` JSON. Connection reset = wrong binding or IPv4/IPv6 mismatch.
- `-N` flag = no remote command = blank line after password = NORMAL (tunnel is running).
