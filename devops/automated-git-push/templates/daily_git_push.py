#!/usr/bin/env python3
"""Automated git add + commit + push with retry and logging.

Usage:
  python daily_git_push.py              # scheduled mode (requires cron)
  python daily_git_push.py --push-now   # immediate push once
  python daily_git_push.py --push-now -m "fix: xxx"  # custom commit message
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────
COMMIT_MSG_PREFIX = "auto"                       # commit message prefix
LOG_FILE = Path("daily_push.log")                # log file in repo dir
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
    """Run a git command. Uses cwd, NOT git -C (old git compat)."""
    cmd = ["git"] + list(args)
    log.debug("exec: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def git_push(msg: str | None = None) -> bool:
    """Execute git add -A / commit / push. Returns success status."""
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
    log.info("commit succeeded: %s", commit_msg)

    r = run_git("push")
    if r.returncode != 0:
        log.error(
            "git push failed (exit %d):\nstdout: %s\nstderr: %s",
            r.returncode, r.stdout.strip(), r.stderr.strip(),
        )
        return False

    log.info("push succeeded ✓")
    return True


def push_with_retry(msg: str | None = None, max_attempts: int = 3) -> bool:
    """Push with retry and exponential backoff."""
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if run_git("rev-parse", "--is-inside-work-tree").returncode != 0:
        log.error("Not a git repo: %s", Path.cwd())
        sys.exit(1)

    if args.push_now:
        log.info("Manual push mode")
        success = push_with_retry(msg=args.message)
        sys.exit(0 if success else 1)

    # Dead code path — cron handles scheduling, this is just a fallback warning
    log.warning("Running without --push-now. Use cron for scheduling. Exiting.")
    sys.exit(0)


if __name__ == "__main__":
    main()
