# Home Channel Configuration

Home channels are the default destination for cron job delivery and
cross-platform message routing when no specific chat ID is provided.

## How Home Channels Are Stored

Home channels persist in `~/.hermes/.env` as environment variables.
The `/sethome` slash command (run from any gateway chat) writes these
automatically. You can also set them manually.

### Env Var Naming Convention

| Platform   | Home channel env var         | Thread ID env var (optional)     |
|------------|------------------------------|----------------------------------|
| Telegram   | `TELEGRAM_HOME_CHANNEL`      | `TELEGRAM_HOME_CHANNEL_THREAD_ID`|
| Discord    | `DISCORD_HOME_CHANNEL`       | `DISCORD_HOME_CHANNEL_THREAD_ID` |
| Slack      | `SLACK_HOME_CHANNEL`         | -                                |
| Signal     | `SIGNAL_HOME_CHANNEL`        | -                                |
| Feishu     | `FEISHU_HOME_CHANNEL`        | `FEISHU_HOME_CHANNEL_THREAD_ID`  |
| WeCom      | `WECOM_HOME_CHANNEL`         | -                                |
| Weixin     | `WEIXIN_HOME_CHANNEL`        | -                                |
| QQBot      | `QQBOT_HOME_CHANNEL`         | -                                |
| DingTalk   | `DINGTALK_HOME_CHANNEL`      | -                                |
| Matrix     | `MATRIX_HOME_ROOM`           | -                                |
| Mattermost | `MATTERMOST_HOME_CHANNEL`    | -                                |
| Email      | `EMAIL_HOME_ADDRESS`         | -                                |
| SMS        | `SMS_HOME_CHANNEL`           | -                                |
| WhatsApp   | `WHATSAPP_HOME_CHANNEL`      | -                                |

Legacy aliases: `QQBOT_HOME_CHANNEL` was formerly `QQ_HOME_CHANNEL`.

### Display Name (optional)

Some platforms also support `{PLATFORM}_HOME_CHANNEL_NAME` for a
human-readable label used in logs and dashboard display.

## Checking Current Home Channels

```bash
# Show all non-commented home channel settings
grep -i "HOME_CHANNEL\|HOME_ROOM\|HOME_ADDRESS" ~/.hermes/.env | grep -v "^#"
```

### channel_directory.json

`~/.hermes/channel_directory.json` tracks all known channels per
platform that the bot has seen. Useful for finding chat IDs to use as
home channels. Format:

```json
{
  "platforms": {
    "feishu": [{"id": "oc_xxx", "name": "...", "type": "dm", "thread_id": null}],
    "weixin": [{"id": "o9xxx@im.wechat", "name": "...", "type": "dm"}]
  }
}
```

### gateway_state.json

`~/.hermes/gateway_state.json` shows live platform connection states
(`connected`, `retrying`, etc.) — check this when home channel delivery
fails to rule out platform connectivity issues.

## Setting Home Channels

### Method 1: /sethome (preferred)

From the chat you want as home, send `/sethome`. This writes the env
vars and updates the running gateway config in one step.

### Method 2: Manual .env edit

```bash
# Edit .env directly
FEISHU_HOME_CHANNEL=oc_xxxxxxxxxxxxxxxx
FEISHU_HOME_CHANNEL_THREAD_ID=          # leave empty for DMs
```

Then restart: `hermes gateway restart`

## How Home Channels Are Used

- **Cron delivery**: `deliver="feishu"` without explicit chat ID routes
  to `FEISHU_HOME_CHANNEL`
- **Gateway startup notifications**: "Gateway online" messages go to
  home channels (if `gateway_restart_notification: true` for that
  platform)
- **Cross-platform handoff**: `/handoff <platform>` routes to the
  target platform's home channel

## Source Code Reference

- `HomeChannel` dataclass: `gateway/config.py`
- Env var registry: `cron/scheduler.py::_HOME_TARGET_ENV_VARS`
- `/sethome` handler: `gateway/slash_commands.py::_handle_set_home_command`
- Env var resolver: `gateway/run.py::_home_target_env_var()`
