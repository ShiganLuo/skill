---
name: kde-wayland-desktop
version: 1.0
license: MIT
description: "Use when KDE Wayland 桌面故障：fcitx5 输入失效、主题自动变黑、显示器不出图."
metadata:
  hermes:
    tags: [linux, kde, plasma, wayland, fcitx5, ime, theme, display]
    related_skills: [linux-hardware-troubleshooting, linux-system-administration]
tags: [linux, kde, plasma, wayland, fcitx5, ime, theme, display]
author: curator
---

# KDE Plasma Wayland 桌面故障排查

适用：KDE Plasma 6.x + Wayland + fcitx5 环境（Kubuntu/Ubuntu 系）。四大高频故障模式，每个模式都先取证据再动手。

## When to Use

- 应用里中文打不出来（尤其 Chromium 系 Chrome/VSCode/Obsidian），但其他应用正常
- 主题在夜间/锁屏后自动变黑，关掉系统设置里的"夜间切换"开关仍复现
- 显示器/内屏 connected 但无画面，怀疑被软件禁用
- 外接屏分辨率突然骤降（只剩 640x480），尤其在睡眠唤醒之后
- 熄屏后网络消失，怀疑和睡眠/挂起有关
- 需要判断某应用跑在原生 Wayland 还是 XWayland、输入法走哪条链路

## 模式一：fcitx5 中文输入在某些应用失效

### 本质：两条互不相通的输入链路

| 链路 | 路径 | 何时使用 |
|------|------|----------|
| IM-module 链路 | 应用 → `GTK_IM_MODULE`/`QT_IM_MODULE=fcitx` → fcitx5 (DBus 直连) | 工具包应用显式设了环境变量时，**与显示后端无关** |
| Wayland text-input 链路 | 应用 → 合成器 → IME（三方协议） | 原生 Wayland 后端且启用了 IME 支持 |

判据：**后端 × 该后端下应用实现的链 × 链两端在听**，三者交集非空才能打字。Chromium 系跑原生 Wayland 时放弃链 1，链 2 又默认关闭（`--enable-wayland-ime` 未设）且默认 text-input **v1** 而合成器要 v3 → 两条链皆断 → 按键直达应用、IME 被旁路，**无报错无提示**。

### 诊断（30 秒定位）

```bash
p=$(pgrep -x chrome | head -1)
ls -l /proc/$p/fd | grep -c wayland    # >0 (memfd:wayland-*) = 原生 Wayland
tr '\0' ' ' < /proc/$p/cmdline          # 有无 --ozone-platform=x11
fcitx5-diagnose                          # InputContext 列表里没有该应用 = 根本没来连
```

**wayland fd > 0 且 cmdline 无 x11 flag → 中文必挂。** 对照组：能打字的应用（Qt、微信/QQ 等 XWayland 应用）走的都是链 1。

### 修复（实测可用的路线：强制 XWayland）

1. 图形启动的应用 → 改**用户目录副本**（别动 /usr/share，升级会覆盖）：

```bash
cp /usr/share/applications/<app>.desktop ~/.local/share/applications/
sed -i 's|^Exec=<bin>|Exec=<bin> --ozone-platform=x11|' ~/.local/share/applications/<app>.desktop
# 注意所有 Exec 行（含 --new-window、--incognito 变体）
update-desktop-database ~/.local/share/applications
```

2. 终端启动（`code .`）→ 不走 .desktop，加 alias：`alias code='code --ozone-platform=x11'`

备选路线（保留原生 Wayland）：`--enable-wayland-ime --wayland-text-input-version=3`（Chromium 默认 v1，必须显式指定 v3）。**两组 flag 不可混用**。

### 坑：Chromium 单实例吞 flag（真实踩过，曾据此误判"flag 无效"）

旧进程开着时执行 `app --flag`，新进程只把参数转交旧进程就退出，**flag 静默丢弃**。必须完全退出（关窗口 ≠ 退出，注意"关闭后继续后台运行"）再启动。修复后必须回读验证：

```bash
tr '\0' ' ' < /proc/<pid>/cmdline        # 应含 flag
ls -l /proc/<pid>/fd | grep -c wayland   # 应为 0
```

## 模式二：主题自动变黑（关了"夜间切换"开关还会变黑）

### 本质：两个开关，配置文件里那个只是门面

