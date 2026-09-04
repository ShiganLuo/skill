# AI Agent Tool Integration Pitfalls

## Critical: Verify the Actual Call Path

When adding AI Agent tool-calling capability to a Spring Boot + Vue3 project, the **most common failure** is building the tool system but never wiring it into the actual request path.

### The Bug Pattern

1. Build `AgentOrchestrator` with tool calling loop
2. Build `QAAgent` / `PipelineAgent` etc. with `getTools()` and tool execution
3. Register tools in `AgentToolExecutor` via `@Component`
4. **BUT**: the frontend's SSE streaming endpoint calls a *different* service class that directly calls the LLM with a hardcoded system prompt and NO tools
5. Result: tools are registered, agents are ready, but **nothing ever uses them**

### How to Detect

Check the actual controller → service call chain:

```
Frontend POST /chat/stream
  → AdminAgentController.chatStream() / FrontAgentController.chatStream()
    → AgentServiceImpl.streamChat()
      → streamLlmApi()  ← THIS is the actual LLM call, NOT the orchestrator!
```

If `streamLlmApi()` builds the request body manually (hardcoded system prompt, no tools), the entire agent system is bypassed.

### The Fix

Modify the service layer that actually handles the request to:
1. Inject `LLMClient` and `AgentToolExecutor`
2. Use `llmClient.chatWithTools(messages, systemPrompt, tools)` instead of raw HTTP
3. Implement tool calling loop (max 5 rounds) before streaming the final response
4. Stream the final text to SSE after tool calls complete

```java
// In the service that handles the actual request
private String processWithTools(List<AgentMessage> history, SseEmitter emitter) {
    List<ChatMessage> messages = convertToChatMessages(history);
    String systemPrompt = "...with tool usage instructions...";
    List<ToolDefinition> tools = toolExecutor.getAllToolDefinitions();
    
    // Tool calling loop (synchronous)
    LLMResponse response = llmClient.chatWithTools(messages, systemPrompt, tools);
    int rounds = 0;
    while (response.hasToolCalls() && rounds < 5) {
        rounds++;
        // CRITICAL: include tool_calls in assistant message (see pitfall below)
        List<ChatMessage.ToolCallReference> refs = response.getToolCalls().stream()
                .map(tc -> new ChatMessage.ToolCallReference(tc.id(), tc.name(), tc.arguments()))
                .toList();
        messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));
        for (ToolCall tc : response.getToolCalls()) {
            String result = toolExecutor.executeTool(tc.name(), parseArgs(tc.arguments()));
            messages.add(ChatMessage.tool(tc.id(), result));
        }
        response = llmClient.chatWithTools(messages, systemPrompt, tools);
    }
    
    // Stream final text to SSE
    String finalText = response.getContent();
    for (int i = 0; i < finalText.length(); i += 20) {
        emitter.send(SseEmitter.event().data("{\"delta\":\"" + escapeJson(chunk) + "\"}"));
    }
    return finalText;
}
```

### UX Trade-off

Tool calling is synchronous (blocks while executing tools), then the final response streams. User sees a delay while tools execute, then the response appears. This is acceptable — trying to stream tool calls in real-time via SSE is significantly more complex.

## Missing Import = Runtime Error (Not Compile Error)

When code runs inside a `new Thread()` or lambda, missing imports cause **runtime** `Error` (not compile-time). `mvn compile` passes, but the app crashes at runtime:

```
Exception in thread "sse-stream-5" java.lang.Error: Unresolved compilation problem:
    Map cannot be resolved to a type
```

**Rule**: After adding new code that uses `Map`, `List`, etc. inside a lambda/thread, verify all imports are present. `mvn compile` is NOT sufficient — check the imports manually.

## System Prompt Must Mention Tools

Even with tools passed in the API request, the LLM won't use them unless the system prompt tells it to. Add explicit instructions:

```
你拥有服务器 shell 执行能力（shell_execute 工具），可以查询数据库、查看文件系统。
当用户询问平台数据相关问题时，必须先调用工具获取真实数据再回答，不要凭空猜测。
```

## CRITICAL: Assistant Message Must Include tool_calls

When adding an assistant message (that contains tool calls) to the LLM context, you MUST include the `tool_calls` array. The OpenAI-compatible API requires the full tool_calls structure so the LLM knows what it previously called when it receives the tool results.

**Bug**: `messages.add(new ChatMessage("assistant", response.getContent(), null))` — this drops tool_calls, so the second LLM call sees tool results with no context → silent failure or empty response.

