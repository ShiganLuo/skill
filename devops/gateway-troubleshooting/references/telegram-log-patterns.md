# Telegram Log Patterns (from real diagnostics)

## Pattern: GFW Network Blocking (no proxy configured)

```
# Reconnection loop with exponential attempts:
2026-07-13 07:25:21,063 INFO gateway.run: Reconnecting telegram (attempt 628)...
2026-07-13 07:25:21,150 WARNING hermes_plugins.telegram_platform.adapter: [Telegram] Discovering Telegram API fallback IPs via DNS-over-HTTPS…
2026-07-13 07:25:31,178 INFO plugins.platforms.telegram.telegram_network: DoH discovery yielded no usable IPs (system DNS: unknown); using seed fallback IPs 149.154.166.110, 149.154.167.220
2026-07-13 07:25:31,180 INFO hermes_plugins.telegram_platform.adapter: [Telegram] Telegram fallback IPs active: 149.154.166.110, 149.154.167.220
2026-07-13 07:25:31,266 WARNING hermes_plugins.telegram_platform.adapter: [Telegram] Connecting to Telegram (attempt 1/8)…
# Then: telegram.error.TimedOut on get_me() call
```

The adapter's fallback IP mechanism (DoH → seed IPs) is internal to the python-telegram-bot library. When the network is completely blocked, even the fallback IPs fail.

## Pattern: No Bot Token (platform skipped entirely)

```
# After restart, no Telegram log lines at all — just:
2026-07-13 07:25:44,393 WARNING gateway.run: No messaging platforms enabled.
```

This means no platform credentials were found in .env. The Telegram adapter is never instantiated.

## Pattern: Token Set But No Allowlist

```
WARNING gateway.run: No env user allowlists configured. Messaging platforms default to pairing/allowlist policies and will deny unknown senders unless you configure platform allowlists (e.g., TELEGRAM_ALLOWED_USERS=your_id) or explicitly opt in with GATEWAY_ALLOW_ALL_USERS=true plus dm_policy/group_policy: open on the platform.
```

The platform IS connecting (token is valid), but incoming messages from unknown users will be rejected.

## Pattern: state.db Malformed (accompanies gateway restarts)

```
WARNING hermes_state: state.db dedup repair pass failed: database disk image is malformed
ERROR hermes_state: state.db schema repair could not recover /home/user/.hermes/state.db automatically (backup: /home/user/.hermes/state.db.malformed-backup-YYYYMMDD_HHMMSS); manual restore from backup may be required.
```

The gateway continues running with a fresh empty DB. Session history is lost but functionality is preserved. Multiple malformed backups can accumulate across restarts.
