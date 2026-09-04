---
name: docker-networking-on-cloud
description: "Fix Docker containers no internet on cloud VPS."
tags: [docker, networking, iptables, aliyun, ecs, vpc, bridge, nat]
related_skills: [development-runtime-orchestration, docker-vite-frontend-debugging]
---

# Docker Networking on Cloud VPS

Use when Docker bridge network containers can reach the host but not external internet, while the host itself has full connectivity.

## Diagnosis Flow

### 1. Confirm the symptom
```bash
# From container — fails
docker exec <container> curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/

# From host — succeeds
curl --noproxy '*' -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/
```

### 2. Check nftables ruleset FIRST (CRITICAL — iptables won't show these)
```bash
sudo nft list ruleset
```
**This is the #1 missed cause.** `iptables -L` only shows iptables-managed rules. Tools like firewalld, mihomo/Clash Meta, and other nftables-native apps create独立的 tables that `iptables -L`完全看不到.

Look for non-Docker tables:
- `table inet firewalld` — firewalld残留规则，forward链可能有`policy drop`
- `table inet mihomo` — Clash Meta透明代理，prerouting链redirect到本地代理端口
- Any `table` that is NOT `ip filter`, `ip nat`, `ip raw`, `ip mangle`

Quick filter to find non-Docker tables:
```bash
sudo nft list ruleset | grep -E '^table ' | grep -v -E 'ip filter|ip nat|ip raw|ip mangle|ip6 |bridge '
```

**Fix**: Delete the entire table:
```bash
sudo nft delete table inet <table_name>
```

See `references/nftables-interception.md` for detailed case studies.

### 3. Check iptables NAT
```bash
sudo iptables -t nat -L POSTROUTING -n -v --line-numbers
```
Look for MASQUERADE rule matching Docker subnet (e.g., 172.19.0.0/16). Packet counter should increment when container makes requests.

### 4. Check if packets leave the host
```bash
sudo tcpdump -i eth0 -n host 220.181.111.1 -c 3 &
sleep 1
docker exec <container> curl -s --max-time 3 http://www.baidu.com/ > /dev/null 2>&1
```
If no packets on eth0, the issue is between the bridge and eth0.

Look for non-Docker tables:
- `table inet firewalld` — firewalld残留规则，forward链可能有`policy drop`
- `table inet mihomo` — Clash Meta透明代理，prerouting链redirect到本地代理端口
- Any `table` that is NOT `ip filter`, `ip nat`, `ip raw`, `ip mangle`

**Fix**: Delete the entire table:
```bash
sudo nft delete table inet <table_name>
```

See `references/nftables-interception.md` for detailed case studies.

### 5. Check raw table DROP rules
```bash
sudo iptables -t raw -L PREROUTING -n --line-numbers
```
Cloud providers (especially Aliyun 1Panel/BT-Panel) add DROP rules in raw PREROUTING for container IPs like:
```
DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.2
DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.3
...
```
These say: drop packets arriving from ANY interface OTHER than the bridge, destined for container IPs. This blocks return traffic from external hosts (they arrive via eth0, not the bridge). The packet gets dropped before conntrack can de-NAT it, so the kernel generates an immediate RST (visible in tcpdump as same-microsecond SYN→RST).

**PITFALL**: `!` in bash triggers history expansion. Use `set +H` first, OR use the alternative syntax `! -i` (NOT `!-i` which includes the `!` in the interface name).

**Fix** — delete all Docker subnet rules:
```bash
set +H  # disable bash history expansion
# Correct syntax: ! comes BEFORE -i as a separate token
sudo iptables -t raw -D PREROUTING ! -i br-f94c057f9c2b -d 172.19.0.2 -j DROP
sudo iptables -t raw -D PREROUTING ! -i br-f94c057f9c2b -d 172.19.0.3 -j DROP
# ... repeat for all container IPs
```
**Alternative**: insert an ESTABLISHED,RELATED ACCEPT rule BEFORE the DROPs (less disruptive):
```bash
sudo iptables -t raw -I PREROUTING 1 -d 172.19.0.0/16 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
```
Note: raw table is processed BEFORE conntrack, so this may not always work. Deleting the DROP rules is more reliable.

