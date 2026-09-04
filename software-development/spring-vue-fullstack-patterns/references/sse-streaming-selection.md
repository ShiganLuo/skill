# SSE vs WebSocket Selection

## 为什么 LLM 对话用 SSE

LLM 对话的通信模式是：用户发一条消息，服务端持续推送 token。这是典型的"请求-流式响应"，单向推送，不需要双向通信。

SSE 相比其他方案的优势：
- 协议简单，基于普通 HTTP，不需要协议升级
- 认证统一，复用 HTTP Authorization header
- 浏览器原生支持 EventSource API（虽然本项目用 fetch ReadableStream）
- 服务端实现简单（Spring 的 SseEmitter）
- 负载均衡器天然支持

## 为什么不用 WebSocket

WebSocket 是双向通信协议，适合聊天室、在线客服等需要双向实时通信的场景。LLM 对话只需要服务端→客户端的单向推送，WebSocket 的双向能力是多余的。

## 项目中的选择

- AI 对话/Agent 流式输出 → SSE（SseEmitter + OkHttp 流式读取 + fetch ReadableStream）
- 在线客服 WebSocket 浮动对话框 → WebSocket（需要双向实时通信）

## 为什么不用 Axios

Axios 底层用 XMLHttpRequest，不支持浏览器端流式读取响应体。必须等响应完全返回才能拿到数据。

fetch 原生支持 `response.body.getReader()` 返回 ReadableStream，可以逐块读取 SSE 数据流。

## SSE fetch Token 读取陷阱

`chatStream` 用原生 `fetch` 发请求，不经过 Axios 拦截器，必须自己读 token 并加 Authorization header。

**Bug**: 直接从 `localStorage.getItem('bio_user')` 读 token — Pinia plugin persist 写入 localStorage 有微小延迟，登录后首次发消息可能读到空 token。

**Fix**: 优先从 Pinia store 读（实时值），fallback 到 localStorage：

```typescript
import { useUserStore } from '@/stores/user'

function getAccessToken(): string {
  try {
    const store = useUserStore()
    if (store.token) return store.token
  } catch { /* store 未初始化时 fallback */ }
  try {
    const stored = localStorage.getItem('bio_user')
    if (stored) return JSON.parse(stored).token || ''
  } catch {}
  return ''
}
```

**Axios 拦截器也是从 localStorage 读的（`getStoredToken()`），但它每次请求都读，而 SSE fetch 只在发起时读一次。如果 token 被 Axios 的 401 刷新机制更新了，SSE 请求用的还是旧 token。加一个 401 retry 机制：收到 HTTP 401/403 时用最新 token 重试一次。**
