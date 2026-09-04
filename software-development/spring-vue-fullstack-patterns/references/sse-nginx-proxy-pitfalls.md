# SSE Through Nginx Proxy Pitfalls

SSE (Server-Sent Events) requires special nginx configuration. Without it, connections drop silently.

## proxy_buffering Must Be Off

nginx buffers upstream responses by default. SSE events get queued in the buffer and never reach the client in real-time.

```nginx
location /api/ {
    proxy_pass http://backend:8080;
    proxy_buffering off;           # CRITICAL for SSE
    proxy_read_timeout 300s;       # LLM/tool calls can take minutes
    proxy_send_timeout 300s;
}
```

## Multi-Layer Proxy Timeout Chain

When nginx-proxy → inner-nginx → backend, EACH layer must have sufficient timeout:

```
Client → nginx-proxy (300s) → bioplatform-front nginx (300s) → backend:8080
```

If ANY layer has a short timeout (e.g., 60s), the connection breaks at that layer.

## HTTP/2 Idle Timeout

`http2 on` in nginx adds HTTP/2 framing. HTTP/2 has stream-level idle timeouts that can close SSE connections even when proxy_read_timeout is long.

**Fix**: SSE heartbeat comments keep the connection active:

```java
// Backend: send SSE comment every 15s
ScheduledExecutorService heartbeat = Executors.newSingleThreadScheduledExecutor();
ScheduledFuture<?> task = heartbeat.scheduleAtFixedRate(() -> {
    try {
        emitter.send(SseEmitter.event().comment("keepalive"));
    } catch (Exception e) {
        heartbeat.shutdown();
    }
}, 15, 15, TimeUnit.SECONDS);

// Stop on connection close
emitter.onCompletion(() -> { task.cancel(false); heartbeat.shutdown(); });
emitter.onTimeout(() -> { task.cancel(false); heartbeat.shutdown(); });
emitter.onError(e -> { task.cancel(false); heartbeat.shutdown(); });
```

Frontend ignores `:` comment lines automatically (standard SSE behavior).

## Broken Pipe on Request Thread

When SSE runs in a Spring async thread (`new Thread()`), the original HTTP request thread returns to the pool. If the client disconnects, writes from the async thread get `Broken pipe`. The GlobalExceptionHandler may also try to write an error response to the already-closed connection, causing `HttpMessageNotWritableException: No converter for [class ApiResponse] with preset Content-Type 'text/event-stream'`.

**Fix**: Register emitter callbacks to detect disconnection early:

```java
AtomicBoolean disconnected = new AtomicBoolean(false);
emitter.onCompletion(() -> disconnected.set(true));
emitter.onTimeout(() -> disconnected.set(true));
emitter.onError(e -> disconnected.set(true));

// Check before each SSE send in the processing loop
while (hasMoreWork && !disconnected.get()) {
    // ... do work ...
    sendSse(emitter, "data", payload);
}
```

## sendSse Must Swallow Exceptions

```java
private void sendSse(SseEmitter emitter, String eventType, String data) {
    try {
        emitter.send(SseEmitter.event()
                .data("{\""+ eventType + "\":" + data + "}"));
    } catch (Exception e) {
        log.warn("SSE 发送失败: {}", e.getMessage());
        // Don't rethrow — the disconnected flag will stop the loop
    }
}
```

## Frontend fetch + SSE Parsing

```typescript
// SSE comments (lines starting with :) are automatically skipped
for (const line of lines) {
    if (!line.startsWith('data:')) continue  // skips comments, empty lines
    const jsonStr = line.slice(5).trim()     // "data:" is 5 chars, no space
    // ... parse JSON
}
```

Note: `data:` has NO space after the colon in the backend's `SseEmitter.event().data(...)`. Use `slice(5)` not `slice(6)`.