**Fix**: Use `ChatMessage.assistantWithToolCalls(content, refs)` and ensure `LLMClient.buildRequestBody()` serializes the tool_calls array in assistant messages:

```java
// ChatMessage record needs a toolCalls field
public record ChatMessage(String role, String content, String toolCallId, 
                          List<ToolCallReference> toolCalls) {
    public record ToolCallReference(String id, String name, String arguments) {}
    
    public static ChatMessage assistantWithToolCalls(String content, List<ToolCallReference> toolCalls) {
        return new ChatMessage("assistant", content, null, toolCalls);
    }
}

// In LLMClient.buildRequestBody(), serialize tool_calls for assistant messages:
if (msg.toolCalls() != null && !msg.toolCalls().isEmpty()) {
    ArrayNode tcArray = msgNode.putArray("tool_calls");
    for (ChatMessage.ToolCallReference tc : msg.toolCalls()) {
        ObjectNode tcNode = tcArray.addObject();
        tcNode.put("id", tc.id());
        tcNode.put("type", "function");
        ObjectNode fnNode = tcNode.putObject("function");
        fnNode.put("name", tc.name());
        fnNode.put("arguments", tc.arguments());
    }
}
```

**Symptom**: Agent calls 2 tools, then goes silent — no final response. The second LLM call fails because the context is malformed (tool results without preceding tool_calls).

## nginx Proxy Reload After Container Recreation

When a Docker container is recreated (`docker-compose up -d`), nginx-proxy may fail to resolve the new container hostname:

```
host not found in upstream "bioplatform-backend"
```

Fix: `docker exec nginx-proxy nginx -s reload`

This is because nginx caches DNS resolution. Container recreation changes the IP.

## chroot /host: Executing Host Commands from Docker Container

When the backend runs in Docker but needs to execute shell commands on the host (access host tools like samtools, mysql client, or host filesystem):

1. Mount host root: `volumes: - /:/host:ro` in docker-compose
2. Execute via chroot: `chroot /host bash -c "command"`
3. Detect container mode: `new File("/host").isDirectory()`

```java
// ShellExecuteTool pattern
boolean inContainer = new File("/host").isDirectory();
String[] prefix = inContainer ? new String[]{"chroot", "/host", "bash", "-c"} 
                               : new String[]{"bash", "-c"};
ProcessBuilder pb = new ProcessBuilder(prefix[0], prefix[1], prefix[2], prefix[3], command);
```

**Pitfall**: chroot only changes filesystem root, NOT the process namespace. `hostname` still returns the container ID. But `df -h /`, `which bash`, file access all work on the host's filesystem.

**Do NOT install tools in the container** (apt-get mysql-client, samtools, etc.) — the data and tools are on the host, not in the container. User correction: "你加这个干嘛,数据又不在后端那个容器里面,你需要调用真正的系统工具"

## Encrypted Config Values in Database

Sensitive config (API keys) stored with `ENC:` prefix are AES-GCM encrypted. Reading directly from DB returns ciphertext:

```java
// WRONG — sends encrypted ciphertext as API key
String apiKey = systemConfigMapper.selectByKey("llm_api_key").getConfigValue();

// CORRECT — decrypt first
String apiKey = AesEncryptUtil.decrypt(systemConfigMapper.selectByKey("llm_api_key").getConfigValue());
```

**Rule**: `LLMClient.loadConfig()` must decrypt API keys. `SystemService.getConfigValue()` already decrypts internally, but direct mapper calls do not.

## docker restart vs docker-compose up -d

`docker restart bioplatform-backend` restarts the SAME container with the SAME image. It does NOT pick up a new image from `docker load`.

To deploy a new image: `docker-compose -f docker-compose-remote.yml up -d backend` (recreates the container with the latest image).

Workflow: `mvn package` → `docker build` → `docker save | ssh load` → `docker-compose up -d` (NOT `docker restart`)

## SSE Streaming with Tool Call Progress

**Problem**: Tool calling loop is synchronous — user sees blank screen for 30+ seconds. User feedback: "你不扯淡吗，服务这样,客户能满意.想想好的解决方案,能否做到hermes那样的体验感"

**Solution**: Stream every step to frontend via SSE as it happens.

### SSE Event Protocol

