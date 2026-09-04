# WebSocket Pitfalls in Spring Boot + Vue3

## Reconnection Death Spiral

**Problem**: Using `scheduleReconnect(true)` with delay=0 in `ws.onclose` creates an infinite loop when the connection keeps failing — freezes the browser.

**Root cause**: `immediate=true` sets delay=0 and doesn't increase `reconnectDelay`, so every close triggers an instant reconnect that fails again.

**Fix**: Always use backoff, add max retry count:

```javascript
let reconnectDelay = 500
let reconnectCount = 0
const MAX_RECONNECT = 10

ws.onclose = (e) => {
  wsConnected.value = false
  ws = null
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
  if (e.code !== 1000) scheduleReconnect()
}

function scheduleReconnect() {
  if (reconnectCount >= MAX_RECONNECT) return
  reconnectCount++
  setTimeout(() => {
    connectWebSocket()
    reconnectDelay = Math.min(reconnectDelay * 2, 10000)
  }, reconnectDelay)
}

ws.onopen = () => {
  reconnectDelay = 500
  reconnectCount = 0
  heartbeatTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
  }, 25000)
}
```

## Heartbeat Keep-Alive

WebSocket behind Nginx/proxies gets dropped after idle timeout (~60s). Send ping every 25s:

- Client: `ws.send('{"type":"ping"}')` every 25s
- Server: reply `{"type":"pong"}`, skip ping in message handler
- Clear heartbeat timer on close

## Manual vs Auto Reconnect

For customer service / chat widgets, prefer **manual reconnect** with a "连接已断开" + reconnect button. Auto-reconnect with backoff still risks resource exhaustion if the server is permanently down. The server should also have a max retry limit.

## Token Storage Key Mismatch

Admin and Front apps store JWT differently:

| App | Storage Key | Format |
|-----|------------|--------|
| Admin | `localStorage.access_token` | Direct string |
| Front | `localStorage.bio_user` | JSON `{ token, userInfo }` (pinia-plugin-persistedstate) |

When creating components used in both apps, always check which key the host app uses. Reading the wrong key → `null` → WebSocket/API silently fails.

```javascript
// Admin context
const token = localStorage.getItem('access_token') || ''

// Front context
const stored = localStorage.getItem('bio_user')
const token = stored ? JSON.parse(stored).token : ''
```

## Spring Bean Naming Conflicts

`@EnableScheduling` auto-registers a bean named `taskScheduler`. Creating `@Component class TaskScheduler` causes `BeanDefinitionOverrideException`. Same for `taskExecutor` with `@EnableAsync`. Use descriptive names: `PipelineTaskDispatcher`, `AsyncJobRunner`.

## SSE vs WebSocket Choice

- **SSE (Server-Sent Events)**: Single direction (server→client), HTTP-based, browser auto-reconnect, simple auth via headers. Best for: LLM streaming, notifications, progress updates.
- **WebSocket**: Bidirectional, independent protocol, manual reconnect needed, auth via URL param or handshake. Best for: chat rooms, collaborative editing, real-time gaming.

In BioPlatform: AI chat uses SSE (fetch + ReadableStream), customer service uses WebSocket (bidirectional).

## Storage Strategy Pattern (Distributed Deployment)

When deploying across isolated internal servers with no shared filesystem, use a `StorageStrategy` interface:

```java
public interface StorageStrategy {
    String store(MultipartFile file, Long projectId, String fileName);
    Path resolve(String storagePath);
    void delete(String storagePath);
}
```

Two implementations selected via `@ConditionalOnProperty(name = "bioplatform.storage.type")`:
- `SharedStorageStrategy` — NFS mount, files at `{sharedPath}/{projectId}/{uuid_filename}`, path format: `{projectId}/{filename}`
- `WorkerStorageStrategy` — files on internal Worker servers, path format: `{workerId}:{projectId}/{filename}`, uses HTTP to transfer via Worker's storage API

Gateway stores only metadata (DB records with storage path). Never store files on the Gateway itself in distributed mode.

## Nginx Proxy Config

```nginx
# WebSocket
location /ws/ {
    proxy_pass http://backend:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
}

# SSE
location /api/ {
    proxy_pass http://backend:8080;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
}
```

## User Preference: Concise Technical Docs

When writing technical documentation for this project:
- Don't over-explain obvious choices (e.g., don't write a full SSE vs WebSocket comparison when SSE is clearly the right choice — just state why briefly)
- Project is "生信云平台" (bioinformatics platform), not a blog — directory naming must reflect the project domain (use `docs/tech/` not `docs/blog/`)
- When user says "不需要" about a comparison/section, remove it entirely — don't trim, delete
- Git: use `git rm --cached` to remove files from tracking, never `git filter-branch` unless explicitly asked to rewrite history. `filter-branch` rewrites ALL commits and causes force-push requirements

## Vite Dev Server Proxy

```typescript
// vite.config.ts
server: {
  proxy: {
    '/ws': {
      target: 'ws://localhost:8080',
      ws: true,
      changeOrigin: true,
    }
  }
}
```
