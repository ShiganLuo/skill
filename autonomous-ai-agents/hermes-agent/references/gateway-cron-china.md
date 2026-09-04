# Gateway + Cron in China: Debugging Reference

## Problem
Hermes cron jobs created but never execute. `last_run_at` stays null.

## Root Cause Chain
1. Cron scheduler runs inside the Gateway process
2. Gateway requires at least one messaging platform to connect on startup
3. If all platforms fail (e.g. Telegram blocked by GFW), Gateway exits immediately
4. No Gateway → no cron scheduler → jobs never fire

## Diagnostic Commands
```bash
# Quick check: is scheduler alive?
hermes cron status
# Output shows: "✗ Gateway is not running — cron jobs will NOT fire"

# Check Gateway service
systemctl --user status hermes-gateway
# Shows: Active: activating (auto-restart) / failed

# Read logs for specific error
journalctl --user -u hermes-gateway -n 30 --no-pager
# Key error: "Gateway failed to connect any configured messaging platform: telegram: telegram connect timed out after 30s"
```

## Fix Options (China)
1. **Switch to China-accessible platform**: DingTalk, Feishu, WeCom, WeChat (Weixin)
2. **Proxy for Telegram**: Configure HTTP_PROXY/HTTPS_PROXY in .env
3. **Disable unreachable platforms**: Remove/comment Telegram config in config.yaml

## Verified Working Alternatives
- Feishu (飞书): Chinese Lark, no GFW issues
- DingTalk (钉钉): Alibaba, fully accessible
- WeCom (企业微信): WeChat Work, fully accessible

## Session: 2026-06-22
User set up daily bio-industry report cron job. Created at 21:30 on June 21.
Job didn't fire on June 22 at 9am. Diagnosed Gateway not running due to Telegram timeout.
Gateway had restarted 333 times (auto-restart loop) all failing with same error.

## Additional Diagnostic Signals
- **Restart counter in logs**: `restart counter is at N` in `journalctl` output. A high number (e.g. 333) confirms the Gateway has been crash-looping — no need to wait and observe, the problem is systemic.
- **`enabled_toolsets` on cron jobs**: Cron jobs can specify which toolsets they need (e.g. `["browser", "file"]`). If the job needs browser access, ensure `browser` toolset is enabled.
