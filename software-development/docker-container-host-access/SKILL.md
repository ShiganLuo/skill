---
name: docker-container-host-access
description: "Use when containers need host filesystem or tool access."
---

# Docker Container Host Access (chroot /host)

Pattern for executing host machine commands from within Docker containers without installing tools in the container image.

## The Problem

Containerized backend (Spring Boot, Node.js, etc.) needs to:
- Access host files (`/data/...`, `/home/...`)
- Run host-installed tools (samtools, mysql client, etc.)
- Execute arbitrary shell commands on the host

## Wrong Approaches

1. **Install tools in container** — bloats image, version drift, maintenance burden
2. **Pure Worker forwarding** — requires separate process on host, adds complexity
3. **Mount specific directories** — fragile, must enumerate every path

## Correct: chroot /host

```yaml
# docker-compose
services:
  backend:
    volumes:
      - /:/host:ro    # host root → /host (read-only)
```

```java
// Detect container mode
private final boolean inContainer = new File("/host").isDirectory();

// Execute command
String[] cmd = inContainer
    ? new String[]{"chroot", "/host", "bash", "-c", command}
    : new String[]{"bash", "-c", command};

ProcessBuilder pb = new ProcessBuilder(cmd);
pb.redirectErrorStream(true);
```

### Workdir handling

chroot changes root, so workdir is relative to /host:

```java
if (inContainer && workdir != null && !workdir.isBlank()) {
    command = "cd " + workdir + " && " + command;
}
```

## Security

### Command blacklist (block destructive ops)

```java
private static final List<Pattern> BLOCKED = List.of(
    Pattern.compile("\\brm\\s+(-[a-zA-Z]*\\s+)*-?rf\\b"),
    Pattern.compile("\\bmkfs\\b"),
    Pattern.compile("\\bdd\\s+if="),
    Pattern.compile("\\bshutdown\\b"),
    Pattern.compile("\\breboot\\b"),
    Pattern.compile("\\bDROP\\s+(DATABASE|TABLE)\\b", CASE_INSENSITIVE),
    Pattern.compile("\\bDELETE\\s+FROM\\b", CASE_INSENSITIVE),
    Pattern.compile("\\bTRUNCATE\\b", CASE_INSENSITIVE),
    Pattern.compile("\\bcurl\\b.*\\|\\s*bash"),
    Pattern.compile("\\bwget\\b.*\\|\\s*bash")
);
```

### Other measures

- `/:/host:ro` — read-only mount
- Output truncation (10KB) — prevent context overflow
- Timeout (default 30s, max 300s) — prevent hanging

## Multi-Node: Local + Remote Worker

For distributed deployments, support both local (chroot) and remote (Worker HTTP) execution:

```java
// Default: local host via chroot
if (workerId == null) {
    return executeLocal(command, timeout, workdir);
}
// Remote: forward to Worker via HTTP
else {
    WorkerInfo worker = workerRegistry.getById(workerId);
    return workerClient.executeShell(worker.getUrl(), command, timeout, workdir);
}
```

Worker endpoint: `POST /worker/shell/execute`

## Pitfalls

- **Container must run as root** for `chroot` — Dockerfile (no USER directive) works by default
- **`SYS_CHROOT` capability required** — Docker's default capabilities do NOT include `SYS_CHROOT` in all environments. Add explicitly:
  ```yaml
  # docker-compose.yml
  services:
    backend:
      cap_add:
        - SYS_CHROOT
  ```
  Without it: `chroot: cannot chroot to '/host': Operation not permitted (os error 1)`. The capability is needed even when running as root in some Docker versions / container runtimes.
- **Read-only mount** means Agent can't write host files — use named volumes for writable paths
- **chroot ≠ namespace isolation** — `hostname` still returns container hostname (expected)
- **Host must have bash** — standard Linux hosts always do; Alpine hosts may not
- **NFS mounts visible** — if host mounts NFS at `/data`, chroot sees it at `/data` (this is the desired behavior)
- **nginx-proxy needs reload after container recreation** — `docker exec nginx-proxy nginx -s reload`, because nginx caches DNS resolution and the container IP changes on recreate
- **Missing Java imports cause runtime Error, not compile Error** — code in `new Thread()` or lambdas compiles fine with missing `import java.util.Map`, but crashes at runtime with `Unresolved compilation problem`. Always verify imports manually after adding new code in async blocks
