# LLM Agent Tool Calls & SSE Streaming Patterns

## LLM Tool Calls Context Management

### The Bug: Missing tool_calls in History

When building a multi-round tool-calling loop with OpenAI-compatible APIs, the assistant message that initiated tool calls MUST include the `tool_calls` array in the conversation history. Without it, the LLM cannot correlate tool results to the original calls, causing the second LLM call to fail or return empty.

### Wrong

```java
// Only saves content — LLM sees tool results with no context
messages.add(new ChatMessage("assistant", response.getContent(), null));
for (ToolCall tc : response.getToolCalls()) {
    messages.add(ChatMessage.tool(tc.id(), executeTool(tc)));
}
response = llmClient.chatWithTools(messages, systemPrompt, tools); // FAILS
```

### Correct

```java
// Save assistant message WITH tool_calls
List<ToolCallReference> refs = response.getToolCalls().stream()
    .map(tc -> new ToolCallReference(tc.id(), tc.name(), tc.arguments()))
    .toList();
messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));

for (ToolCall tc : response.getToolCalls()) {
    messages.add(ChatMessage.tool(tc.id(), executeTool(tc)));
}
response = llmClient.chatWithTools(messages, systemPrompt, tools); // OK
```

The serialized JSON must look like:
```json
{"role": "assistant", "content": "...", "tool_calls": [
  {"id": "call_123", "type": "function", "function": {"name": "shell_execute", "arguments": "{...}"}}
]}
{"role": "tool", "tool_call_id": "call_123", "content": "{...}"}
```

### All Agent classes need the same fix

When multiple agent classes (QAAgent, DataAnalysisAgent, PipelineAgent) share the same tool-calling loop pattern, ALL of them must be updated when changing the message format. One missed class = same bug in a different code path.

---

## SSE Streaming Through Nginx

### Problem

SSE (Server-Sent Events) require real-time, unbuffered data flow. Nginx default settings buffer proxy responses and have short read timeouts, breaking SSE.

### Nginx Config for SSE

```nginx
location /api/ {
    proxy_pass http://backend:8080;
    
    # CRITICAL: disable buffering for SSE
    proxy_buffering off;
    
    # Long timeout for tool execution chains (LLM + tool calls can take minutes)
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Pitfalls

- **`proxy_buffering on` (default)** — nginx holds SSE events in buffer, client sees delayed/batched delivery. With two proxy layers (outer nginx-proxy + inner container nginx), the inner buffering is the bottleneck.
- **`proxy_read_timeout 60s`** — tool execution chains (LLM call → tool execute → LLM call again) can easily exceed 60s. Set to 300s minimum.
- **Double proxy** — if request goes through `nginx-proxy` → `bioplatform-front nginx` → `backend`, BOTH nginx layers must have buffering off and sufficient timeout.
- **HTTP/2 in outer proxy** — `http2 on` in nginx-proxy can introduce frame-level idle timeouts that drop SSE connections even when `proxy_read_timeout` is long. Use SSE keepalive to counteract.

---

## SSE Keepalive Heartbeat

### Problem

Even with `proxy_buffering off` and long `proxy_read_timeout`, SSE connections can be dropped by intermediate proxies (HTTP/2 gateways, CDN, load balancers) when the connection is idle for 30-60 seconds. This happens during long LLM tool-call chains where no SSE data is sent for extended periods (e.g., waiting for LLM API response).

### Solution: Scheduled Keepalive Comments

SSE comment lines (starting with `:`) are transmitted but ignored by browsers. Send them periodically to keep the connection alive:

```java
// In streamChat(), after creating the emitter:
ScheduledExecutorService heartbeat = Executors.newSingleThreadScheduledExecutor(r -> {
    Thread t = new Thread(r, "sse-heartbeat-" + conversationId);
    t.setDaemon(true);
    return t;
});
ScheduledFuture<?> heartbeatTask = heartbeat.scheduleAtFixedRate(() -> {
    try {
        emitter.send(SseEmitter.event().comment("keepalive"));
    } catch (Exception e) {
        heartbeat.shutdown();
    }
}, 15, 15, TimeUnit.SECONDS);

