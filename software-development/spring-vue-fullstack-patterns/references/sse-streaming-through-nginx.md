# SSE Streaming Through Nginx Proxy

Complete guide for Spring Boot SseEmitter through nginx reverse proxy chain.

## nginx Configuration (REQUIRED for SSE)

Both outer and inner nginx must have:

```nginx
location /api/ {
    proxy_pass http://backend:8080;
    proxy_buffering off;        # SSE MUST disable buffering
    proxy_read_timeout 300s;    # Tool calls can take >60s
    proxy_send_timeout 300s;
}
```

**Check BOTH layers**: outer nginx-proxy AND inner container nginx. Missing either one causes 502 Bad Gateway or silent connection drops.

## SseEmitter Lifecycle Management

```java
SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);

// Register callbacks for cleanup
emitter.onCompletion(() -> cleanup());
emitter.onTimeout(() -> cleanup());
emitter.onError(e -> cleanup());
```

## Heartbeat Keepalive Pattern

During LLM processing (no SSE data for 10-30s), proxies may close the connection. Send periodic SSE comments:

```java
ScheduledExecutorService heartbeat = Executors.newSingleThreadScheduledExecutor(r -> {
    Thread t = new Thread(r, "sse-heartbeat-" + id);
    t.setDaemon(true);
    return t;
});

// Array wrapper avoids "variable may not be initialized" compile error
ScheduledFuture<?>[] holder = new ScheduledFuture<?>[1];
holder[0] = heartbeat.scheduleAtFixedRate(() -> {
    try {
        emitter.send(SseEmitter.event().comment("keepalive"));
    } catch (Exception e) {
        holder[0].cancel(false);
        heartbeat.shutdown();
    }
}, 15, 15, TimeUnit.SECONDS);

emitter.onCompletion(() -> { holder[0].cancel(false); heartbeat.shutdown(); });
emitter.onTimeout(() -> { holder[0].cancel(false); heartbeat.shutdown(); });
emitter.onError(e -> { holder[0].cancel(false); heartbeat.shutdown(); });
```

SSE comments (`:keepalive\n\n`) are ignored by browsers but transmitted through proxies.

## Broken Pipe Handling

Suppress in GlobalExceptionHandler:

```java
@ExceptionHandler(IOException.class)
public void handleIOException(IOException ex) {
    log.debug("SSE disconnect: {}", ex.getMessage());
}
```

## Frontend SSE Parsing

```typescript
// fetch-based SSE (NOT EventSource, which is GET-only)
const reader = response.body?.getReader()
while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    if (!line.startsWith('data:')) continue  // skip comments
}
```

## Pitfalls

- **Lambda variable capture**: `heartbeatTask` referenced before assignment → use `holder[]` array pattern
- **Heartbeat after complete()**: catch block must self-cancel, not just log
- **Both nginx layers**: outer AND inner must have `proxy_buffering off`
- **HTTP/2**: can interfere with SSE; try disabling for SSE locations if issues persist
- **Backend as non-root + chroot**: needs `cap_add: SYS_CHROOT` and no USER in Dockerfile
