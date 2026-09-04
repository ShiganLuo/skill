# WebSocket Customer Service — Lessons Learned

## Critical Bug: Reconnect Death Spiral

**Problem**: `scheduleReconnect(true)` with `delay=0` created infinite tight loop:
`onclose → reconnect(delay=0) → fail → onclose → reconnect(delay=0) → ...`

This froze the entire browser page, not just the chat widget. The `reconnectDelay` variable never increased when `immediate=true`, so exponential backoff was completely bypassed.

**Fix**: Remove the `immediate` parameter entirely. Always use backoff starting at 500ms:

```typescript
let reconnectDelay = 500
let reconnectCount = 0
const MAX_RECONNECT = 10

ws.onclose = (e) => {
  wsConnected.value = false
  ws = null
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
  if (e.code !== 1000) scheduleReconnect()  // NO immediate parameter
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (reconnectCount >= MAX_RECONNECT) {
    console.warn('[WS] Max reconnect attempts reached')
    return
  }
  reconnectCount++
  reconnectTimer = setTimeout(() => {
    connectWebSocket()
    reconnectDelay = Math.min(reconnectDelay * 2, 10000)
  }, reconnectDelay)
}

ws.onopen = () => {
  wsConnected.value = true
  reconnectDelay = 500   // reset on success
  reconnectCount = 0     // reset counter
}
```

**Alternative (simpler)**: Remove auto-reconnect entirely. Show "连接已断开" + "重新连接" button. User clicks to reconnect. This eliminates all possibility of death spirals and is more honest about connection state.

## Critical Bug: Token Storage Key Mismatch

**Problem**: Admin FeedbackView read token from `localStorage.getItem('bio_user')` (front app format), but admin app stores token as `localStorage.getItem('access_token')`. Token was always empty → WebSocket never connected → "无法重新连接".

**Root cause**: The two Vue3 apps have different localStorage conventions:
- `bioplatform-admin`: `access_token` (direct key)
- `bioplatform-front`: `bio_user` (pinia-plugin-persistedstate format: `{ token, userInfo }`)

**Fix**: Each app's WebSocket code must read token from ITS OWN storage key:
```typescript
// Admin FeedbackView:
const token = localStorage.getItem('access_token') || ''

// Front FeedbackChat:
const stored = localStorage.getItem('bio_user')
let token = ''
try { token = JSON.parse(stored || '{}').token || '' } catch {}
```

## Heartbeat Keepalive

WebSocket connections are silently dropped by proxies/NATs after 30-60s idle. Send ping every 25s:

```typescript
ws.onopen = () => {
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  heartbeatTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
  }, 25000)
}
```

Backend must respond to ping:
```java
if ("ping".equals(type)) {
    session.sendMessage(new TextMessage("{\"type\":\"pong\"}"));
    return;
}
```

## Map.of() Null Safety

`Map.of()` throws NPE on null values. Use `HashMap` for WebSocket message construction:
```java
Map<String, Object> msgData = new HashMap<>();
msgData.put("createdAt", msg.getCreatedAt() != null ? msg.getCreatedAt().toString() : "");
```

Also guard Integer comparisons: `if (fbSession.getStatus() != null && fbSession.getStatus() == 0)`

## handleTextMessage Needs try-catch

If JSON parsing fails, Spring closes the WebSocket connection. Always wrap:
```java
protected void handleTextMessage(WebSocketSession session, TextMessage message) {
    try {
        // ... parse and process
    } catch (Exception e) {
        log.error("处理WebSocket消息异常: {}", e.getMessage(), e);
        // Connection stays open — don't rethrow
    }
}
```

## handleKeydown Type Signature

Element Plus `el-input` `@keydown` passes `Event | KeyboardEvent`, not just `KeyboardEvent`:
```typescript
function handleKeydown(e: Event | KeyboardEvent) {
  const ke = e as KeyboardEvent
  if (ke.key === 'Enter' && !ke.shiftKey) { ke.preventDefault(); sendMessage() }
}
```

## Vite WebSocket Proxy

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': { target: 'http://localhost:8080', changeOrigin: true },
    '/ws':  { target: 'ws://localhost:8080', ws: true, changeOrigin: true },
  }
}
```

## DDL Must Be Executed Against Running DB

Adding CREATE TABLE to `bioplatform.sql` only affects fresh `docker-compose up`. For running Docker MySQL:
```bash
docker exec -i bioplatform-mysql mysql -uroot -pPASSWORD dbname < /tmp/init.sql
```

## defineExpose Must Call Init Logic

When a parent calls `ref.openChat()` via `defineExpose`, the exposed function must NOT just set visibility. It must also initialize WebSocket and load history. Otherwise the chat opens but can't send messages.

```typescript
// WRONG — window opens but WS never connects
defineExpose({ openChat: () => { chatVisible.value = true } })

// CORRECT — also initialize connection
function openChat() {
  chatVisible.value = true
  unreadCount.value = 0
  nextTick(() => { ensureConnected() })
}
defineExpose({ openChat })
```

## sendMessage Must Not Silently Return

When `ws.readyState !== WebSocket.OPEN`, returning silently gives zero feedback. The user types a message, clicks send, nothing happens, no error shown.

```typescript
function sendMessage() {
  const content = inputText.value.trim()
  if (!content) return
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    connectWebSocket()  // attempt reconnect
    return              // message stays in input
  }
  // ... send
}
```

## StorageStrategy for Multi-Server Architecture

When the platform has internal compute servers (no public internet), files can't live on the public gateway. Use a strategy interface:

```java
public interface StorageStrategy {
    String getType();
    String store(MultipartFile file, Long projectId, String fileName);
    Path resolve(String storagePath);
    void delete(String storagePath);
}
```

Two implementations with `@ConditionalOnProperty`:
- `SharedStorageStrategy` — NFS mount, direct file I/O
- `WorkerStorageStrategy` — routes to Worker via HTTP, path format `{workerId}:{remotePath}`

Config: `bioplatform.storage.type=shared` or `worker`.

Workers expose `/worker/storage/upload|download|delete|exists` endpoints. Files transferred as Base64 JSON payloads.

Using a `connecting` ref to disable BOTH textarea AND send button breaks UX. WebSocket connection is async — `connecting` is set false at end of `initChat()`, but `ws.readyState` is still CONNECTING. User can type but clicking send silently does nothing.

Track `wsConnected` separately (set in `ws.onopen`/`ws.onclose`). Never disable the textarea. Show connection status indicator instead.
