---
name: llm-chat-integration
description: "Vue3 LLM chat: SSE streaming and error handling patterns."
version: "1.0"
author: "curator"
tags: [vue3, element-plus, llm, chat, sse, streaming]
metadata:
  hermes:
    tags: [frontend, chat, ai, streaming]
    related_skills: [spring-vue-fullstack-patterns, vue3-element-plus-integration]
---

# LLM Chat Integration Patterns

Reusable patterns for integrating LLM chat (SSE streaming) into Vue3 + Element Plus web applications.

## When to Use

- Building AI assistant chat interfaces with SSE streaming
- Handling errors in LLM-powered chat components
- Integrating tool call displays in chat UIs
- Ensuring front/admin consistency in chat error handling

## Error Handling — THE RULE

**Never expose raw backend errors to users.** LLM calls fail for many reasons (API key, rate limit, model timeout, provider outage). The user sees NONE of that.

### What to do

1. In `agentApi.ts` (the SSE fetch wrapper), all `onError()` calls pass a **generic message**:
   ```ts
   // ❌ WRONG — exposes backend internals
   if (obj.error) { onError(obj.error); return }
   onError(`HTTP ${response.status}`)
   onError(e.message || '流式读取异常')

   // ✅ CORRECT — generic message
   if (obj.error) { onError('服务不可用'); return }
   onError('服务不可用')
   onError('服务不可用')
   ```

2. In the chat view component (e.g. `AgentView.vue`), display the error as an **assistant message bubble**, NOT as a popup:
   ```ts
   // ❌ WRONG — popup dialog
   ElMessageBox.alert('当前服务不可用', '提示', { type: 'warning' })
   ElMessage.error('AI 请求失败: ' + errMsg)

   // ✅ CORRECT — assistant message bubble in chat area
   messages.value.push({
     role: 'assistant',
     content: '服务不可用',
     timestamp: Date.now(),
   })
   ```

3. **Auth errors (401/403)** are the exception — show a specific "请先登录" message as an assistant bubble, still not a popup.

### Why bubbles, not popups?

- Popups (ElMessageBox/ElMessage) **interrupt** the chat flow
- A message bubble **stays in context** — the user can see what they asked and that it failed
- Chat UI convention: errors are part of the conversation, not system alerts

## Front + Admin Consistency

Both the public frontend and admin panel have AI assistants. **Error handling must be identical** in both:
- Same generic message ("服务不可用")
- Same display method (assistant bubble)
- Same auth error handling (401/403 → "请先登录")

When changing error handling, **always update both** `bioplatform-front` and `bioplatform-admin`.

## SSE Streaming Architecture

```
agentApi.ts (chatStream)
  ├── fetch() → response.body.getReader()
  ├── SSE parsing: lines starting with "data:"
  ├── JSON events: { delta, done, error, tool_call, tool_result, status }
  └── Callbacks: onToken, onDone, onError, onToolCall, onToolResult, onStatus

AgentView.vue
  ├── streamingContent ref → real-time rendering
  ├── streamingToolCalls ref → tool call display
  ├── onDone → push to messages array, clear streaming refs
  └── onError → push generic assistant message, clear streaming refs
```

## Tool Call Display

Tool calls stream in via `tool_call` and `tool_result` SSE events. Display pattern:
- Show tool name + "执行中..." while running
- Show tool name + "✓ 完成" + result preview when done
- Tool calls are part of the assistant's response, not separate UI elements

## Chat Bubble CSS Sizing

See `references/chat-bubble-css.md` for the full pattern. Key rule:

```css
.message-bubble {
  width: fit-content;
  max-width: 100%;
}
.message-bubble.user {
  margin-left: auto;
}
```

Without `fit-content`, bubbles stretch to parent width — short messages get oversized bubbles.

## Pitfalls

1. **Don't push error into streaming content** — if streaming was in progress, save whatever content was received as a separate assistant message, then push the error message
2. **Clear all streaming refs on error** — `streamingContent`, `streamingStatus`, `streamingToolCalls` must all be reset
3. **Set loading=false on error** — otherwise the input stays disabled
4. **scrollToBottom after error** — the new message needs to be visible
5. **"对话框" means chat area bubble** — when the user says "以对话框的形式" or "AI助手的对话框", they mean the chat area message bubble, NOT a popup dialog (ElMessageBox). Don't misinterpret "对话框" as "弹窗".