### 5. Check bridge-nf-call-iptables
```bash
sudo sysctl net.bridge.bridge-nf-call-iptables
```
If "No such file or directory":
```bash
sudo modprobe br_netfilter
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1
```
Without this, bridge traffic bypasses iptables — MASQUERADE never applies.

### 6. Check kernel routing for forwarded packets
On cloud VPS where the host NIC subnet (e.g. 172.21.0.0/20) differs from Docker's bridge subnet (172.19.0.0/16), the kernel may reject forwarded packets because it cannot find a valid route for a source IP that doesn't belong to any local interface:
```bash
# This is the KEY diagnostic — if it says "Network is unreachable", you've found the root cause
ip route get <external_ip> from <container_ip>
# Example:
ip route get 220.181.111.1 from 172.19.0.3
```
If this returns "Network is unreachable", MASQUERADE will never apply because the packet is dropped at the routing stage BEFORE reaching POSTROUTING. The MASQUERADE counter in `iptables -t nat -L POSTROUTING -v` may still show matches from other traffic, creating a false positive.

**Symptoms**:
- Default bridge (docker0) works, custom bridges don't
- tcpdump on bridge shows SYN, tcpdump on eth0 shows nothing
- SYN→RST in same microsecond on bridge (kernel generates RST for unroutable packets)
- MASQUERADE counter shows matches but packets never leave eth0
- Container can't even ping the gateway (172.19.0.1) — confirmed on Aliyun ECS

**CRITICAL FINDING**: On some Aliyun ECS instances, containers on bridge networks cannot reach the HOST at all (not just external internet). `ping 172.19.0.1` from container times out. This means ANY approach requiring container→host communication (HTTP proxy on host, socat forwarding, etc.) will NOT work. The only option is host network mode with direct container IP connections.

**Fix — policy routing** (requires both the rule AND the subnet route in the table):
```bash
echo "100 docker_net" | sudo tee -a /etc/iproute2/rt_tables
sudo ip route add 172.21.224.0/20 dev eth0 table docker_net    # subnet route to reach gateway
sudo ip route add default via 172.21.239.253 dev eth0 table docker_net
sudo ip rule add from 172.19.0.0/16 table docker_net
ip route get 220.181.111.1 from 172.19.0.3  # should now return a valid route
```

**If policy routing still fails**: the kernel may still reject because the source IP doesn't pass `src_valid_mark` checks. This was confirmed on Aliyun ECS where policy routing was configured correctly (rule at priority 8999, subnet route + default route in table) but `ip route get` still returned "Network is unreachable". The remaining options are:

**PITFALL: bridge-nf-call-iptables breaks inter-container communication**
Enabling `bridge-nf-call-iptables=1` makes ALL bridge traffic go through iptables. If 1Panel/BT-Panel raw table DROP rules exist for container IPs, this causes:
- Container-to-container communication on the SAME bridge breaks
- HikariPool connects initially but HTTP requests hang forever
- Root cause: raw table `DROP all -- !br-f94c057f9c2b * 172.19.0.4` matches inter-container traffic when bridge-nf-call-iptables is enabled
- **Fix**: Either delete raw table DROP rules FIRST, OR leave bridge-nf-call-iptables=0 and find another solution

