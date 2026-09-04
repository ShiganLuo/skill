---
name: ai-agent-skill-architecture
description: "Use when building AI agent tools with self-describing skills"
---

# AI Agent Skill Architecture

Build extensible AI agent tool systems where tools self-describe, system prompts auto-generate, and agents can create new skills at runtime.

## Core Pattern: Tool extends Skill

```java
public interface Skill {
    String getName();
    String getDescription();
    String getTriggerDescription();      // when to use
    String getUsageHint();               // how to use
    String getSystemPromptFragment();    // dynamic context (schema, etc.)
    int getPriority();                   // ordering
}

public interface Tool extends Skill {
    Map<String, Object> getParameters();  // JSON Schema
    String execute(Map<String, String> args);
}
```

Every Tool automatically becomes a Skill.

## SkillRegistry: Auto-Generated System Prompts

```java
@Component
public class SkillRegistry {
    public SkillRegistry(List<Skill> skills, ...) {
        // Spring auto-discovers all @Component Skills
        // + loads DB-created skills (skill:* config keys)
    }

    public String buildSystemPrompt() {
        // = base prompt + each skill's trigger/hint + global rules + dynamic fragments
    }
}
```

AgentService never hardcodes system prompts. New tool = new @Component.

## Agent-Created Skills

```java
// Store as JSON in system_config with key = "skill:<name>"
// SkillRegistry loads on next conversation
```

## Dynamic Schema Injection

```java
@Override
public String getSystemPromptFragment() {
    // Query information_schema → formatted table schema
    // Eliminates SHOW TABLES + DESCRIBE exploration rounds
}
```

## LLM Tool Calling Loop

```java
while (response.hasToolCalls() && rounds < MAX_ROUNDS) {
    rounds++;
    messages.add(ChatMessage.assistantWithToolCalls(content, toolCallRefs));
    for (ToolCall tc : response.getToolCalls()) {
        messages.add(ChatMessage.tool(tc.id(), executeTool(tc)));
    }
    response = llmClient.chatWithTools(messages, systemPrompt, tools);
}
// Fallback: rounds exhausted → no-tool LLM call for text response
```

## SSE Streaming for Agent Output

Spring `SseEmitter` with heartbeat keepalive + disconnect detection:

```java
SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);

// Heartbeat: array wrapper solves Java lambda reference-before-assignment
ScheduledFuture<?>[] holder = new ScheduledFuture<?>[1];
holder[0] = heartbeat.scheduleAtFixedRate(() -> {
    try { emitter.send(SseEmitter.event().comment("keepalive")); }
    catch (Exception e) { holder[0].cancel(false); heartbeat.shutdown(); }
}, 15, 15, TimeUnit.SECONDS);

// Disconnect detection: stop tool loop when client gone
AtomicBoolean disconnected = new AtomicBoolean(false);
emitter.onCompletion(() -> { holder[0].cancel(false); disconnected.set(true); });
emitter.onTimeout(() -> { holder[0].cancel(false); disconnected.set(true); });
emitter.onError(e -> { holder[0].cancel(false); disconnected.set(true); });

// In tool loop: check disconnected before each tool call
if (disconnected.get()) { return null; }
```

**nginx SSE requirements** (both frontend and admin nginx):
```nginx
proxy_buffering off;        # MUST — buffering blocks SSE push
proxy_read_timeout 300s;    # Tool calls + LLM can take >60s
```

**Broken pipe handling**: Add IOException handler to GlobalExceptionHandler at DEBUG level:
```java
@ExceptionHandler(IOException.class)
public void handleIOException(IOException ex) {
    log.debug("SSE连接断开: {}", ex.getMessage());
}
```

## Pitfalls

- **Assistant message MUST include tool_calls array** before tool results
- **MAX_ROUNDS=5**, exhausted → fallback no-tool call
- **Inject schema into prompt**, don't let LLM explore (wastes 2-3 rounds)
- **ChatMessage record**: adding fields requires updating ALL factory methods
- **Schema format**: `table_name(col1 type, col2 type)` one per line
- **Java lambda captures**: `ScheduledFuture<?> var = executor.schedule(() -> { use(var); })` won't compile — use `ScheduledFuture<?>[] holder = new [1]` array wrapper
- **SSE heartbeat must self-cancel**: catch exception in heartbeat lambda → cancel + shutdown, otherwise logs flood with Broken pipe after emitter.complete()
- **Two-layer nginx proxy**: both inner (container) and outer (host) need `proxy_buffering off` for SSE
- **Docker chroot needs**: `cap_add: SYS_CHROOT` + run as root (not USER directive in Dockerfile)