```
{"status": "正在分析问题..."}                              — thinking indicator
{"tool_call": {"name": "shell_execute", "arguments": {...}}} — tool about to execute
{"tool_result": {"name": "shell_execute", "output": "..."}}  — tool finished (truncated to 500 chars)
{"status": "正在根据工具结果生成回答..."}                       — between rounds
{"delta": "text chunk"}                                      — final response streaming
{"done": true, "conversationId": N}                          — completion
```

### Backend: processWithTools with real-time SSE

```java
private String processWithTools(String modelName, List<AgentMessage> history,
                                 SseEmitter emitter) throws Exception {
    List<ChatMessage> messages = convertToChatMessages(history);
    String systemPrompt = "...with tool usage instructions...";
    List<ToolDefinition> tools = toolExecutor.getAllToolDefinitions();

    sendSse(emitter, "status", "正在分析问题...");

    LLMResponse response = llmClient.chatWithTools(messages, systemPrompt, tools);
    int rounds = 0;
    while (response.hasToolCalls() && rounds < 3) {  // limit to 3 rounds for speed
        rounds++;
        // MUST include tool_calls in assistant message for LLM API consistency
        List<ChatMessage.ToolCallReference> refs = response.getToolCalls().stream()
                .map(tc -> new ChatMessage.ToolCallReference(tc.id(), tc.name(), tc.arguments()))
                .toList();
        messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));

        for (ToolCall tc : response.getToolCalls()) {
            // Push tool call event
            sendSse(emitter, "tool_call",
                "{\"name\":\"" + escapeJson(tc.name()) + "\",\"arguments\":" + tc.arguments() + "}");

            // Execute tool
            String result = toolExecutor.executeTool(tc.name(), parseArgs(tc.arguments()));

            // Push tool result (truncated for SSE, full for LLM context)
            String preview = result.length() > 500 ? result.substring(0, 500) + "..." : result;
            sendSse(emitter, "tool_result",
                "{\"name\":\"" + escapeJson(tc.name()) + "\",\"output\":" + toJson(preview) + "}");

            messages.add(ChatMessage.tool(tc.id(), result));
        }

        sendSse(emitter, "status", "正在根据工具结果生成回答...");
        response = llmClient.chatWithTools(messages, systemPrompt, tools);
    }

    // Stream final text in chunks
    String finalText = response.getContent();
    for (int i = 0; i < finalText.length(); i += 20) {
        emitter.send(SseEmitter.event()
            .data("{\"delta\":\"" + escapeJson(finalText.substring(i, Math.min(i+20, finalText.length()))) + "\"}"));
    }
    return finalText;
}

private void sendSse(SseEmitter emitter, String type, String data) {
    try {
        emitter.send(SseEmitter.event().data("{\"" + type + "\":" + data + "}"));
    } catch (Exception e) { log.warn("SSE send failed: {}", e.getMessage()); }
}
```

### Frontend: agentApi.ts callbacks

```typescript
export function chatStream(data, onToken, onDone, onError,
    onToolCall?, onToolResult?, onStatus?) {
  // ... fetch + reader loop ...
  const obj = JSON.parse(jsonStr)
  if (obj.tool_call && onToolCall) onToolCall(obj.tool_call)
  if (obj.tool_result && onToolResult) onToolResult(obj.tool_result)
  if (obj.status && onStatus) onStatus(obj.status)
  if (obj.delta) onToken(obj.delta)
}
```

### Frontend: AgentView.vue tool call display

```vue
<div v-if="streamingToolCalls.length > 0" class="tool-calls-section">
  <div v-for="(tc, i) in streamingToolCalls" :key="i" class="tool-call-card">
    <div class="tool-call-header">
      <span class="tool-name">{{ tc.name }}</span>
      <span v-if="!tc.result" class="tool-status running">执行中...</span>
      <span v-else class="tool-status done">✓ 完成</span>
    </div>
    <div class="tool-call-args"><code>{{ JSON.stringify(tc.arguments) }}</code></div>
    <div v-if="tc.result" class="tool-call-result"><pre>{{ tc.result }}</pre></div>
  </div>
</div>
<div v-if="streamingStatus && !streamingContent" class="status-hint">
  <span class="typing-dot"></span> {{ streamingStatus }}
</div>
```

### Key Rules

- **Limit to 3 rounds** (not 5) — fewer rounds = faster response
- **Truncate tool results to 500 chars** in SSE events (full result stays in messages for LLM)
- **Send status events** between tool rounds so user sees progress
- **Use sendSse() helper** that catches IOException (broken pipe from client disconnect)
- **Reset streaming state on error**: `streamingToolCalls.value = []`, `streamingStatus.value = ''`