#### Option A: Host network mode
Set `network_mode: host` on the backend. Pitfalls (all confirmed):
- **Port conflicts**: another container (e.g., blog_backend) may already bind the same port (8080). Set `SERVER_PORT: 8083` env var to change.
- **Raw table rules block 127.0.0.1**: 1Panel/BT-Panel adds `DROP tcp -- !lo * 127.0.0.1 tcp dpt:3308`. Even though host-network containers share the host namespace, the raw table may block connections to 127.0.0.1:3308. Use container IPs instead (e.g., `172.19.0.4:3306`).
- **MySQL/Redis via container IP may still hang**: On some Aliyun VPC configurations, even host-network containers connecting to bridge-network containers via their IP (172.19.0.x) can hang. If this happens, stick with bridge network and use Option B.
- **nginx-proxy needs updating**: change `proxy_pass http://backend:8080` to `proxy_pass http://172.19.0.1:8083` (host IP on Docker network + new port).

#### Option B: HTTP proxy on the host
Run a simple HTTP proxy on the host, listening on the bridge gateway IP. The container uses `http_proxy` for external calls only. This is the least disruptive option — no network mode changes, no port conflicts.

#### Option C: Dual-network
Connect container to both custom bridge and default bridge: `docker network connect bridge <container>`. The container gets a second NIC on docker0. BUT: docker0 is often `linkdown` and may not work either.

**PITFALL**: `enable_ip_masquerade` option on custom networks does NOT fix this. Tested and confirmed it has no effect.

