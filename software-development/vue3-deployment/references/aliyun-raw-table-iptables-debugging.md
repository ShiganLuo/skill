# Aliyun ECS Raw Table iptables Debugging

## Problem

Docker containers on Aliyun ECS can't reach external internet, even with:
- Correct NAT masquerade rules
- Security group outbound rules allowing all traffic
- ip_forward=1

Symptoms:
- `docker exec <container> curl http://www.baidu.com/` returns 000/empty
- `curl: (56) Connection refused` or `Recv failure: Connection reset by peer`
- Host can access internet fine, but containers can't

## Root Cause

Aliyun's security agent adds per-container-IP DROP rules in the `raw` table PREROUTING chain:

```
Chain PREROUTING (policy ACCEPT)
DROP  all  !br-f94c057f9c2b  *  0.0.0.0/0  172.19.0.2
DROP  all  !br-f94c057f9c2b  *  0.0.0.0/0  172.19.0.3
...
```

These rules say: "Drop any packet NOT coming from the bridge interface that is destined for this container IP." This blocks return traffic from the internet — when the container sends a SYN, the response comes through eth0 (not the bridge), gets dropped, and the host generates a RST.

The `raw` table is processed BEFORE `conntrack`, so even `ESTABLISHED,RELATED` rules in other tables can't help.

## Diagnosis

```bash
# 1. tcpdump on the bridge shows SYN going out and RST coming back in SAME millisecond
sudo tcpdump -i br-f94c057f9c2b -n host 172.19.0.3 -c 5
# Output: SYN → RST with same timestamp = locally generated RST

# 2. Check raw table
sudo iptables -t raw -L PREROUTING -n --line-numbers
# Look for per-container-IP DROP rules
```

## Fix

Delete the raw table DROP rules:

```bash
set +H  # disable bash history expansion for !
sudo iptables -t raw -D PREROUTING ! -i br-f94c057f9c2b -d 172.19.0.2 -j DROP
sudo iptables -t raw -D PREROUTING ! -i br-f94c057f9c2b -d 172.19.0.3 -j DROP
# ... repeat for each container IP
```

**Syntax notes:**
- `!` must come BEFORE `-i`, not after: `! -i br-xxx` not `-i !br-xxx`
- Bash interprets `!` as history expansion — use `set +H` first
- Single quotes don't work: `'!br-xxx'` makes `!` part of the interface name (too long)

## Persistence

These rules are re-added by Aliyun's security agent on reboot. Options:
1. Cron job: `@reboot /path/to/fix-iptables.sh`
2. Systemd service that runs after docker.service
3. Aliyun security group agent configuration (if available)

## Related

This is SEPARATE from the NAT masquerade issue. Both must be fixed:
- NAT: translates source IP for outbound packets
- Raw table: blocks return traffic before conntrack

See also: Docker container outbound connectivity in SKILL.md