- `kdeglobals [KDE] AutomaticLookAndFeel` → KCM 界面勾对应的键，只管时间表分支
- **kded6 常驻模块 `lookandfeelautoswitcher`** → 真正干活的，登录起常驻，双触发链：`KDarkLightSchedule`（日出日落）+ `KIdleTime`（**闲置/锁屏**）。闲置分支不看那个键 → 改文件治不了不读文件的常驻进程

### 证据链（识别"整套 LAF 被应用"）

```bash
journalctl --user -b | grep 'New theme'        # snapd-desktop-integration: icon=breeze-dark = 精确时刻
find ~/.config -maxdepth 2 -newermt "HH:MM" -type f -printf '%TH:%TM %p\n' | sort
    # kdeglobals/kwinrc/gtk-3.0//gtk-4.0//kdedefaults//plasmarc 同一分钟全被写 = LAF 整套应用特征
grep -c lookandfeelautoswitcher /proc/$(pgrep -x kded6)/maps   # >0 = 模块常驻已加载
gdbus introspect --session --dest org.kde.kded6 --object-path /kded   # 拿可用方法
```

### 修复（永久）

```bash
gdbus call --session --dest org.kde.kded6 --object-path /kded \
  --method org.kde.kded6.unloadModule lookandfeelautoswitcher        # 本会话关死
kwriteconfig6 --file kded6rc --group Modules --key lookandfeelautoswitcher false   # 跨登录
plasma-apply-lookandfeel -a org.kubuntulight.desktop                 # 重新应用浅色
```

验证：`isModuleAutoloaded` 返回 `(false,)`、`loadedModules` 不含该模块、`LookAndFeelPackage` 为 light。残余风险：模块 `isModuleLoadedOnDemand=(true)`，系统设置里再碰"夜间切换"勾会按需复活它——别动那个勾。

## 模式三：内屏/显示器不出图

先分辨软件禁用 vs 硬件故障：

```bash
kscreen-doctor -o                            # 输出里 disabled 但 connected = 软件禁用
cat /sys/class/drm/card*-eDP-*/status        # connected = 面板 EDID 正常（硬件活着）
cat /sys/class/drm/card*-eDP-*/enabled
kscreen-doctor output.eDP-2.enable           # 软件禁用的修复
```

connected + disabled → 不是硬件坏，是 KWin/kscreen 把输出关了（常见于 GPU 重置/热插拔事件后输出重排、盖子事件）。启用后 sysfs `enabled` 应变 enabled，再让用户看物理屏幕。

### 更深一层：连接器根本不存在/永远 disconnected = dGPU 驱动没加载（外接屏接在 NVIDIA 卡上）

混合显卡本外接口（HDMI/DP）物理上多挂在 NVIDIA dGPU。NVIDIA 模块没加载时这些口在硬件层就是死的——插线也不触发 HPD，`card*-DP-*/HDMI-*` 要么不存在要么永远 disconnected，设置界面无从调起。

判据链（外接屏"完全没反应"时先跑这条再想 kscreen）：

```bash
for c in /sys/class/drm/card*-*/status; do echo "$c: $(cat $c)"; done
# 只见 iGPU 的 card + eDP，无 NVIDIA card 或其口全 disconnected
journalctl -b -k | grep 'HDA NVidia'      # HDMI/DP 音频 pin 在 dGPU 地址 = 视频口也在 dGPU
lsmod | grep -c nvidia                     # 0 = 模块没加载
sudo modprobe nvidia 2>&1                  # "Key was rejected by service" = Secure Boot 拒签
```

Secure Boot 拒签时最省事的修法不是折腾 MOK 登记（实测 `mokutil --import` + 蓝屏确认后仍可能静默失败、pending 请求消失），而是改用 Ubuntu 官方签名的模块：`linux-modules-nvidia-580-<kernel>` 装的模块在 `kernel/nvidia-580/`（Canonical 签名，SB 直接认），常被 `updates/dkms/` 里本机 MOK 签名的 DKMS 模块遮蔽（depmod 解析优先级 updates/dkms 更高）。修法：

```bash
modinfo nvidia | grep filename             # 若指向 updates/dkms = 被遮蔽
sudo mkdir -p /root/dkms-nvidia-backup
sudo mv /lib/modules/$(uname -r)/updates/dkms/nvidia*.ko.zst /root/dkms-nvidia-backup/
sudo depmod -a $(uname -r)
sudo modprobe nvidia nvidia-drm nvidia-modeset
```