// Clean up on connection end
emitter.onCompletion(() -> { heartbeatTask.cancel(false); heartbeat.shutdown(); });
emitter.onTimeout(() -> { heartbeatTask.cancel(false); heartbeat.shutdown(); });
emitter.onError(e -> { heartbeatTask.cancel(false); heartbeat.shutdown(); });
```

### Frontend Handling

The frontend's SSE parser already skips non-`data:` lines, so `:keepalive` comments are automatically ignored. No frontend changes needed.

### Key Points

- 15-second interval is safe for most proxies (idle timeout is typically 30-60s)
- Use daemon threads so they don't prevent JVM shutdown
- Always clean up heartbeat on emitter completion/timeout/error
- HTTP/2 in outer nginx-proxy (`http2 on`) can have stricter idle timeouts than HTTP/1.1

---

## SSE Connection Lifecycle (Backend)

### Problem

When SSE connection breaks (client closes tab, network drop), the backend thread continues executing tool calls, wasting resources and producing "Broken pipe" / "ResponseBodyEmitter has already completed" errors.

### Solution: Disconnected Flag

```java
private String processWithTools(List<ChatMessage> messages, SseEmitter emitter) {
    AtomicBoolean disconnected = new AtomicBoolean(false);
    emitter.onCompletion(() -> disconnected.set(true));
    emitter.onTimeout(() -> disconnected.set(true));
    emitter.onError(e -> disconnected.set(true));

    // Tool call loop
    while (response.hasToolCalls() && toolRounds < MAX_ROUNDS) {
        if (disconnected.get()) {
            log.info("SSE disconnected, stopping tool loop");
            return null;  // caller handles null gracefully
        }
        
        for (ToolCall tc : response.getToolCalls()) {
            if (disconnected.get()) return null;  // check before EACH tool
            
            // ... execute tool, send SSE events ...
        }
        
        response = llmClient.chatWithTools(messages, systemPrompt, tools);
    }
    // ...
}
```

### Caller Must Handle Null + Already-Completed Emitter

```java
// In the async thread:
try {
    String content = processWithTools(messages, emitter);
    // Save message if content != null...
    
    // Send done event (connection may be gone)
    try {
        emitter.send(SseEmitter.event().data("{\"done\":true}"));
        emitter.complete();
    } catch (Exception ex) {
        try { emitter.complete(); } catch (Exception ignored) {}
    }
} catch (Exception e) {
    try {
        emitter.send(SseEmitter.event().data("{\"error\":\"...\"}"));
        emitter.complete();
    } catch (Exception ex) {
        try { emitter.complete(); } catch (Exception ignored) {}
    }
}
```

### sendSse Helper

```java
private void sendSse(SseEmitter emitter, String eventType, String data) {
    try {
        emitter.send(SseEmitter.event()
            .data("{\""+ eventType +"\":" + data + "}"));
    } catch (Exception e) {
        log.warn("SSE send failed: {}", e.getMessage());
        // Do NOT throw — let the disconnected flag handle loop termination
    }
}
```

---

## Tool Call Loop: Exhaustion Fallback

### Problem

When the LLM uses all available tool-call rounds (e.g., 5 rounds) and the last response still contains tool_calls, the code exits the loop with `response.hasToolCalls() == true`. The `response.getContent()` is null/empty, so the user sees "抱歉，我无法处理您的请求".

### Solution: Final No-Tools LLM Call

```java
// After the tool call loop:
if (response.hasToolCalls()) {
    log.info("Tool rounds exhausted, making final no-tools LLM call");
    // Add the last assistant message with tool_calls to context
    List<ChatMessage.ToolCallReference> lastRefs = response.getToolCalls().stream()
        .map(tc -> new ChatMessage.ToolCallReference(tc.id(), tc.name(), tc.arguments()))
        .toList();
    messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), lastRefs));
    // Call LLM WITHOUT tools — forces text-only response
    response = llmClient.chatWithTools(messages, systemPrompt, null);
}
```

### System Prompt Optimization

Reduce unnecessary tool calls by instructing the LLM to be efficient:

```
重要：查询数据库时，先用一条SQL获取所需数据（如 SELECT COUNT(*) FROM projects），
不要分多步查询。尽量减少工具调用轮次，每轮只调用一次工具获取足够数据后直接回答。
```

---

## Admin Config Save: Snapshot-Based Dirty Tracking

### Problem

"Save all configs" sends every config value to backend. For sensitive fields (API keys) stored as masked values (`sk-***cdef`), the masked string gets saved as the actual value, breaking the key.

### Solution: Snapshot Comparison

```typescript
// On page load: save original snapshot
let originalSnapshot: Record<string, string> = {}

