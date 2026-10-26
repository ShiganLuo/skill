---
name: cronjob-troubleshooting
description: "Use when a Hermes cron job doesn't fire or delivers nothing."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, cron, scheduler, debugging]
---

# Cron 任务排障

## When to Use

- 用户问"为什么还没触发/没收到推送/定时任务是不是挂了"
- 需要确认某次 cron 运行的成败、错误原文或产物去向

按三层定位，**每层都有独立证据，别混为一谈**：

## 1. 调度层：到底触发没有

`cronjob(action='list')` 看三个字段：

- `last_run_at`：今天/预期时间有没有跑过 → 有 = 调度正常，问题在执行或投递
- `last_status`: `ok` / `error`
- `next_run_at`：下次时间（正常就说明调度器健康）
- 返回里的 `gateway_running: false` 警告：若 `last_run_at` 是新的，说明 ticker 在跑，**别拿这个当根因**

## 2. 执行层：跑成了还是报错

每次运行（无论成败）都会落盘：

```
~/.hermes/cron/output/<job_id>/YYYY-MM-DD_HH-MM-SS.md
```

- 文件模板：成功 = `## Response`；失败 = 标题带 **(FAILED)** + `## Error` 代码块
- 末尾 `grep -c` 各失败类型可判断是偶发还是连续故障
- 常见错误：`RuntimeError: Connection error.` = **LLM 后端连接失败**（瞬时/代理问题，非任务本身）；`loop_web_search_cap` = agent 陷入重复搜索被护栏打断（提示词问题，需改策略）
- `sqlite3` CLI 可能未安装（exit 127）——直接读 output 文件即可，不必查 `executions.db`
- 成功与否的最终判据：任务目标产物是否生成（如约定保存的报告目录里有没有当日文件），而不是 output 文件存在

## 3. 投递层：成功了为什么没收到

- `deliver: "local"` = **只存档、不发消息**——任务成功也不会推到聊天窗口，这是设计不是故障
- 要收到推送：`cronjob(action='update', job_id=..., )` 把 deliver 改为 `origin`（发起对话）或 `feishu` 等平台
- 报告类任务若目标是"每天收到"，创建时就要选对 deliver，别等用户来问

## 坑

- `cronjob create` 用 `'30m'` 这类间隔写法会建成 `repeat=once` 一次性任务；循环任务**创建时直接用 cron 表达式**（如 `*/30 * * * *`）。`update` 不修正 repeat，错的只能删了重建
- "没触发"三连问的排查顺序固定：list 看 last_run_at → 读 output 错误段 → 查 deliver，三层各给一条证据再下结论（用户偏好：证据够就停）
