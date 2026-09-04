# Docker iptables Chain Structure (Aliyun ECS with 1Panel/BT-Panel)

## FORWARD chain
```
FORWARD (policy ACCEPT)
  → DOCKER-USER   (empty by default, user rules go here)
  → DOCKER-FORWARD
      → DOCKER-CT       (conntrack: RELATED,ESTABLISHED to each bridge)
      → DOCKER-INTERNAL  (empty)
      → DOCKER-BRIDGE    (sends to DOCKER chain for traffic TO each bridge)
      → ACCEPT (in=br-f94c057f9c2b)   ← outbound from blog_net containers
      → ACCEPT (in=br-251d51bb4310)   ← outbound from other network
      → ACCEPT (in=docker0)           ← outbound from default bridge
```

## DOCKER chain (filter table)
```
# Per-container port-specific ACCEPT rules (published ports)
ACCEPT tcp -- !br-f94c057f9c2b br-f94c057f9c2b 0.0.0.0/0 172.19.0.x tcp dpt:YYYY
...
# Catch-all DROP for each bridge (blocks external → container for unpublished ports)
DROP   all  -- !br-f94c057f9c2b br-f94c057f9c2b 0.0.0.0/0 0.0.0.0/0
DROP   all  -- !br-251d51bb4310 br-251d51bb4310 0.0.0.0/0 0.0.0.0/0
DROP   all  -- !docker0         docker0          0.0.0.0/0 0.0.0.0/0
```

## POSTROUTING (nat table)
```
# Docker-generated MASQUERADE for each bridge subnet
MASQUERADE all -- * !br-f94c057f9c2b 172.19.0.0/16  0.0.0.0/0
MASQUERADE all -- * !br-251d51bb4310 172.17.0.0/16  0.0.0.0/0
MASQUERADE all -- * !docker0         192.168.100.0/24 0.0.0.0/0
# User-added duplicates (from manual troubleshooting, harmless but messy)
MASQUERADE all -- * !docker0         172.19.0.0/16  0.0.0.0/0  ← duplicate
```

## PREROUTING (raw table) — 1Panel/BT-Panel additions
```
# Block external access to container IPs (security)
DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.2
DROP all -- !br-f94c057f9c2b * 0.0.0.0/0 172.19.0.3
...
# Block external access to MySQL/Redis on localhost
DROP tcp -- !lo * 0.0.0.0/0 127.0.0.1 tcp dpt:3308
DROP tcp -- !lo * 0.0.0.0/0 127.0.0.1 tcp dpt:6380
```

## Diagnostic commands
```bash
# See packet counters on each chain (verbose shows -i/-o interfaces)
sudo iptables -L FORWARD -n -v --line-numbers
sudo iptables -L DOCKER-FORWARD -n -v --line-numbers
sudo iptables -L DOCKER -n -v --line-numbers
sudo iptables -t nat -L POSTROUTING -n -v --line-numbers
sudo iptables -t raw -L PREROUTING -n --line-numbers

# Test specific bridge vs default
docker run --rm --network bridge alpine ping -c 2 223.5.5.5
docker run --rm --network <custom_net> alpine ping -c 2 223.5.5.5

# Tcpdump per-interface (NOT -i any which uses Linux cooked format)
sudo tcpdump -i br-f94c057f9c2b -n host 220.181.111.1 -c 3
sudo tcpdump -i eth0 -n host 220.181.111.1 -c 3
```
