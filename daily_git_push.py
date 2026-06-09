#!/usr/bin/env python3
"""git add + commit + push，失败时记录详细日志。

用法:
  python daily_git_push.py              # 立即推送
  python daily_git_push.py -m "fix: xxx"  # 自定义 commit message
"""

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
COMMIT_MSG_PREFIX = "auto"                       # commit message 前缀
LOG_FILE = Path("daily_push.log")                # 日志文件路径（仓库目录下）
# ──────────────────────────────────────────────────────

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
    """执行 git 命令并返回结果。"""
    cmd = ["git"] + list(args)
    log.debug("exec: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def git_push(msg: str | None = None) -> bool:
    """执行 git add -A / commit / push，返回是否成功。

    Args:
        msg: 自定义 commit message，为 None 时使用默认前缀 + 时间戳。
    """
    # 1. git add -A
    r = run_git("add", "-A")
    if r.returncode != 0:
        log.error("git add 失败:\n%s", r.stderr.strip())
        return False

    # 2. 检查是否有变更需要提交
    r = run_git("diff", "--cached", "--quiet")
    if r.returncode == 0:
        log.info("没有待提交的变更，跳过。")
        return True

    # 3. git commit
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = msg if msg else f"{COMMIT_MSG_PREFIX}: {ts}"
    r = run_git("commit", "-m", commit_msg)
    if r.returncode != 0:
        log.error("git commit 失败:\n%s", r.stderr.strip())
        return False
    log.info("commit 成功: %s", commit_msg)

    # 4. git push
    r = run_git("push")
    if r.returncode != 0:
        log.error(
            "git push 失败 (exit %d):\nstdout: %s\nstderr: %s",
            r.returncode,
            r.stdout.strip(),
            r.stderr.strip(),
        )
        return False

    log.info("push 成功 ✓")
    return True


def push_with_retry(msg: str | None = None, max_attempts: int = 3) -> bool:
    """带重试的推送。"""
    import time
    for attempt in range(1, max_attempts + 1):
        log.info("第 %d 次尝试推送...", attempt)
        if git_push(msg):
            return True
        if attempt < max_attempts:
            log.warning("推送失败，等待 %d 秒后重试...", attempt * 30)
            time.sleep(attempt * 30)
    log.error("%d 次推送均失败。", max_attempts)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="git add + commit + push")
    parser.add_argument("-m", "--message", type=str, default=None, help="自定义 commit message")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 验证是否为 git 仓库
    r = run_git("rev-parse", "--is-inside-work-tree")
    if r.returncode != 0:
        log.error("目录不是 git 仓库: %s", Path.cwd())
        sys.exit(1)

    success = push_with_retry(msg=args.message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
