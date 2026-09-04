# OpenAI Tool Calls Message Format in Multi-Round Loops

## The Bug: Missing tool_calls in Assistant Messages (CRITICAL)

When building a multi-round tool calling loop with OpenAI-compatible APIs, the message history sent to the LLM MUST follow this exact sequence:

```
[user message]
[assistant message WITH tool_calls array]    ← MUST include tool_calls
[tool result message 1]
[tool result message 2]
[assistant message WITH tool_calls array]    ← if another round
[tool result message 3]
...
[final assistant text response]
```

**The assistant message before tool results MUST contain the `tool_calls` array.** Without it, the LLM API returns an error or empty response because it cannot correlate the tool results to the original calls.

## Wrong Pattern (causes LLM failure)

```java
// ❌ WRONG: only saves content, loses tool_calls
messages.add(new ChatMessage("assistant", response.getContent(), null));
for (ToolCall tc : response.getToolCalls()) {
    String result = executeTool(tc);
    messages.add(ChatMessage.tool(tc.id(), result));
}
response = llmClient.chatWithTools(messages, systemPrompt, tools);
// ↑ FAILS: LLM sees tool results but no tool_calls → context mismatch
```

## Correct Pattern

```java
// ✅ CORRECT: assistant message includes tool_calls
List<ToolCallReference> refs = response.getToolCalls().stream()
    .map(tc -> new ToolCallReference(tc.id(), tc.name(), tc.arguments()))
    .toList();
messages.add(ChatMessage.assistantWithToolCalls(response.getContent(), refs));

for (ToolCall tc : response.getToolCalls()) {
    String result = executeTool(tc);
    messages.add(ChatMessage.tool(tc.id(), result));
}
response = llmClient.chatWithTools(messages, systemPrompt, tools);
```

## Required JSON Format

The assistant message in the API request must look like:
```json
{
  "role": "assistant",
  "content": "Let me check that for you.",
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "shell_execute",
        "arguments": "{\"command\":\"mysql -e 'SELECT COUNT(*) FROM project'\"}"
      }
    }
  ]
}
```

Followed by:
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "COUNT(*)\n5"
}
```

## Java Implementation

```java
// ChatMessage record needs a toolCalls field
public record ChatMessage(
    String role,
    String content,
    String toolCallId,
    List<ToolCallReference> toolCalls
) {
    public record ToolCallReference(String id, String name, String arguments) {}

    public static ChatMessage assistantWithToolCalls(String content, List<ToolCallReference> toolCalls) {
        return new ChatMessage("assistant", content, null, toolCalls);
    }
}
```

In the request builder:
```java
if (msg.toolCalls() != null && !msg.toolCalls().isEmpty()) {
    ArrayNode tcArray = msgNode.putArray("tool_calls");
    for (ToolCallReference tc : msg.toolCalls()) {
        ObjectNode tcNode = tcArray.addObject();
        tcNode.put("id", tc.id());
        tcNode.put("type", "function");
        ObjectNode fnNode = tcNode.putObject("function");
        fnNode.put("name", tc.name());
        fnNode.put("arguments", tc.arguments());
    }
}
```

## Pitfall: All Agent Classes Need the Same Fix

If you have multiple agent classes (QAAgent, DataAnalysisAgent, PipelineAgent) with tool call loops, ALL of them must be updated. Search for `new ChatMessage("assistant"` to find all affected locations.
