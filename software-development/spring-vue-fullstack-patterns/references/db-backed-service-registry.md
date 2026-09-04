# DB-Backed Service Registry Pattern

When managing distributed compute nodes (Workers), persist node config in DB instead of YAML config files. This enables runtime CRUD via admin UI without restarts.

## Schema

```sql
CREATE TABLE compute_nodes (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    node_id     VARCHAR(64) NOT NULL,   -- UUID-based unique ID
    hostname    VARCHAR(128),
    url         VARCHAR(256) NOT NULL,  -- Worker address (e.g. http://localhost:18081)
    cpu_cores   INT DEFAULT 0,
    memory_mb   BIGINT DEFAULT 0,
    status      TINYINT DEFAULT 1,      -- 0=disabled 1=enabled
    healthy     TINYINT DEFAULT 0,      -- 0=offline 1=online
    last_heartbeat DATETIME(6),
    created_at  DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_node_id (node_id)
);
```

## Registry Component

```java
@Component
public class WorkerRegistry {
    private final Map<String, WorkerInfo> workers = new ConcurrentHashMap<>();
    private final ComputeNodeMapper nodeMapper;

    // Load from DB on startup
    @EventListener(ApplicationReadyEvent.class)
    public void init() {
        List<ComputeNode> nodes = nodeMapper.selectEnabled();
        for (ComputeNode node : nodes) {
            workers.put(node.getNodeId(), fromEntity(node));
        }
        checkAllHealth();
    }

    // Periodic health check — updates both memory cache and DB
    @Scheduled(fixedDelay = 30000, initialDelay = 10000)
    public void checkAllHealth() {
        for (WorkerInfo info : workers.values()) {
            try {
                // HTTP GET /worker/health
                boolean healthy = checkHealth(info.getUrl());
                info.setHealthy(healthy);
                nodeMapper.updateHealth(info.getId(), healthy ? 1 : 0, cpuCores, memoryMB);
            } catch (Exception e) {
                info.setHealthy(false);
                nodeMapper.updateHealth(info.getId(), 0, 0, 0L);
            }
        }
    }

    // CRUD operations
    public WorkerInfo addNode(String url, String hostname) { ... }
    public void removeNode(String nodeId) { ... }
    public void setNodeEnabled(String nodeId, boolean enabled) { ... }
}
```

## Admin Controller

```java
@RestController
@RequestMapping("/api/admin/workers")
public class AdminWorkerController {
    @GetMapping                    // list all
    @PostMapping                   // add node
    @DeleteMapping("/{nodeId}")    // remove node
    @PutMapping("/{nodeId}/status") // enable/disable
    @PostMapping("/test")          // test connection
}
```

## Pitfalls

- Memory cache (`ConcurrentHashMap`) and DB must stay in sync — always update both
- Health check updates DB directly via `updateHealth` mapper method, not through full entity update
- `nodeId` is UUID-based (not auto-increment) so Workers can self-register with consistent IDs
- Disabled nodes (`status=0`) are excluded from health checks and task scheduling
