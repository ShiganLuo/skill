---
name: skills-sync
version: 1.0
license: MIT
description: "Use when syncing ~/.hermes/skills across multiple servers."
metadata:
  hermes:
    tags: [rsync, skills, sync, backup, multi-server]
    related_skills: [rsync-file-sync]
tags: [rsync, skills, sync, backup, multi-server]
author: <USER>
---

# Hermes Skills 多机同步

## When to Use

- 用户要求同步/分发 Hermes skills 到其他服务器，或从远端拉取 skills
- 用户提到 rsync.sh（skills 目录那个）要改方向、加服务器、改参数
- 同步后报告远端 skill 缺失/多余，怀疑 push/pull 方向或 --delete 语义问题

## 概况

三台服务器之间同步 `~/.hermes/skills/`，脚本：`/home/<USER>/.hermes/skills/rsync.sh`（脚本本身放在 skills 目录里，会随同步分发到各机）。

## 用法

```bash
~/.hermes/skills/rsync.sh <zhang_c2|math_zhou|lv> [push|pull]
```

- push = 本地 → 远端；pull = 远端 → 本地
- 省略 direction 用分支默认：zhang_c2=pull，math_zhou/lv=push（沿用历史行为）
- 两方向都带 `--delete`：目标严格镜像源（2026-10 起）

| server | 端点 | SSH |
|---|---|---|
| zhang_c2 | <USER>@<ZC2_IP> | `-p <PORT> -i ~/.ssh/zhang_c2`（阿里云 frp 隧道） |
| math_zhou | <USER>@<ZHOU_IP> | `-p 22 -i ~/.ssh/math_zhou`（内网） |
| lv | <USER>@<LV_IP> | `-p 22 -i ~/.ssh/lv`（南开 VPN 内网） |

lv 只在 VPN 可达（lv_zheda 走阿里云 frp 隧道，内网网段不可直达）。

## 尾斜杠语义（详见 rsync-file-sync skill，此处只列结论）

- push 源 `${SKILLS_DIR}/`（带斜杠）→ 内容直入远端 skills/
- pull 源 `${remote%/}/`（先剥再补）→ 无斜杠的分支不会嵌套出 skills/skills

## --delete 审计记录（2026-10-26，lv 首跑前）

干跑结果：305 条删除，`grep -c 'rsync:'` == 0（清单完整可信）。分类结论——**零唯一副本**：

- 291 条 `.archive/`：旧扁平布局归档（`<name>-<timestamp>`），本地已重构进分类目录；7 个"archive 里找不到"的基础名（audiocraft、yuanbao、petdex、polymarket 等）逐一验证在本地**活跃 skill 目录**中存在 → 移动/重构类
- 9 条 `.curator_backups/<旧时间戳>/`：过期 curator 快照 → 垃圾类
- 5 条散件（codebase-inspection、computer-use、ngs-data-download 等）：本地已移入 software-development/ 等分类目录；`recover-sample-provenance.md` 在 git 历史（commit a225312）→ 移动类

math_zhou 干跑 0 删除（两端已一致）。zhang_c2 当日隧道端口 refused，连通性未验证。

## 敏感信息纪律（2026-10-26 全库脱敏后）

skills 仓库推送 GitHub（ShiganLuo/skill），所有文档已脱敏并重写历史：

- **占位符约定**：服务器 IP → `<ALIYUN_IP>`/`<ZC2_IP>`/`<LV_IP>`/`<ZHOU_IP>`，用户名（luosg/zhousha）→ `<USER>`，SSH 端口（20225/20226/20221）→ `<PORT>`，MySQL 密码 → `<MYSQL_PASSWORD>`。真实值只存本机 rsync.sh（gitignored）和 memory
- **.gitignore 已排除**：curator 运行时状态（.curator_ledger.jsonl 曾含 5 万+ 用户名路径）、.usage、.hub、各类密钥文件模式（*.pem/id_rsa/credentials/.env）
- **新增 skill 时的自查**：写完 grep 一遍真实 IP/用户名/密码模式再提交；发现泄漏走 git filter-repo --replace-text 重写历史 + force push（本仓库 2026-10-26 已做过一轮，方法见 git-history-rewriting skill）

## 坑

- **skills/ 目录含 `.git`、`.archive`、`.curator_ledger.jsonl`（约 1MB）**：全量随同步走。若不想同步归档/备份，加 `--exclude='.archive/'` 等（exclude 默认即保护目标端独有文件，无需额外 protect）
- **脚本自同步悖论（已解决，2026-10-26）**：rsync.sh 在被同步目录内，pull zhang_c2（其默认方向）会用远端旧脚本覆盖本地脚本。解法：push/pull 都加了 `--exclude=rsync.sh`，脚本自身不参与同步（exclude 同时受 --delete 保护，远端脚本不会被删）。合成样例实测：远端旧脚本既不被覆盖也不被删，其余文件正常镜像。**代价：脚本不再自动分发**，改脚本后需 scp 手动分发到各机：
  ```bash
  scp -P <PORT> -i ~/.ssh/zhang_c2 ~/.hermes/skills/rsync.sh <USER>@<ZC2_IP>:~/.hermes/skills/
  scp -i ~/.ssh/math_zhou ~/.hermes/skills/rsync.sh <USER>@<ZHOU_IP>:~/.hermes/skills/
  scp -i ~/.ssh/lv ~/.hermes/skills/rsync.sh <USER>@<LV_IP>:~/.hermes/skills/
  ```
- **首次对某机带 --delete 真跑前**：按 `rsync-file-sync` skill 的删除审计流程（dry run → deleting 行按一级目录分组归类 → 唯一副本停下问用户 → 真跑前单独要确认）
- 远端 skills 是 Hermes 活跃目录：push 会即时改变对端可用 skill 集，别把半成品 push 上去

## 验证清单

1. `bash -n` 语法检查
2. 未知 server/direction 打印用法且不触发 rsync（exit 1）
3. 干跑 `rsync -avzPn --delete ...` 审计删除清单后才真跑
4. 干跑失败（如端口 refused）= 连通性未验证，如实告知，不得声称同步完成
