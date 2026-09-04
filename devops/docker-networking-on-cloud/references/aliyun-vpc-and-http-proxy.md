# Aliyun VPC Docker Networking — Confirmed Findings

## The Aliyun VPC Subnet Mismatch Problem — CORRECTED ROOT CAUSE

**Original analysis**: Kernel routing rejects forwarded packets because source IP doesn't belong to eth0's subnet. `ip route get <external_ip> from <container_ip>` returns "Network is unreachable".

**Actual root cause (confirmed 2026-08-28)**: On the bioplatform Aliyun ECS instance, the real blocker was **mihomo (Clash Meta) transparent proxy's nftables rules**, NOT the VPC subnet mismatch. The `inet mihomo` table's prerouting chain was redirecting all container outbound TCP to a local proxy port (44907). This was invisible to `iptables -L`.

After `sudo nft delete table inet mihomo`, containers could access external internet immediately — no host network mode, no proxy, no policy routing needed.

**Lesson**: When `ip route get ... from <container_ip>` returns "Network is unreachable", the cause may not be routing at all. An nftables prerouting rule intercepting the packet before routing can also produce this symptom. Always check `nft list ruleset` FIRST.

1. Container sends SYN with source `172.19.0.3`
2. Routing table says: default via `172.21.239.253` dev `eth0`
3. Kernel checks: can `172.19.0.3` be routed through `eth0`?
4. `172.19.0.3` is NOT on eth0's subnet (`172.21.0.0/20`)
5. `ip route get 220.181.111.1 from 172.19.0.3` → **"Network is unreachable"**
6. Packet is dropped BEFORE reaching POSTROUTING (MASQUERADE never applies)

**Confirmed NOT fixable by**:
- Adding MASQUERADE rules (already present, counters increment from other traffic)
- Setting `rp_filter=0` (already 0)
- Enabling `bridge-nf-call-iptables` (causes inter-container breakage with raw table rules)
- Policy routing (`ip rule add from 172.19.0.0/16 table X` + routes in table X) — configured correctly but kernel still rejects
- Adding subnet route to policy table — still fails
- Using `enable_ip_masquerade=true` on custom networks — tested, no effect

**Why default bridge works**: docker0 uses `192.168.100.0/24`. On some Aliyun instances, docker0's subnet may have special kernel handling or the default bridge has different iptables rules injected by Docker.

## Container-to-Host Communication Also Broken

On some Aliyun ECS instances, containers on bridge networks cannot reach the HOST at all:
- `ping 172.19.0.1` from container times out
- HTTP proxy on host (172.19.0.1:3128) unreachable from containers
- socat forwarding on bridge gateway IP unreachable

This means **ANY approach requiring container→host communication will NOT work** on these instances. The only reliable option is `network_mode: host` with direct container IP connections for internal services.

## bridge-nf-call-iptables Side Effects

Enabling `bridge-nf-call-iptables=1` makes ALL bridge traffic go through iptables, including container-to-container traffic. If 1Panel/BT-Panel raw table DROP rules exist for container IPs:

```
DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.4
```

These rules match inter-container traffic because with bridge-nf-call-iptables, all bridge packets go through PREROUTING. Result: backend can't connect to MySQL on the same bridge, HikariPool connects initially but HTTP requests hang forever.

**Rule**: Always delete raw table DROP rules BEFORE enabling bridge-nf-call-iptables. Or leave it disabled and use alternative solutions.

## HTTP Proxy Limitations

The HTTP proxy approach (Python proxy on host, containers use http_proxy env var) only works if:
1. Container can reach host IP (172.19.0.1) — NOT guaranteed on Aliyun VPC
2. Proxy listens on 0.0.0.0 (not just172.19.0.1) — but even then, container→host routing may fail

If container→host communication is broken, the proxy approach is useless. Test first:
```bash
docker exec <container> ping -c 1 -W 3 172.19.0.1
```

## Aliyun Security Groups vs Network ACLs

- **Security Groups**: Instance-level, stateful. Checked on inbound AND outbound.
- **Network ACLs**: Subnet-level, stateless. Higher priority than security groups. Check VPC → Switch → Network ACL.
- Both must allow outbound TCP for container internet access.
- Aliyun internal services (e.g., smtpdm.aliyun.com) are reachable without public internet — they route through VPC internal network.

## Bioplatform-Specific Deployment Notes

### Shared infrastructure with blog project
- MySQL: `blog_mysql:3306` on blog_net, password `3rQndkCBaN3xqRTHE2f4`
- Redis: `blog_redis:6379` on blog_net, password `8978654`
- Network: `blog_net` (external, bridge, subnet 172.19.0.0/16)
- MySQL port mapping: `127.0.0.1:3308:3306` (bound to localhost only)
- Redis port mapping: `127.0.0.1:6380:6379` (bound to localhost only)

### application-prod.yml critical fields
- `spring.data.redis.host: blog_redis` (NOT `host.docker.internal`)
- `spring.data.redis.password: "8978654"` (MUST exist as YAML field, env var alone doesn't work)
- `spring.data.redis.timeout: 3000ms` (prevents infinite hang on connection failure)

### nginx-proxy configuration
- Config file on host: `/home/luosg/blog/nginx-proxy.conf`
- Must proxy `/api/` and `/ws/` to backend: `proxy_pass http://bioplatform-backend:8080`
- After container rebuild, nginx DNS cache may be stale → `docker exec nginx-proxy nginx -s reload`

### operation_logs.method column
- Must be VARCHAR(500), not VARCHAR(16) — method field stores full class.method name
- SQL file: `database/bioplatform.sql`

### API Key encryption
- Frontend encrypts with AES-GCM before sending (format: `ENC:Base64(...)`)
- Backend decrypts before storing, returns masked value (`sk-***xyzw`)
- Database stores encrypted format
- Key: `bioplatform-aes-key-2024-default-32b` (must match frontend crypto.ts)

### SSH command pitfalls
- `nohup ... &` in SSH causes exit code 255 — use separate SSH calls or `background=true`
- `!` in bash triggers history expansion — use `set +H` or escape with `\!`
- `scp` fails with "Received message too long" — use `cat file | ssh "cat > remote_file"` instead
- docker-compose v1 on remote: use `docker-compose` (hyphen), not `docker compose`
