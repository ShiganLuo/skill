# 桌面通知排查配方（Linux KDE + Chrome + Web 应用，2026-10 Gmail 实测）

「XX 没有桌面提醒」这类问题的排查顺序与证据链。核心教训：**逐层验证、自证，别让用户操作，也别凭单点证据下结论**。

## 三层链路（每层独立验证）

```
Web 应用设置(Gmail 自己的开关) → 浏览器站点权限(chrome 通知授权) → OS 通知系统(KDE/GNOME 通知服务)
```

任何一层断了都静默无提醒，且三层的问题症状完全一样（= 没弹窗），必须逐层区分。

## 层 3：OS 通知链路（先测这层，最底层）

不经过 Chrome/应用，直接打系统通知：

```bash
notify-send "测试" "链路验证"        # 最简
# 或带应用名（模拟 Chrome 来源）：
gdbus call --session --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.Notify \
  "google-chrome" 0 "" "标题" "正文" [] '{}' 8000
```

**弹了 = OS 层正常**，问题在应用或权限层；不弹 = 查系统勿扰（`gsettings get org.gnome.desktop.notifications show-banners`）和通知服务（`busctl --user list | grep Notifications`，KDE 由 plasmashell 持有）。

**"弹没弹"要自证，别问用户**：`spectacle -b -n -o /tmp/shot.png` 截屏后 vision 看图确认（发通知后 sleep 1.5 再截）。2026-10 实测：截图确认 gdbus 发的通知以 google-chrome 名义正常弹出。

## 层 2：浏览器站点权限（容易查错的一层）

**坑：自动化会话里 `Notification.permission` 不可信。** Hermes 拉起的 Chrome 实例和用户日常的 Chrome 是不同 profile，自动化实例里读到 `denied` 不代表用户实例的状态。真实状态读用户 profile 的 Preferences 文件：

```bash
python3 - << 'EOF'
import json, glob
for pd in glob.glob("/home/<user>/.config/google-chrome/*/Preferences"):
    prefs = json.load(open(pd))
    cset = (prefs.get("profile", {}).get("content_settings", {})
            .get("exceptions", {}).get("notifications", {}))
    for site, v in cset.items():
        print(pd.split("/")[-2], site, "->", v.get("setting"))  # 1=allow 2=block
EOF
```

若权限曾是"拒绝"，网页再请求也不会弹框，必须去 `chrome://settings/content/siteDetails?site=<url>` 手动改回允许。

## 层 1：Web 应用自己的开关

浏览器权限只是"不拦"，应用自己还得"发"。**Gmail 的桌面通知开关藏在 设置→常规→桌面通知**，默认"停用"——这是最容易被漏的一层（Chrome 权限允许 + OS 链路正常，Gmail 自己不发，照样没提醒）。注意别把设置页停在"标签"等其他分类就以为检查过了（2026-10 实测：用户开着设置页但停在标签分类）。

## 用户交互纪律

- **"不要让我去操作"（用户原话）**：能自己查/自己做的（读配置文件、发测试通知、截图验证）全部自己做，只把必须人手的动作（如点 Gmail 设置开关）留给用户，并给出精确到点击的位置。
- 用户反问"你是怎么查询的"时，说明查询方法可能有问题——重新用更权威的数据源验证（Preferences 文件 > 自动化实例读数），查错要明确认错并给出更正后的事实。
