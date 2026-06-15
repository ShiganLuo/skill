---
name: automated-git-push
description: Python script + user-level cron for daily automated git pushes with failure logging and retry.
triggers:
  - user wants scheduled/automatic git push
  - daily commit and push to git repo
  - cron job for git operations
---

# Automated Git Push

Set up a Python script that performs `git add -A / commit / push`, scheduled via user-level cron.

## Pitfalls

1. **Old git versions** — some systems (e.g., CentOS 7 with git 1.8) do NOT support `git -C <dir>`. Use `cwd=` parameter in `subprocess.run()` instead of passing `-C` to git.
2. **No root needed** — user-level `crontab -e` works without sudo. Always check `which crontab` and `crontab -l` first.
3. **Don't over-engineer config** — if the script runs inside the repo, there's no need for a `GIT_REPO_DIR` variable. Use `cwd` directly. Users will call this out as unnecessary.
4. **Sleep loops are fragile** — a `while True` + `time.sleep()` approach dies on process exit or system restart. Prefer cron for scheduling; the script should run once and exit.
5. **Manual + scheduled coexistence** — use `--push-now` flag for manual runs. Cron uses the same flag. The scheduled loop code path becomes dead code once cron is set up — clean it up or leave it but don't mix concerns.
6. **Repository directory** — use `--repo-dir` to specify a different repository directory. Default is current directory (`.`).

## Script Pattern

```python
#!/usr/bin/env python3
"""Automated git add + commit + push with retry and logging."""

import argparse, logging, subprocess, sys, time
from datetime import datetime
from pathlib import Path

COMMIT_MSG_PREFIX = "auto"
LOG_FILE = Path("daily_push.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("daily_git_push")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["git"] + list(args)  # NO git -C (old git compat)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def git_push(msg: str | None = None) -> bool:
    r = run_git("add", "-A")
    if r.returncode != 0:
        log.error("git add failed:\n%s", r.stderr.strip())
        return False

    r = run_git("diff", "--cached", "--quiet")
    if r.returncode == 0:
        log.info("No changes to commit, skipping.")
        return True

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = msg if msg else f"{COMMIT_MSG_PREFIX}: {ts}"
    r = run_git("commit", "-m", commit_msg)
    if r.returncode != 0:
        log.error("git commit failed:\n%s", r.stderr.strip())
        return False

    r = run_git("push")
    if r.returncode != 0:
        log.error("git push failed (exit %d):\nstdout: %s\nstderr: %s",
                  r.returncode, r.stdout.strip(), r.stderr.strip())
        return False

    log.info("push succeeded ✓")
    return True


def push_with_retry(msg=None, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        log.info("Attempt %d...", attempt)
        if git_push(msg):
            return True
        if attempt < max_attempts:
            log.warning("Failed, retrying in %ds...", attempt * 30)
            time.sleep(attempt * 30)
    log.error("All %d attempts failed.", max_attempts)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated daily git push")
    parser.add_argument("--push-now", action="store_true", help="Push once and exit")
    parser.add_argument("-m", "--message", type=str, default=None, help="Custom commit message (--push-now only)")
    parser.add_argument("--repo-dir", type=str, default=".", help="Repository directory (default: current directory)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Change to specified repo directory
    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.is_dir():
        log.error("Directory does not exist: %s", repo_dir)
        sys.exit(1)
    
    import os
    os.chdir(repo_dir)
    log.info("Working directory: %s", repo_dir)

    if run_git("rev-parse", "--is-inside-work-tree").returncode != 0:
        log.error("Not a git repo: %s", repo_dir)
        sys.exit(1)

    if args.push_now:
        sys.exit(0 if push_with_retry(args.message) else 1)

    # Dead code once cron is configured — can be removed
    log.warning("No --push-now flag. Use cron for scheduling, not this loop.")


if __name__ == "__main__":
    main()
```

## Cron Setup

```bash
# Check if crontab is available (user-level, no root)
which crontab && crontab -l

# Set up daily 18:00 push
REPO_DIR="/path/to/repo"
SCRIPT="/path/to/daily_git_push.py"

cat << EOF | crontab -
# Daily git push at 18:00
0 18 * * * /usr/bin/python $SCRIPT --push-now --repo-dir $REPO_DIR >> ${SCRIPT%/*}/daily_push_cron.log 2>&1
EOF

# Verify
crontab -l
```

## Key Points

- Script lives in the repo or elsewhere — cron `cd`s into the repo dir first
- Two log files: `daily_push.log` (script's own), `daily_push_cron.log` (cron stdout/stderr)
- Manual use: `python script.py --push-now` or `python script.py --push-now -m "msg"`
- Specify repo directory: `python script.py --push-now --repo-dir /path/to/repo`
- Default repo directory: current directory (`.`)
- Retry: 3 attempts with 30s/60s/90s backoff
- No external dependencies (stdlib only)

## 中文使用说明

### 脚本位置
- 主脚本: `daily_git_push.py`（中文版，已添加所有参数）
- 模板: `devops/automated-git-push/templates/daily_git_push.py`（英文版）

### 使用方法
```bash
# 立即推送
python daily_git_push.py --push-now

# 自定义 commit message
python daily_git_push.py --push-now -m "fix: 修复xxx问题"

# 指定仓库目录
python daily_git_push.py --push-now --repo-dir /path/to/repo

# 组合使用
python daily_git_push.py --push-now -m "更新文档" --repo-dir /path/to/repo
```

### 定期执行设置
```bash
# 检查 crontab 是否可用
which crontab && crontab -l

# 设置每天 18:00 自动推送
REPO_DIR="/path/to/your/repo"
SCRIPT="/path/to/daily_git_push.py"

cat << EOF | crontab -
# 每天 18:00 自动 git push
0 18 * * * /usr/bin/python3 $SCRIPT --push-now --repo-dir $REPO_DIR >> ${SCRIPT%/*}/daily_push_cron.log 2>&1
EOF

# 验证设置
crontab -l
```

### 日志文件
- `daily_push.log`: 脚本自身的日志（在仓库目录下）
- `daily_push_cron.log`: cron 执行日志（在脚本目录下）

### 注意事项
1. 脚本会自动重试 3 次，每次间隔 30/60/90 秒
2. 如果没有变更，脚本会跳过提交
3. 使用 `--push-now` 参数才会实际执行推送
4. 不带参数运行会提示使用 cron 调度