验证：`nvidia-smi -L` 有输出、`/sys/class/drm/` 出现新 card 带 HDMI/DP 口且 connected、`kscreen-doctor -o` 自动列出该输出。物理屏仍黑则拔插一次线触发 HPD。

坑：换内核后 DKMS 会把 MOK 签名模块重新塞回 `updates/dkms/`，问题复发时同法再移一次；根治可卸载 `nvidia-dkms-580` 只留官方模块。

## 模式四：外接屏分辨率骤降（只剩 640x480）

### 本质：EDID 读失败，内核回退 VESA 兜底模式

分辨率不来自系统设置，而来自显示器经 DDC 上报的 EDID（含详细时序描述符 DTD）。EDID 读回无效 → 内核 modes 列表只剩兜底的 640x480，KWin/系统设置里怎么调都无济于事——问题在 sysfs 层，不在设置界面。高发触发：睡眠唤醒瞬间，GPU modeset 与 USB-C 扩展坞/转接头重新上电并发竞争，DDC 读早于设备就绪 → 读回一坨零。

### 诊断（判据链，三步钉死）

```bash
kscreen-doctor -j                          # 每块屏 currentModeId/modes/pos（-l 参数无效，列输出用 -o 或 -j）
cat /sys/class/drm/card*-<CONN>/modes      # 只有 640x480 = EDID 坏，不是设置问题
xxd /sys/class/drm/card*-<CONN>/edid       # 头 00ff..ff00 正常但 0x36-0x7D 全零 = DTD 空
journalctl -b -k | grep -iE 'suspend exit|reset full-speed|Digital AV'   # 唤醒 + 转接头重枚举时刻
journalctl --user -b | grep 'Adding view'  # sddm-greeter 记录各屏历史分辨率 = 正常值对照（如 1920x1080）
```

判据：modes 只剩 640x480 + EDID 描述符全零 + journal 里同刻有 resume/USB 重枚举 = 根因钉死。哪块是"左屏"看 `kscreen-doctor -j` 的 `pos.x`（x=0 即最左），别猜接口名。

### 修复

拔插该屏线缆/转接头触发 EDID 重读，回读 `modes` 应恢复原生分辨率列表（需用户动手，别在设置界面空转）。根因是睡眠唤醒竞争——只要还允许自动睡眠就有概率复发，根治=关自动睡眠（KDE 系统设置→电源管理→睡眠改"关闭"）。

### 坑

- EDID 无效时 kscreen-doctor/KCM 设不了原生模式——内核根本没提供该 mode。
- `kwin: EDID colorimetry ... is invalid` 只是警告，不是根因，别追。
- 混合显卡机器外接口可能挂在独显 cardN 上（`lspci | grep -E 'VGA|3D'` 先认清 card1/card2 归属）。

## 附：熄屏后网络消失（先判定是不是睡眠断的）

熄屏本身不断网；真正的断网者通常是**熄屏后触发的自动挂起**。NM 挂起时主动断网是设计行为（它持有 systemd-inhibit "NetworkManager needs to turn off networks"），睡眠期间网络物理上不可能保持（无线电断电、TCP 会死），所以"睡眠不断网"只能靠不睡眠。

```bash
journalctl --since "-1 day" | grep -E 'PM: suspend (entry|exit)'        # 挂起/唤醒时刻
journalctl -u NetworkManager --since "-1 day" | grep -E 'sleep requested|ASLEEP|sleeping'
grep -A2 SuspendSession ~/.config/powermanagementprofilesrc             # idleTime>0 = 自动睡眠开着
```

判据：NM 的 `sleep requested → DISABLED (ASLEEP) → deactivated (reason 'sleeping')` 与 `PM: suspend entry` 同刻 = 睡眠断网，不是网络故障。处理：KDE 系统设置→电源管理→睡眠改"关闭"（只熄屏+锁屏，机器保持运行）。改 powerdevil 配置优先走设置界面——直接改 `powermanagementprofilesrc` 有被运行中的 powerdevil 覆写且不热生效的风险；用户可能中途接管这类系统配置修改，改动后要把"改了什么、是否已生效"交接清楚再停手。

## 附：查全局快捷键（KWin/Plasma）

用户问"XX 的快捷键是什么"时不要凭记忆答，直接读配置（系统设置→快捷键界面也走同一份数据）：

