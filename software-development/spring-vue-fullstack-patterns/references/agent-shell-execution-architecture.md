# Agent Shell Execution Architecture

## Two Deployment Scenarios

1. **Cross-network**: Different LANs, servers can't reach each other. Workers connect to public server via SSH reverse tunnel. Backend forwards commands through tunnel.
2. **Shared storage (NFS)**: Same LAN, servers share data via NFS. Backend can HTTP-call Workers directly. Service can be on any LAN machine or public server.

**Key constraint**: backend service always runs in Docker container.

## Architecture: chroot /host (Primary) + Worker (Remote)

### Local execution (default — backend's own host)

```yaml
# docker-compose-remote.yml
backend:
  volumes:
    - /:/host:ro   # mount host root read-only
```

```java
// ShellExecuteTool detects container mode
boolean inContainer = new File("/host").isDirectory();
String[] prefix = inContainer ? new String[]{"chroot", "/host", "bash", "-c"}
                               : new String[]{"bash", "-c"};
```

This gives access to host's filesystem, tools (samtools, mysql CLI), and data.

### Remote execution (Worker nodes for NFS/compute)

When `worker_id` is specified, route through Worker:

```
Agent → ShellExecuteTool → HTTP POST → Worker /worker/shell/execute → bash -c on host
```

Worker runs on host machine (not in Docker), has access to real tools and data.

## Pitfalls

1. **NEVER install tools in the backend container** — mysql-client, samtools, etc. belong on the host. User correction: "你加这个干嘛,数据又不在后端那个容器里面,你需要调用真正的系统工具"

2. **NFS is shared storage, not a compute node** — multiple servers share the same data directory via NFS mount. Each server's Worker can execute commands against the shared data. User correction: "NFS是共享存储,怎么是分发节点呢"

3. **Backend host also needs execution** — don't assume only remote Workers need shell access. The server running the backend also has data and tools. Use chroot /host for local, Worker for remote.

4. **chroot only changes filesystem root, NOT process namespace** — `hostname` still returns container ID. But file access, `which`, `df` all work on host.

5. **Security: command blacklist** — block dangerous operations (rm -rf, DROP DATABASE, DELETE FROM, fork bombs, etc.). Log all executions.

6. **Two architecture modes for ShellExecuteTool**:
   - No `worker_id` → chroot /host (local host execution)
   - With `worker_id` → HTTP to Worker (remote execution)

7. **Dockerfile must NOT use non-root USER for chroot** — `chroot` requires root privileges. Remove `USER bioplatform` from Dockerfile when shell_execute uses chroot:
   ```dockerfile
   # WRONG — non-root can't chroot
   RUN groupadd -r bioplatform && useradd -r -g bioplatform bioplatform
   USER bioplatform
   
   # CORRECT — keep root for chroot capability
   # (no USER directive)
   ```

8. **docker-compose needs SYS_CHROOT capability** — even with root user, Docker drops the SYS_CHROOT capability by default:
   ```yaml
   backend:
     cap_add:
       - SYS_CHROOT
     volumes:
       - /:/host:ro
   ```

## database_query Tool: Direct JDBC for Database Access

When the host has no `mysql` client and no Python MySQL driver, `shell_execute` can't query the database. Add a `DatabaseQueryTool` that uses the Spring Boot app's existing JDBC connection:

```java
@Component
public class DatabaseQueryTool implements Tool {
    private final DataSource dataSource;  // auto-injected by Spring
    
    // Only allows SELECT/SHOW/DESCRIBE
    // Max 100 rows, 30s timeout
    // Blocks INSERT/UPDATE/DELETE/DROP etc.
}
```

**System prompt must mention it** — tell the LLM which tool to use for database queries:
```
1. database_query: 直接查询平台MySQL数据库，执行SELECT查询。
   当用户询问数据库相关问题时，优先使用此工具。
2. shell_execute: 在服务器上执行shell命令。
```

**User feedback**: "宿主机工具不能解决问题吗" — the user questioned why a new Java tool was needed instead of host tools. The answer: host has no mysql client, container mounts are read-only so can't install packages. database_query uses the app's existing JDBC connection — zero external dependencies.