function collectSnapshot(): Record<string, string> {
  const snap: Record<string, string> = {}
  for (const [k, v] of Object.entries(config)) snap[k] = String(v)
  // Include sensitive fields too (they hold masked values)
  snap['api_key'] = apiKeyValue
  return snap
}

onMounted(async () => {
  await loadConfigs()
  originalSnapshot = collectSnapshot()
})

// On save: only send changed items
async function handleSave() {
  const current = collectSnapshot()
  const changed = []
  
  for (const [key, value] of Object.entries(current)) {
    if (originalSnapshot[key] !== value) {
      // Skip masked sensitive values (contain ***)
      if (isSensitive(key) && value.includes('***')) continue
      changed.push({ key, value })
    }
  }
  
  if (changed.length === 0) {
    ElMessage.info('没有配置被修改')
    return
  }
  
  // Encrypt sensitive fields before sending
  for (const config of changed) {
    if (isSensitive(config.key)) {
      config.value = await encrypt(config.value)
    }
    await updateConfig(config)
  }
  
  // Update snapshot after successful save
  originalSnapshot = collectSnapshot()
}
```

### Key Points

- Sensitive fields (API keys, passwords) ARE included in snapshot as their masked display value
- If masked value unchanged → not detected as dirty → not sent
- If user inputs new real value → detected as changed → encrypted then sent
- No separate `apiKeyDirty` tracking needed — unified mechanism for all config types
- After save, snapshot is refreshed so the newly saved value becomes the baseline
- API Key must NOT have special handling (no separate dirty flag) — user explicitly rejected that design

---

## Pinia Store Token Sync with Raw Fetch

### Problem

`chatStream` uses native `fetch` (not Axios) for SSE. Reading token from `localStorage.getItem('bio_user')` can miss the token if `pinia-plugin-persistedstate` hasn't flushed yet (async write).

### Solution: Read from Pinia Store First

```typescript
function getAccessToken(): string {
  try {
    const store = useUserStore()
    if (store.token) return store.token  // Real-time from Pinia
  } catch { /* store not initialized */ }
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).token || ''  // Fallback
  } catch {}
  return ''
}
```

Also add a retry on 401: if the first fetch returns 401/403, re-read the token (which may have been refreshed by another Axios request) and retry once.

---

## Docker chroot for Host Command Execution

### Problem

Agent's `shell_execute` tool uses `chroot /host` to access host filesystem. Fails with "Operation not permitted" because:
1. Container runs as non-root user (Dockerfile `USER bioplatform`)
2. Missing `SYS_CHROOT` capability

### Solution

```dockerfile
# Dockerfile: do NOT switch to non-root user
# chroot needs root privileges
ENTRYPOINT ["sh", "-c", "java ... -jar app.jar"]
```

```yaml
# docker-compose.yml
services:
  backend:
    cap_add:
      - SYS_CHROOT
    volumes:
      - /:/host:ro
```

### Key Points

- `/:/host:ro` mount is read-only, so host can't be modified
- Container runs as root but the application (Java) handles its own security
- Alternative: use dedicated tools (like `database_query`) instead of `chroot` for common operations
