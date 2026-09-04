# nftables Interception — Cases Where iptables Shows Nothing Wrong

## The Core Problem

`iptables -L` and `nft list ruleset` show DIFFERENT things:
- `iptables -L` → only iptables-managed chains/tables
- `nft list ruleset` → ALL netfilter rules, including nft-native tables

Tools that create nft-native tables (invisible to iptables):
- **firewalld** (uses nft backend on modern systems)
- **mihomo / Clash Meta** (transparent proxy)
- **nftables-native firewall scripts**
- **1Panel / BT-Panel** (may use nft on newer versions)

## Case 1: firewalld Residual Rules

**Symptom**: Container TCP connections fail, ICMP may work. `iptables -L` shows everything正常.

**Root cause**: firewalld was stopped/disabled but its nftables table persists:
```
table inet firewalld {
    chain forward {
        policy drop;    ← THIS blocks all forwarded traffic
        reject ...
    }
}
```

**Fix**:
```bash
sudo nft delete table inet firewalld
sudo nft delete table ip firewalld
sudo nft delete table ip6 firewalld
```

**Key detail**: firewalld's nft table has `priority filter` on the forward chain, same as Docker's DOCKER-FORWARD. The `policy drop` acts as a catch-all after all explicit rules, silently dropping container traffic.

## Case 2: mihomo / Clash Meta Transparent Proxy

**Symptom**: Container can ping external IPs but TCP connections fail with immediate RST. tcpdump on bridge shows SYN→RST in same microsecond. tcpdump on eth0 shows nothing. MASQUERADE counter increments but source IP is NOT translated.

**Root cause**: mihomo creates an `inet mihomo` table with prerouting chain that redirects all TCP to a local proxy port:
```
table inet mihomo {
    set inet4_local_address_set {
        type ipv4_addr
        flags interval
        elements = { 127.0.0.0/8, 172.17.0.0-172.19.255.255,
                     172.21.224.0/20, 192.168.100.0/24 }
    }

    chain prerouting {
        type nat hook prerouting priority dstnat + 1; policy accept;
        ...
        ip daddr @inet4_local_address_set counter ... return     ← local traffic passes
        meta nfproto ipv4 meta l4proto tcp counter ... redirect to :44907  ← ALL other TCP → proxy
    }
}
```

**Why it's subtle**:
- Container-to-container traffic works (destination in local address set → return)
- Container-to-host traffic works (destination in local address set → return)
- Container-to-external-TCP fails (destination NOT in local set → redirect to proxy)
- ICMP works (only TCP is redirected)
- The prerouting priority `dstnat + 1` runs AFTER Docker's DNAT, so it intercepts outbound traffic that Docker DNAT doesn't handle

**Why bridge-nf-call-iptables matters**:
- `bridge-nf-call-iptables=1`: bridge traffic goes through nftables → mihomo intercepts → packet never reaches eth0
- `bridge-nf-call-iptables=0`: bridge traffic bypasses nftables → mihomo doesn't intercept → but MASQUERADE also doesn't apply → source IP not translated → VPC rejects

**Fix**:
```bash
sudo nft delete table inet mihomo
```

**Verification**:
```bash
# Should return 200
docker exec <container> curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/
```

## Diagnostic Flow

When containers can't reach external internet but iptables looks correct:

```bash
# Step 1: Check nftables — this often reveals the culprit immediately
sudo nft list ruleset | grep -E '^table ' | grep -v -E 'ip filter|ip nat|ip raw|ip mangle|ip6 |bridge '

# Step 2: If non-Docker tables found, check their chains
sudo nft list table inet <suspicious_table>

# Step 3: Look for prerouting/forward chains with DROP/redirect/policy drop
# Step 4: Delete the offending table
sudo nft delete table inet <offending_table>

# Step 5: Verify
docker exec <container> curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://www.baidu.com/
```

## Why This Is Common on Cloud VPS

Cloud VPS images often come with:
- 1Panel/BT-Panel (installs firewalld with nft backend)
- Pre-installed proxy tools (mihomo, Clash, v2ray)
- Custom security hardening scripts using nftables

These tools create nft-native rules that persist even after the service is stopped or uninstalled. The standard Docker troubleshooting guide (`iptables -L FORWARD`, check MASQUERADE, check ip_forward) completely misses these.