```bash
grep -n -E 'Expose|Overview|DesktopGrid|Show' ~/.config/kglobalshortcutsrc
```

行格式 `名称=当前生效,默认值,描述`，同一字段内 `\t` 分隔多个备选键（当前文件可能已被用户改过，以当前值为准，别照抄文档默认值）。Plasma 6 实测基线：

| 效果 | 键 |
|------|-----|
| Overview 总览（窗口缩略+搜索） | Meta+W |
| Present Windows 当前桌面 | Meta+F9 / Ctrl+F9 |
| Present Windows 全部桌面（"所有应用缩小页"） | Meta+F10 / Ctrl+F10 |
| Present Windows 同类窗口 | Meta+F7 / Ctrl+F7 |
| 桌面网格（虚拟桌面并排） | Ctrl+F8 |

## 附：桌面通知排障（Gmail/Chrome 通知不弹）

三层链路，逐层独立验证，每层都要实测证据、不能只看设置显示：

1. **浏览器站点权限**：别信自动化会话里的 `Notification.permission`（agent 的 Chrome 实例与用户日常实例是不同 profile，读数互相无关）——读用户真实配置文件：
   ```bash
   python3 -c "import json; p=json.load(open('/home/<USER>/.config/google-chrome/Default/Preferences')); print(p['profile']['content_settings']['exceptions']['notifications'])"
   ```
   setting=1 允许 / 2 拒绝。注意 Web 通知还有**第二道闸**：Gmail 等站点自己的设置（Gmail 设置→常规→桌面通知，默认停用且藏在"常规"标签页）。
2. **OS 通知服务**：`qdbus`/`busctl` 查 `org.freedesktop.Notifications` 归属（plasmashell 持有 = KDE 正常）；`gsettings get org.gnome.desktop.notifications show-banners` = true 为勿扰关闭。
3. **端到端弹窗验证**（发一条以 chrome 名义的测试通知并**截图确认**，口头"应该弹了"不算数）：
   ```bash
   gdbus call --session --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications \
     --method org.freedesktop.Notifications.Notify "google-chrome" 0 "" "测试标题" "测试正文" [] '{}' 10000
   spectacle -b -n -o /tmp/screen.png   # wayland 下截图，vision_analyze 读弹窗
   ```
   busctl 调 Notify 的签名拼写易错，gdbus 更省事。实践教训：本会话两次误报根因（一次读了错误 profile 的权限、一次没实测弹窗就说"链路通"），都被用户纠正——**每层结论必须来自该层的直接证据**。

常见用户误区（排障时先澄清）：Web 通知要求 Gmail 标签页保持打开（Chrome 进程活着即可，不必前台）；要"浏览器解耦"的常驻通知，方案是 Thunderbird + IMAP 或把 Gmail 装成 PWA。

## 模式五：SSH 端入侵木马取证（"这服务器是不是被攻击了"）

触发：`/etc/cron.d/` 出现不明文件且 root `rm` 报 `Operation not permitted`，或用户直接问服务器是否被入侵。这不是权限问题——`lsattr` 的 `a` = append-only，root 须先 `chattr -a`。挖矿木马正是用这手法锁持久化文件。清理需真 root（ssh 进来 sudo 要密码时先向用户要密码，用 `sudo -S` 传 stdin）。完整流程（快速体检脚本、uid0 后门、ld.so.preload、多点持久化、入口判定、重装教训、集群横向排查）见 `references/linux-malware-ir.md`（lv/d419 实战：三轮载荷、潜伏 3 年、重装未清配置被搬回、内网横向）。

## 诊断纪律（用户明确纠正过）

1. **先找"谁写的/谁触发的"，不要在配置键之间无休止猜**：时间窗 journalctl、同分钟文件 cascade（find -newermt）、进程 /proc/maps、D-Bus introspect——这四类证据能把写入者钉死。
2. 视觉/渲染类问题第一动作是取实际状态或渲染证据（kscreen-doctor、截图、fd 检查），不是列假设。
3. 改完必须回读验证（cmdline、sysfs、isModuleAutoloaded）才能说修好了。

## 文档化到用户 Wiki 的结构（用户反馈过"文档不够本质"）

`现象 → 本质（第一性原理的机制模型，如"两条链路""两个开关"，从模型推导出表象，不罗列表面现象）→ 诊断（命令 + 判据）→ 修复（每步可验证）→ 坑`。本质优先，删掉冗余对比。
