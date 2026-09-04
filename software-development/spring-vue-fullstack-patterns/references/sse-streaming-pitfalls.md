# SSE Streaming Pitfalls

## nginx proxy_buffering Kills SSE (CRITICAL)

When SSE responses pass through nginx, `proxy_buffering on` (the default) causes nginx to **buffer the entire response** before forwarding to the client. This destroys real-time streaming — events pile up in the buffer and arrive in a burst instead of incrementally.

**Symptom**: Frontend sees no SSE events for 30-60 seconds, then all events arrive at once. Or the connection appears to "hang" and eventually times out.

**Fix**: For any nginx location that proxies SSE endpoints:
```nginx
location /api/ {
    proxy_pass http://backend:8080;
    proxy_buffering off;          # CRITICAL for SSE
    proxy_read_timeout 300s;      # Tool calls + LLM can take >60s
    proxy_send_timeout 300s;
}
```

**Multi-layer proxy pitfall**: When requests pass through multiple nginx instances (e.g., an outer `nginx-proxy` + an inner container nginx), EACH layer needs `proxy_buffering off`. One buffered layer blocks the entire chain.

The bioplatform project has this exact setup:
- Outer: `nginx-proxy` container (handles TLS termination, routes to `bioplatform-front:80`)
- Inner: `bioplatform-front` container's nginx (proxies `/api/` to `backend:8080`)

Both must have `proxy_buffering off` for the `/api/` location.

## Spring SseEmitter Connection Lifecycle (CRITICAL)

When running long async operations (tool call loops, LLM chains) in a background thread with SseEmitter, the client can disconnect at any time. Without detection, the backend thread keeps running — executing tools, making LLM calls — all wasted.

**Fix**: Register emitter callbacks and check a flag:
```java
private String processWithTools(String modelName, List<AgentMessage> history,
                                 SseEmitter emitter) throws Exception {
    AtomicBoolean disconnected = new AtomicBoolean(false);
    emitter.onCompletion(() -> disconnected.set(true));
    emitter.onTimeout(() -> disconnected.set(true));
    emitter.onError(e -> disconnected.set(true));

    // Tool call loop
    while (response.hasToolCalls() && toolRounds < 3) {
        if (disconnected.get()) {
            log.info("SSE连接已断开，停止工具调用循环");
            return null;
        }
        for (ToolCall tc : response.getToolCalls()) {
            if (disconnected.get()) return null;  // Check before EACH tool
            // ... execute tool, send SSE events ...
        }
        response = llmClient.chatWithTools(messages, systemPrompt, tools);
    }
    return finalContent;
}
```

**Also wrap the done event** — the emitter may already be completed:
```java
try {
    emitter.send(SseEmitter.event().data("{\"done\":true}"));
    emitter.complete();
} catch (Exception ex) {
    try { emitter.complete(); } catch (Exception ignored) {}
}
```

## Token Sync Between Pinia Store and Raw fetch (CRITICAL)

When using raw `fetch` for SSE (not Axios), the token must be read correctly. `pinia-plugin-persistedstate` writes to localStorage asynchronously — reading localStorage immediately after login may return empty.

**Fix**: Read from Pinia store first (always in sync), fallback to localStorage:
```typescript
function getAccessToken(): string {
  try {
    const store = useUserStore()
    if (store.token) return store.token
  } catch { /* store not initialized */ }
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).token || ''
  } catch {}
  return ''
}
```

**Also add 401 retry** — Axios interceptor handles token refresh automatically, but raw fetch does not:
```typescript
function doFetch(retryOn401 = true) {
  const token = getAccessToken()
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(async (response) => {
      if (!response.ok && (response.status === 401 || response.status === 403) && retryOn401) {
        doFetch(false)  // Retry once with fresh token
        return
      }
      // ... handle response
    })
}
```

## SseEmitter Timeout Configuration

Default SseEmitter timeout is 30 seconds. For LLM tool call loops (multiple LLM calls + tool execution), set at least 5 minutes:
```java
SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);
```

Match nginx timeouts to be at least as long:
```nginx
proxy_read_timeout 300s;  # 5 minutes
```

## OpenAI API tool_calls Context Requirement (CRITICAL)

**Symptom**: LLM returns tool_calls → tools execute → second LLM call fails silently, returns empty, or errors. The agent responds "抱歉，我无法处理您的请求" after tool execution.

**Root cause**: OpenAI-compatible APIs require the assistant message to carry the full `tool_calls` array when followed by tool result messages. If you only save `content` to the conversation context, the second LLM call sees tool results with no corresponding tool calls — the API rejects or returns garbage.

**Correct message sequence**:
```
1. assistant: { content: "...", tool_calls: [{id, type:"function", function:{name, arguments}}] }
2. tool:      { role: "tool", tool_call_id: "xxx", content: "result..." }
3. assistant: { content: "final answer" }
```

**Fix** — ALL agent classes must use `assistantWithToolCalls()` when adding assistant messages with tool calls:
```java
// WRONG — loses tool_calls info, second LLM call breaks
messages.add(new ChatMessage("assistant", response.getContent(), null));

// CORRECT
List<ToolCallRef> refs = response.getToolCalls().stream()
    .map(tc -> new ToolCallRef(tc.id(), tc.name(), tc.arguments()))
    .toList();
messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));
```

In `buildRequestBody`, serialize tool_calls for assistant messages:
```java
if (msg.toolCalls() != null && !msg.toolCalls().isEmpty()) {
    ArrayNode tcArray = msgNode.putArray("tool_calls");
    for (var tc : msg.toolCalls()) {
        ObjectNode tcNode = tcArray.addObject();
        tcNode.put("id", tc.id());
        tcNode.put("type", "function");
        ObjectNode fn = tcNode.putObject("function");
        fn.put("name", tc.name());
        fn.put("arguments", tc.arguments());
    }
}
```

**Pitfall**: When multiple Agent classes share this pattern (QAAgent, DataAnalysisAgent, PipelineAgent), ALL of them must be updated — not just the main service. Missing one causes the same bug in that agent's code path.
