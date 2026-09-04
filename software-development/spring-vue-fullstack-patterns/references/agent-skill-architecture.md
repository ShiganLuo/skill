# Agent Skill Architecture Pattern

Self-describing tool system where the system prompt is auto-generated from tool metadata, not hardcoded.

## Core Principle

**Tools declare their own prompt fragments. Adding a new tool never requires editing the system prompt.**

## Interface Hierarchy

```java
// Skill: self-describing interface
public interface Skill {
    String getName();
    String getDescription();
    String getTriggerDescription();   // when to use
    String getUsageHint();            // how to use
    String getSystemPromptFragment(); // dynamic context (e.g. DB schema)
    int getPriority();                // ordering
}

// Tool extends Skill: every tool is automatically a skill
public interface Tool extends Skill {
    Map<String, Object> getParameters();  // JSON Schema
    String execute(Map<String, String> args);
    // Skill methods have defaults; tools only override what they need
}
```

## SkillRegistry

```java
@Component
public class SkillRegistry {
    // Spring auto-injects all Skill implementations
    public SkillRegistry(List<Skill> skills, SystemConfigMapper configMapper, ObjectMapper mapper) {
        // 1. Sort by priority
        // 2. Load DB skills (key prefix "skill:", created by agent)
        // 3. Build static prompt template
    }

    public String buildSystemPrompt() {
        // base prompt + all skill trigger/hint + global rules + dynamic fragments
    }
}
```

## Agent-Createable Skills

Agent uses `create_skill` tool to persist new skills to DB (`system_config` table, key `skill:*`):

```json
{
  "name": "gene_expression_query",
  "description": "Query gene expression data",
  "trigger": "When user asks about FPKM, TPM, expression levels",
  "hint": "Query data_files table filtering by organism and genome_version",
  "fragment": "Common query: SELECT * FROM data_files WHERE organism='Human'"
}
```

DB skills are loaded on next startup via `SkillRegistry.loadDbSkills()`.

## Dynamic Fragments

Some skills provide runtime-generated context (e.g. database schema):

```java
@Override
public String getSystemPromptFragment() {
    // Query information_schema, return table/column definitions
    // This avoids LLM wasting tool rounds on SHOW TABLES / DESCRIBE
    return getDatabaseSchema();
}
```

## AgentServiceImpl Integration

```java
// BEFORE (hardcoded):
String systemPrompt = "你是一个...助手。你拥有以下工具：\n1. database_query: ..."

// AFTER (skill-driven):
String systemPrompt = skillRegistry.buildSystemPrompt();
```

## SSE Streaming Pitfalls

- **Heartbeat**: `SseEmitter.event().comment("keepalive")` every 15s, self-cancel on error
- **Disconnect detection**: `emitter.onCompletion/onTimeout/onError` → AtomicBoolean flag → break tool loop
- **Tool round limit**: Max 5 rounds; if exhausted with pending tool_calls, do one more LLM call without tools
- **Broken pipe**: IOException handler in GlobalExceptionHandler at DEBUG level (not ERROR)
- **nginx**: `proxy_buffering off` + `proxy_read_timeout 300s` on ALL proxy layers

## Key Lessons

1. Don't hardcode tool descriptions in system prompts — use the Skill interface
2. Don't special-case sensitive fields (API Key) — use the same snapshot comparison as all configs
3. Database schema injection prevents LLM from wasting 2-3 tool rounds exploring tables
4. SSE heartbeat comments prevent nginx/HTTP2 from closing idle connections
5. Agent self-creation of skills allows the system to improve without code changes
