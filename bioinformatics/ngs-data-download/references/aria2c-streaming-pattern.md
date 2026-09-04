# aria2c Streaming Download Pattern (Python)

Copy-paste pattern for downloading with aria2c while logging dynamic speed/progress.

## Key Design Decisions

1. Use `subprocess.Popen` (not `subprocess.run`) to stream stdout line-by-line
2. `--summary-interval=5` tells aria2c to emit progress summaries every 5 seconds
3. `--console-log-level=warn` suppresses aria2c's default per-event progress noise
4. Application-side throttle with `time.time()` delta ensures exactly 1 log line per 5s
5. On "Download Results", output the final progress line only if >= 2s since last log (avoids duplicate)

## aria2c Progress Line Format

```
[#a350dc 464KiB/72MiB(0%) CN:8 DL:385KiB ETA:3m12s]
```

- `#a350dc`: aria2c GID (hex)
- `464KiB/72MiB(0%)`: downloaded / total (percentage)
- `CN:8`: active connections
- `DL:385KiB`: current download speed
- `ETA:3m12s`: estimated time remaining (omitted near completion)

## Implementation (Python)

```python
import subprocess
import time
import logging
from typing import Optional
from pathlib import Path

def aria2c_download_single(
    url: str,
    dest_dir: Path,
    logger: Optional[logging.Logger] = None,
    connections: int = 8,
    split: int = 8,
    min_split_size: str = "1M",
    timeout: int = 600,
) -> bool:
    filename = url.rsplit("/", 1)[-1]
    cmd = [
        "aria2c",
        "-x", str(connections),
        "-s", str(split),
        "-k", min_split_size,
        "--timeout", str(timeout),
        "--retry-wait", "5",
        "--max-tries", "5",
        "--continue=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--summary-interval=5",
        "--console-log-level=warn",
        "-d", str(dest_dir),
        url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    last_log_time = 0.0
    last_progress = ""
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        if line.startswith("[#") and "DL:" in line:
            last_progress = line
            now = time.time()
            if now - last_log_time >= 5.0:
                if logger:
                    logger.info(f"[aria2c] {filename}  {line}")
                last_log_time = now
        elif "Download Results" in line or "Status Legend" in line:
            if last_progress and logger and time.time() - last_log_time >= 2.0:
                logger.info(f"[aria2c] {filename}  {last_progress}")
            break
    proc.wait()
    rc = proc.returncode
    if rc != 0:
        if logger:
            logger.warning(f"[aria2c] {filename} exit code {rc}")
        return False
    return True
```

## Critical Pitfalls

1. **Boolean flags need `=` syntax**: `--continue=true` NOT `--continue true`. aria2c treats bare `true` as a URI and fails with "Unrecognized URI or unsupported protocol".
2. **`proc.stdout` can be None**: Pyright/type-checker requires `assert proc.stdout is not None` before iteration.
3. **Final progress dedup**: Without the `>= 2.0` guard on the final line, you get a duplicate when the last 5s-window line was emitted moments before completion.
4. **`--summary-interval=0` disables all progress**: Use `=5` for 5-second intervals. Setting to `0` means no summary output at all.
5. **Non-TTY output batching**: When stdout is a pipe (not a TTY), aria2c may batch multiple progress lines in a single write. The line-by-line iteration handles this correctly.