### 7. Check bridge-nf-call-iptables side effects (CRITICAL)
Enabling `bridge-nf-call-iptables` makes ALL bridge traffic go through iptables, including container-to-container traffic on the same bridge. If raw table DROP rules exist for container IPs, this can BREAK inter-container communication (e.g. backend can't connect to MySQL on the same bridge).

**Confirmed scenario**: On Aliyun ECS with 1Panel, enabling `bridge-nf-call-iptables=1` caused `bioplatform-backend` (on blog_net) to hang connecting to `blog_mysql` (also on blog_net). HikariPool connected initially but HTTP requests hung forever. The raw table DROP rules (`DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.4`) were matching inter-container traffic because with bridge-nf-call-iptables, all bridge packets go through PREROUTING.

**Test before enabling**: check if container-to-container communication works:
```bash
docker exec <container1> curl -s --max-time 3 http://<container2>:<port>/
```

**If enabling causes issues**: either delete the raw table DROP rules first, or leave `bridge-nf-call-iptables=0` and find another solution for outbound internet.

**Diagnostic**: if `bridge-nf-call-iptables=1` and container-to-container hangs:
```bash
# Check if raw table DROP rules exist for container IPs
sudo iptables -t raw -L PREROUTING -n --line-numbers
# If DROP rules exist for 172.19.0.x, delete them all first
```

### 8. Check cloud security group AND network ACL
- **Security Group**: Outbound rules must allow all TCP (0.0.0.0/0, ports 1-65535)
- **Network ACL**: Separate from security groups, higher priority
- **NAT Gateway**: If instance has no public IP, needs NAT gateway

### 7. Compare default bridge vs custom bridge
If all above checks pass but custom bridge networks still fail while the default bridge (docker0) works:
```bash
# Test default bridge — works?
docker run --rm --network bridge <image> curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/

# Test custom bridge — fails?
docker run --rm --network <custom_net> <image> curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/
```

If default bridge works but custom doesn't, check the DOCKER chain rules:
```bash
sudo iptables -L DOCKER -n -v --line-numbers
```
The DOCKER chain has port-specific ACCEPT rules (for published ports) and a catch-all DROP at the end for each bridge. The DOCKER-FORWARD chain has interface-specific ACCEPT rules:
```
ACCEPT all -- br-f94c057f9c2b *  0.0.0.0/0  0.0.0.0/0
ACCEPT all -- br-251d51bb4310 *  0.0.0.0/0  0.0.0.0/0
ACCEPT all -- docker0         *  0.0.0.0/0  0.0.0.0/0
```
These accept outbound traffic FROM each bridge. If a bridge is missing from this list, its containers can't reach the internet.

## PITFALL: Application config errors masquerading as network issues
When a backend starts but requests hang (not error, just hang with 0 bytes received until timeout), the cause is often an application config issue, NOT a network issue:
- **Redis wrong password / wrong host**: Spring Boot with Lettuce will hang on the first request that touches Redis if the connection can't be established. The app starts fine (no startup error), HikariPool connects to MySQL, but HTTP requests hang forever. Fix: ensure `SPRING_DATA_REDIS_HOST`, `SPRING_DATA_REDIS_PORT`, `SPRING_DATA_REDIS_PASSWORD` match the actual Redis container.
- **Redis host unreachable**: If Redis host is set to `host.docker.internal` (Docker Desktop feature, doesn't work on Linux), the app hangs. Use container name or IP instead.
- **Diagnostic**: If `docker exec <container> curl -s --max-time 5 http://localhost:8080/api/...` returns data (from within the same network) but host `curl http://127.0.0.1:<mapped_port>/api/...` times out, the issue is port mapping/DNAT, not the application.
- **CONFIRMED**: On bioplatform, setting Redis password via environment variable `SPRING_DATA_REDIS_PASSWORD` did NOT work when `application-prod.yml` had no `password` field. The env var was not picked up by Spring Boot's property binding. Fix: add `password:` field directly in `application-prod.yml` and rebuild the image.

**CONFIRMED**: Spring Boot environment variables for Redis DO work for simple properties like host/port, but `password` requires the field to exist in the YAML. Without the YAML field, the env var is silently ignored and Lettuce tries to connect without authentication → connection hangs forever (no error, no timeout, just hangs). Diagnostic: check `docker exec <container> env | grep REDIS` to confirm env vars are set, but the app still hangs = YAML field missing.

## PITFALL: Host network mode is NOT a simple fix
Switching to `network_mode: host` introduces its own problems:
- **Port conflicts**: another container may already bind the same port. Set `SERVER_PORT: 8083` env var to change.
- **Raw table blocks 127.0.0.1**: 1Panel/BT-Panel adds `DROP tcp -- !lo * 127.0.0.1 tcp dpt:3308`. Host-network containers connecting to `127.0.0.1:3308` (port-mapped MySQL) may be blocked. Use container IPs instead.
- **Container IP connections may hang**: On some Aliyun VPC configs, even host-network containers connecting to bridge-network containers via IP (172.19.0.x:3306) can hang due to raw table rules.
- **Best approach**: Use bridge network + HTTP proxy on host (Option B above). Least disruptive, no port conflicts, no raw table issues.

## PITFALL: DNS resolution between containers
Container name resolution (e.g., `blog_mysql`) only works within the same Docker network. When using host network mode, containers cannot resolve other containers by name. Always use container IPs or keep all services on the same bridge network.

See `references/nftables-interception.md` for firewalld and mihomo/Clash transparent proxy case studies — these are invisible to `iptables -L` and are the #1 missed cause on cloud VPS.

## Traffic Path
```
Container → veth → Bridge → FORWARD (DOCKER-FORWARD → DOCKER-CT/BRIDGE → ACCEPT) → POSTROUTING (MASQUERADE) → eth0 → VPC → Internet
```
Each link can break: br_netfilter, FORWARD DROP, raw table DROP, DOCKER chain DROP, security group, network ACL, no public IP.

**Key insight**: tcpdump on `any` uses Linux cooked format — doesn't show interface names. Use separate `tcpdump -i eth0` and `tcpdump -i br-xxx` to isolate which interface sees the packet. If SYN appears on bridge but not eth0, and MASQUERADE counter increments, the issue is between FORWARD and eth0 (check DOCKER-FORWARD chain verbose output with `-v`).

## Persistence
```bash
echo 'br_netfilter' | sudo tee -a /etc/modules-load.d/br_netfilter.conf
echo 'net.bridge.bridge-nf-call-iptables=1' | sudo tee -a /etc/sysctl.d/99-docker-bridge.conf
```
Note: custom iptables rules are NOT persistent across Docker restarts.
