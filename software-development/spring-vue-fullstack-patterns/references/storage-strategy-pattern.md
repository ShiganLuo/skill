# Storage Strategy Pattern for Distributed Deployments

## Pattern

When deploying across multiple servers (e.g., public gateway + internal compute nodes), abstract file storage behind a strategy interface so the same code works with shared NFS or distributed Worker storage.

## Interface

```java
public interface StorageStrategy {
    String getType();
    String store(MultipartFile file, Long projectId, String fileName);
    String storeBytes(byte[] data, Long projectId, String fileName);
    Path resolve(String storagePath);
    void delete(String storagePath);
    boolean exists(String storagePath);
    long size(String storagePath);
}
```

## Implementations

### SharedStorageStrategy (NFS)
- All servers mount the same NFS/NAS directory
- Storage path: `{projectId}/{uuid_filename}` (relative to mount point)
- `resolve()` returns local path directly
- Config: `bioplatform.storage.type=shared`, `bioplatform.storage.shared-path=/data/shared/bioplatform`

### WorkerStorageStrategy (Distributed)
- Files stored on internal Worker servers
- Storage path: `{workerId}:{projectId}/{filename}` (worker ID prefix)
- `resolve()` downloads to temp file via HTTP
- Requires `WorkerClient` for HTTP communication with Workers
- Config: `bioplatform.storage.type=worker`

## Selection

Use `@ConditionalOnProperty` on each implementation class:

```java
@Component
@ConditionalOnProperty(name = "bioplatform.storage.type", havingValue = "shared", matchIfMissing = true)
public class SharedStorageStrategy implements StorageStrategy { ... }

@Component
@ConditionalOnProperty(name = "bioplatform.storage.type", havingValue = "worker")
public class WorkerStorageStrategy implements StorageStrategy { ... }
```

**Import path**: `org.springframework.boot.autoconfigure.condition.ConditionalOnProperty` (NOT `org.springframework.context.annotation`).

## Integration

Inject `StorageStrategy` into `DataFileServiceImpl` — all file operations go through the strategy. No changes needed to controllers or API layer.

## Pitfalls

- `matchIfMissing = true` on the default (shared) implementation ensures backward compatibility
- WorkerStorageStrategy needs fallback when Worker is unreachable
- Always run `ALTER TABLE` when adding new columns to the running database — updating the SQL file alone does NOT apply to existing DBs
