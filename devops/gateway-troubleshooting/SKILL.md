---
name: gateway-troubleshooting
description: "Diagnose and fix Hermes gateway platform connectivity — Telegram, Discord, Slack, and other messaging adapters. Covers service lifecycle, log analysis, network reachability, proxy/GFW configuration, and state.db corruption recovery."
version: 1.0.0
author: luosg
metadata:
  hermes:
    tags: [gateway, telegram, discord, troubleshooting, networking, proxy]
---

# Gateway Troubleshooting

Diagnose and fix Hermes gateway platform connectivity issues. Covers service management, log analysis, platform-specific errors, network blocking (GFW), proxy configuration, and state.db corruption.

## Quick Diagnostic Flow

```bash
# 1. Service status
hermes gateway status
systemctl --user status hermes-gateway

# 2. Recent logs (platform-specific grep)
tail -100 ~/.hermes/logs/gateway.log | grep -i "telegram\|error\|failed\|TimedOut\|connected"

# 3. Config check
grep -E "^TELEGRAM_|^GATEWAY_ALLOW|^DISCORD_|^SLACK_" ~/.hermes/.env

# 4. Network test (replace api.telegram.org with target platform)
curl -s --connect-timeout 5 https://api.telegram.org
```

## Service Lifecycle Pitfalls

### `hermes gateway restart` hangs but succeeds
The command can timeout (20s+) while the underlying systemd restart completes. Always verify after a seemingly hung restart:
```bash
hermes gateway status
# or
systemctl --user status hermes-gateway
```

### Starting a second gateway while systemd service runs
Hermes blocks this with: "A gateway is already running under systemd (user)". Running two gateways corrupts the kanban DB. Use `hermes gateway restart` or `hermes gateway stop && hermes gateway start`.

### Gateway dies on SSH logout
```bash
sudo loginctl enable-linger $USER
```

### Gateway crash loop (systemd marks failed)
```bash
systemctl --user reset-failed hermes-gateway
hermes gateway restart
```

## Telegram-Specific

### Key log patterns
- `telegram.error.TimedOut` — cannot reach Telegram API (network/firewall/GFW)
- `Reconnecting telegram (attempt N)` — persistent loop, usually network
- `No messaging platforms enabled` — bot token missing or not loaded
- `DoH discovery yielded no usable IPs` — DNS-over-HTTPS fallback for Telegram IP resolution failed; uses seed IPs (149.154.166.110, 149.154.167.220)

### Required .env config
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   # from @BotFather
TELEGRAM_ALLOWED_USERS=123456789        # numeric user IDs, comma-separated
# OR:
GATEWAY_ALLOW_ALL_USERS=true            # less secure, for testing
```

Without allowlist, gateway warns: "No env user allowlists configured... will deny unknown senders"

### Token invalid vs network blocked
- **Token invalid**: API returns `{"ok":false,"error_code":401,"description":"Unauthorized"}` → fix the token
- **Network blocked**: curl times out or returns empty → need proxy

### GFW / Network Blocking (China mainland)
```bash
# Check for existing local proxies
ss -tlnp | grep -E "1080|7890|8080|10808|10809|20170|20171"
env | grep -i proxy
```

Configure proxy in `~/.hermes/.env`:
```
TELEGRAM_PROXY_URL=socks5://127.0.0.1:10808
# or: socks5h:// (DNS through proxy — useful when DNS is also blocked)
# or: http://proxy-host:port
```
Restart: `hermes gateway restart`

## state.db Corruption

Symptom: `WARNING hermes_state: state.db dedup repair pass failed: database disk image is malformed`

Recovery:
```bash
# Check backup sizes — largest is most complete
ls -la ~/.hermes/state.db.malformed-backup-*
# Restore from best backup
cp ~/.hermes/state.db.malformed-backup-YYYYMMDD_HHMMSS ~/.hermes/state.db
hermes gateway restart
```
The gateway auto-creates backups before attempting repair. Multiple backups accumulate — safe to prune old ones. If no good backup exists, deleting state.db lets Hermes recreate it (loses session history but restores functionality).

## Home Channel Configuration

Home channels are the default destination for cron delivery and cross-platform
routing. They persist in `~/.hermes/.env` as `<PLATFORM>_HOME_CHANNEL` env vars.

**Quick check:**
```bash
grep -i "HOME_CHANNEL\|HOME_ROOM\|HOME_ADDRESS" ~/.hermes/.env | grep -v "^#"
```

Set via `/sethome` from the target chat (preferred), or edit `.env` manually.
Full reference: [references/home-channel-configuration.md](references/home-channel-configuration.md)

## General Platform Checklist

For any platform adapter failing to connect:

1. **Service running?** → `hermes gateway status`
2. **Credentials set?** → `grep PLATFORM ~/.hermes/.env`
3. **Platform enabled?** → check `config.yaml` platform section is not empty
4. **Network reachable?** → `curl` the platform API endpoint
5. **Firewall/proxy?** → check `ss -tlnp`, env proxy vars, platform-specific proxy config
6. **Rate limited?** → check logs for 429/rate-limit responses
7. **Bot permissions?** → platform-specific (Discord: Message Content Intent; Slack: message.channels subscription)
