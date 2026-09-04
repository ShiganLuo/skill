# Vite Watch Configuration & inotify

## Problem

Vite dev server uses Linux `inotify` to watch files for HMR (hot module replacement). Linux has THREE independent inotify limits:

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `max_user_watches` | Total watches (files/dirs) per user | 65536 |
| `max_user_instances` | Total inotify instances per user | 128 |
| `max_queued_events` | Events waiting in queue | 16384 |

### Watch vs Instance

- **Instance**: one monitoring context, typically one per process (or per module within a process). Like "opening a control room."
- **Watch**: one file/directory monitored under an instance. Like "a camera in the control room."

```
instance (process A)
  ├── watch: src/
  ├── watch: public/
  └── watch: vite.config.ts
instance (process B)
  ├── watch: .git/
  └── watch: node_modules/
```

One instance can hold thousands of watches, but instance count has its own limit.

**Key insight**: VSCode with many extensions easily exhausts `max_user_instances` (each extension = 1-2 instances) even when total watch count is low. This was the actual cause in a session where watch count was ~100 but instances hit 109/128.

## Consumers

**Instance consumers:**
- VSCode: each window + each extension creates independent instances
- Vite/webpack: 1 instance per dev server
- Obsidian: 1 instance per vault
- File sync tools (Syncthing, Nutstore, etc.)

**Watch consumers:**
- Vite/webpack dev server: watches entire `src/` tree (2000-5000 watches per project)
- VSCode file explorer: each open directory tree registers watches
- node_modules: thousands of small files, pointless to watch

## Fix: Exclude node_modules and .git

In BOTH `vite.config.ts` files (front and back), add under `server:`:

```ts
server: {
  // ... existing config ...
  watch: {
    ignored: ['**/node_modules/**', '**/.git/**']
  }
}
```

This prevents Vite from registering inotify watches on `node_modules` (thousands of files) and `.git` (large internal tree).

## Fix: Increase system limits

```bash
# Runtime (immediate)
sudo sysctl fs.inotify.max_user_watches=524288
sudo sysctl fs.inotify.max_user_instances=512

# Persist across reboots
cat >> /etc/sysctl.conf << 'EOF'
fs.inotify.max_user_watches=524288
fs.inotify.max_user_instances=512
EOF
sudo sysctl -p
```

## Diagnostics

```bash
# All three limits
echo "max_user_watches: $(cat /proc/sys/fs/inotify/max_user_watches)"
echo "max_user_instances: $(cat /proc/sys/fs/inotify/max_user_instances)"
echo "max_queued_events: $(cat /proc/sys/fs/inotify/max_queued_events)"

# Current instance count
find /proc/*/fdinfo -type f -exec grep -l inotify {} \; 2>/dev/null | wc -l

# Per-process watch usage (top consumers)
find /proc/*/fdinfo -type f -exec grep -l inotify {} \; 2>/dev/null | \
  cut -d/ -f3 | sort | uniq -c | sort -rn | head -15 | \
  while read count pid; do
    name=$(cat /proc/$pid/comm 2>/dev/null || echo "unknown")
    echo "  $count watches  PID=$pid  ($name)"
  done
```

### Which limit is exhausted?

- Watch count is high → `max_user_watches` exhausted
- Instance count close to limit → `max_user_instances` exhausted
- Both low but still error → check `ulimit -n` (file descriptor limit)

## Pitfalls

- `watch.ignored` uses glob patterns, not regex. `**/node_modules/**` matches any `node_modules` at any depth.
- The `watch` option is only for the dev server (`vite dev`), not for `vite build`.
- If VSCode alone is consuming too many instances, the Vite config fix won't help — increase `max_user_instances` sysctl limit.
- The error message `EMFILE: too many open files` is the same for both limits — you must check both to diagnose correctly.
