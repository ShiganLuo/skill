# Agent Tool Calling Pitfalls from Bioplatform

## tool_calls Lost in Context

**Problem**: LLM returned empty content after 3 rounds of tool calls.
**Root cause**: Assistant message added to context WITHOUT tool_calls info:
```java
// WRONG
messages.add(new ChatMessage("assistant", response.getContent(), null));
// RIGHT
messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), toolCallRefs));
```
OpenAI API requires tool_calls array in assistant messages before tool results.

## Tool Rounds Exhausted

**Problem**: LLM used 5 rounds exploring database (SHOW TABLES → DESCRIBE → SELECT × 3).
**Fix**: Inject database schema into system prompt via `getSystemPromptFragment()`.
Query `information_schema.COLUMNS` at tool initialization, format as `table(col type, ...)`.

## LLM Returns Null Content

**Problem**: After tool call loop, `response.getContent()` was null → fallback error message.
**Root cause**: Loop exited because rounds exhausted, but last response still had tool_calls.
**Fix**: After loop, if `response.hasToolCalls()`, do one more LLM call WITHOUT tools:
```java
if (response.hasToolCalls()) {
    messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), toolCallRefs));
    response = llmClient.chatWithTools(messages, systemPrompt, null); // no tools = must return text
}
```

## DatabaseQueryTool vs shell_execute

shell_execute runs in container or via chroot to host. Neither has mysql client or Python mysql driver.
**Solution**: DatabaseQueryTool uses Spring's DataSource (JDBC) directly. Zero external dependencies.

## ChatMessage Record Extension

Adding `toolCalls` field to ChatMessage record required:
1. New `ToolCallReference` inner record
2. New `assistantWithToolCalls()` factory method
3. Update ALL callers (AgentServiceImpl + 3 Agent classes) — search `new ChatMessage(`

## SSE Broken Pipe Flooding Logs

**Problem**: After SSE stream completes, heartbeat thread still tries to send → Broken pipe → ERROR logs.
**Root cause**: heartbeat lambda references `heartbeatTask` before assignment (won't compile), and heartbeat doesn't self-cancel on emitter close.
**Fix**:
1. Use array wrapper: `ScheduledFuture<?>[] holder = new ScheduledFuture<?>[1]`
2. In heartbeat catch block: `holder[0].cancel(false); heartbeat.shutdown();`
3. Add IOException handler to GlobalExceptionHandler at DEBUG level

## SSE Connection Drops During Long Tool Calls

**Problem**: Client disconnects during 30+ second LLM processing, backend keeps executing tools.
**Fix**: Register emitter callbacks + AtomicBoolean disconnected flag, check before each tool call:
```java
emitter.onCompletion(() -> disconnected.set(true));
// In tool loop:
if (disconnected.get()) return null;
```

## nginx Proxy Blocking SSE

**Symptom**: SSE events delayed or connection drops after ~60s.
**Fix**: BOTH inner and outer nginx need:
```nginx
proxy_buffering off;        # SSE must not buffer
proxy_read_timeout 300s;    # tool calls can take >60s
```

## Docker chroot Permission Denied

**Symptom**: `chroot: cannot chroot to '/host': Operation not permitted`
**Fix**: docker-compose needs `cap_add: SYS_CHROOT` AND Dockerfile must NOT have `USER` directive (chroot needs root).
