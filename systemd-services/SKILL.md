---
name: systemd-services
version: 1.0
license: MIT
description: "Use when converting manual processes into systemd services."
metadata:
  hermes:
    tags: [linux, systemd, service, boot, daemon]
    related_skills: [linux-system-administration]
tags: [linux, systemd, service, boot, daemon]
author: curator
---

# systemd 服务化：手动进程 → 开机自启 + 崩溃自愈

把 nohup/前台跑的守护进程固化成系统服务，并能干净地删除。

## When to Use

- 手动启动的常驻进程（frps/frpc、自建后端、同步脚本守护）需要随机器重启而启动
- 服务启动失败（Address already in use、配置不生效、unit 改了没反应）
- 需要彻底删除一个自建服务（含软链与残留状态）

> 注意：`linux-system-administration` 也有 Service Management 章节（列举/启动/服务名），与本技能部分重叠，待 curator 合并。

## 单元文件模板

见 `templates/service-unit.conf`（复制到 `/etc/systemd/system/<name>.service` 后填路径）。三段结构与关键指令：

- `[Unit]` `After=` + `Wants=network-online.target`：**外连型客户端必须用 network-online**（network.target 只代表协议栈就绪，不代表网络连通；抢跑连不上只能靠 Restart 重试兜底）
- `[Service]` `User=` / `WorkingDirectory=` / `ExecStart=`：**从运行中的进程实测取值**，不猜
- `[Service]` `Restart=always` + `RestartSec=3`：守护进程全重启；间隔防打爆 CPU/日志
- `[Install]` `WantedBy=multi-user.target`：`enable` 建软链的指向

## 工作流

```bash
# 1. 从运行中的进程取事实（别猜路径）
ps -o user= -p <pid>                 # → User=（身份不一致会读不到配置/密钥）
readlink /proc/<pid>/exe             # → ExecStart=
readlink /proc/<pid>/cwd             # → WorkingDirectory=（相对路径 -c 配置依赖它）

# 2. 写 unit 文件后必须：
sudo systemctl daemon-reload         # 不执行则修改被忽略

# 3. 先停手动进程，再启服务（否则端口冲突 Address already in use）
kill <pid>
sudo systemctl enable --now <name>   # enable=开机自启(建软链)；--now=立即启动

# 4. 双问题验证
systemctl is-enabled <name>          # 重启后会不会自动起来？
systemctl is-active <name>           # 现在在不在跑？
journalctl -u <name> -f              # 日志（替代前台终端输出）

# 5. 最终验收：sudo reboot 后重复第 4 步
```

`enable` vs `start`：`start/stop` 只管当次开机，`enable/disable` 才是持久开关；两者都真才算部署完成。

## 删除服务（顺序有讲究）

```bash
sudo systemctl stop <name>
sudo systemctl disable <name>          # 删 multi-user.target.wants 软链
sudo rm /etc/systemd/system/<name>.service
sudo systemctl daemon-reload
sudo systemctl reset-failed <name>     # 可选：清掉反复崩溃留下的 failed 状态
```

只 `rm` 不 `disable` → 死软链残留；只 `stop` 不删 → 下次开机又起来；删完不做 `daemon-reload` → systemctl 仍显示旧信息。单元文件只是壳，删它不影响二进制和配置文件。

## 实战案例：frp 双端

公网 frps / 内网 frpc 同模板，仅 ExecStart 不同。要点：

- frpc 的 `serverAddr` 必须是**公网服务器地址**——写 127.0.0.1 只有在与 frps 同机（自测）时才对；部署错机器是常见翻车点
- frpc 报 `connection refused` 是**上游症状**：先查 frps 是否在跑、7000 端口是否有人监听，而不是修 frpc
- frpc 晚于 frps 开机没关系：`Restart=always` + 自带重连会一直重试
