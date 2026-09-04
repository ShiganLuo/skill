# LLM Agent Tool Call Loop Patterns

Patterns for building LLM-powered agents with tool calling in Spring Boot.

## OpenAI-Compatible Tool Call Message Format

When the LLM returns tool_calls, the assistant message MUST include the tool_calls array in subsequent API calls. Without it, the LLM can't understand tool results.

```java
// WRONG: loses tool_calls context
messages.add(new ChatMessage("assistant", response.getContent(), null));

// CORRECT: preserves tool_calls
List<ToolCallReference> refs = response.getToolCalls().stream()
    .map(tc -> new ToolCallReference(tc.id(), tc.name(), tc.arguments()))
    .toList();
messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));
```

The assistant message JSON must look like:
```json
{
  "role": "assistant",
  "content": "Let me query the database...",
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "database_query",
        "arguments": "{\"sql\":\"SELECT COUNT(*) FROM projects\"}"
      }
    }
  ]
}
```

Followed by tool result messages:
```json
{"role": "tool", "tool_call_id": "call_abc123", "content": "{\"row_count\":1,...}"}
```

## Tool Call Loop with Round Limits

```java
LLMResponse response = llmClient.chatWithTools(messages, systemPrompt, tools);
int toolRounds = 0;
while (response.hasToolCalls() && toolRounds < 5) {
    toolRounds++;
    // Add assistant message WITH tool_calls
    messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), toolCallRefs));
    // Execute each tool, add results
    for (ToolCall tc : response.getToolCalls()) {
        String result = toolExecutor.executeTool(tc.name(), args);
        messages.add(ChatMessage.tool(tc.id(), result));
    }
    // Next LLM call
    response = llmClient.chatWithTools(messages, systemPrompt, tools);
}

// FALLBACK: if rounds exhausted and still has tool_calls
if (response.hasToolCalls()) {
    messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), lastRefs));
    response = llmClient.chatWithTools(messages, systemPrompt, null); // no tools
}
```

Without the fallback, the LLM returns empty content → "抱歉，我无法处理您的请求".

## Dedicated Database Query Tool

When the host/container doesn't have `mysql` client, create a Java JDBC-based tool instead of relying on shell_execute:

```java
@Component
public class DatabaseQueryTool implements Tool {
    private final DataSource dataSource;

    public String execute(Map<String, String> args) {
        String sql = args.get("sql");
        // Validate: only SELECT/SHOW/DESCRIBE
        if (!sql.strip().toUpperCase().startsWith("SELECT")) {
            return toJson(-1, "只允许 SELECT 查询");
        }
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement()) {
            stmt.setMaxRows(100);
            ResultSet rs = stmt.executeQuery(sql);
            // ... format results as JSON
        }
    }
}
```

This uses the app's existing JDBC connection — zero external dependencies.

## System Prompt Should List Available Tools

The LLM needs to know what tools exist and when to use each:

```
你拥有以下工具能力：
1. database_query: 直接查询平台MySQL数据库，执行SELECT查询。
   当用户询问业务数据时优先使用此工具。
2. shell_execute: 在服务器上执行shell命令。
   适用于查看文件、运行生信工具、检查系统状态。
```

Without this, the LLM tries to use shell_execute to find mysql client (which may not exist).
