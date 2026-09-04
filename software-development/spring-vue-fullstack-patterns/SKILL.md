---
name: spring-vue-fullstack-patterns
description: "Use when developing Spring Boot + Vue3 full-stack projects."
---

# Spring Boot + Vue3 Full-Stack Patterns

Reusable patterns and pitfalls for Spring Boot backend + Vue3/Element Plus frontend projects.

See `references/websocket-and-spring-boot-pitfalls.md` for WebSocket reconnect, heartbeat, bean naming conflicts, and database migration pitfalls.

See `references/storage-strategy-pattern.md` for distributed storage abstraction (NFS shared vs Worker-based) with `@ConditionalOnProperty` switching.

See `references/db-backed-service-registry.md` for managing compute nodes in DB with periodic health checks and admin CRUD.

See `references/worker-deploy-script.md` for Worker one-click deployment script (build/start/stop/restart/status).

## JWT Authentication Pitfalls

### Whitelist Over-Matching

Spring Security whitelist with wildcards like `/api/admin/**` causes ALL matching endpoints to skip JWT validation. The `SecurityContext` is empty, so any code calling `getCurrentUserId()` returns null → 401.

**Rule**: Only whitelist endpoints that genuinely don't need auth. Never use `/api/admin/**`.

### Authorization Header Format

JWT filter checks `authHeader.startsWith("Bearer ")`. Missing prefix causes "请求未携带accessToken":

```typescript
// WRONG: { Authorization: accessToken }
// CORRECT: { Authorization: `Bearer ${accessToken}` }
```

## SSE vs WebSocket Decision

| Scenario | Protocol | Why |
|----------|----------|-----|
| LLM streaming output (user sends 1 message, server pushes tokens) | SSE | Unidirectional, HTTP-based, simpler auth |
| Customer service chat (both sides send messages) | WebSocket | Bidirectional real-time |

**SSE advantages**: HTTP-native, automatic browser reconnect (EventSource), no connection state management, standard auth headers.
**WebSocket advantages**: bidirectional, lower latency, binary support.

Don't use WebSocket for unidirectional streaming — it adds unnecessary complexity (heartbeat, reconnect logic, token-in-URL auth).

## Element Plus el-upload

### before-upload Must Return false

When using `:before-upload` to manually handle upload (calling your own API), the handler MUST return `false` to prevent el-upload's default XHR behavior. Without this, el-upload sends a second request to the `:action` URL (which may be undefined → error).

```vue
<el-upload :show-file-list="false" :before-upload="handleUpload">
  <el-button>上传文件</el-button>
</el-upload>

<script setup>
const handleUpload = async (file: File) => {
  await uploadFile(file, projectId)
  ElMessage.success('上传成功')
  loadFiles()
  return false  // CRITICAL: prevent el-upload default behavior
}
</script>
```

### Authentication

`:action` mode sends requests directly, NOT through axios interceptors. Must pass `:headers` with Bearer token.

Setting `headers: { 'Content-Type': undefined }` in axios can strip the Authorization header from the interceptor.

### Bearer Prefix Pitfall

When defining the headers object for el-upload, the `Bearer` prefix is easy to miss or get wrong due to template literal syntax:

```typescript
// WRONG — missing Bearer prefix:
const headers = { Authorization: accessToken }

// WRONG — template literal display issue (cat -A shows backticks as ***):
const headers = { Authorization: `accessToken` }  // no Bearer!

// CORRECT:
const headers = { Authorization: `Bearer ${accessToken}` }
```

Check with hex dump when in doubt:
```python
python3 -c "
with open('file.vue') as f:
    lines = f.readlines()
print(repr(lines[N-1]))  # shows actual content
"
```

This pattern appears in every `el-upload` with `:action` (website info, photo, friend link pages). Grep for files with `Authorization.*accessToken` but without `Bearer` to find broken ones.

## URL Normalization Pattern

Database stores relative paths. `@MinioFile` + `MinioResponseAdvice` auto-prepends base URL on response.

**Java regex pitfall**: `\\\\d` in source = `\\d` in string = literal `\\d` in regex. Use `\\d` for digit matching.

All image URL fields must be stripped before saving: `articleCover`, `avatarUrl`, `logo`, `favicon`, `authorAvatar`, `userAvatar`, `touristAvatar`, `frontHeadBackground`, `wechatQrCode`, `alipayQrCode`, `siteLogo`.

### `@MinioFile` Limitation: Does NOT Work on `List<String>`

`MinioUrlConverter.convertInternal` treats `String.class` as a simple type (`isSimpleType` returns true) and skips it. When recursing into a `Collection`, each string element hits the guard and is never converted. So `@MinioFile private List<String> imgs` silently does nothing.

**Workaround for image arrays stored as JSON**: Use manual conversion in the service layer:

```java
// SAVE — strip full URLs to relative paths before storing
List<String> urlList = mapper.readValue(jsonString, new TypeReference<List<String>>() {});
urlList.replaceAll(UrlNormalizeUtil::stripUrlPrefix);
entity.setTag(mapper.writeValueAsString(urlList));

// READ — convert relative paths back to full URLs
List<String> imgList = mapper.readValue(entity.getTag(), new TypeReference<List<String>>() {});
imgList.replaceAll(url -> minioUtil.getFullUrl(url));
dto.setImgs(imgList);
```

`MinioUtil.getFullUrl(relativePath)` prepends `file.public-base-url` only when path doesn't start with `http`. Add this method to `MinioUtil` if missing:

```java
public String getFullUrl(String relativePath) {
    if (relativePath == null || relativePath.isBlank()) return relativePath;
    if (relativePath.startsWith("http://") || relativePath.startsWith("https://")) return relativePath;
    return prefix + relativePath;
}
```

## Image Upload Validation

Magic number validation: JPG(`FFD8FF`), PNG(`89504E47`), GIF(`47494638`), BMP(`424D`), ICO(`00000100`). SVG has no magic number — detect by content (`<svg` or `xmlns`).

## API Function Aliasing Pitfall

When one API function is exported as an alias for another (`export const getSuggestions = getTools`), the consuming code loses all visibility into the actual endpoint and response shape. If the alias name implies a different contract than the real function, the UI silently breaks.

**Real example**: `agentApi.ts` had:
```typescript
export const getSuggestions = getTools;  // returns Tool[] (objects with id, name, description...)
```

AgentView.vue consumed it expecting string suggestions:
```typescript
const res = await getSuggestions()
suggestions.value = list  // Tool objects rendered as JSON text in the UI
```

The UI showed raw JSON objects like `{"id":4,"name":"bedtools","description":"Genomic intervals manipulation",...}` instead of clickable suggestion chips.

**Root cause**: No backend `/suggestions` endpoint existed. Someone aliased `getTools` as a placeholder and forgot to fix it.

**Rules**:
1. Never alias API functions with different implied contracts. If the endpoint doesn't exist, remove the export and use frontend defaults.
2. When a UI feature depends on a not-yet-implemented API, use hardcoded defaults in the component — don't wire it to a mismatched endpoint as a "temporary" measure. Temporary aliases become permanent bugs.
3. **Diagnosis pattern**: When the UI renders JSON objects as text, check whether the API function returns the expected type. Grep for the function name in `api/*.ts` and trace to its actual implementation.

## Axios Response Interceptor Unwrapping Pitfall

When the response interceptor unwraps `response.data.result` for successful responses (code 200), ALL downstream code that treats the return value as an AxiosResponse will get `undefined`.

### The Bug Pattern

```typescript
// Response interceptor (CORRECT):
if (code === 200) {
  return Promise.resolve(response.data.result)  // returns PageResult, LoginResult, etc.
}

// request() helper (WRONG):
async function request<T>(config): Promise<T> {
  const res = await axiosInstance.request<T>(config)
  return res.data as T  // BUG: res is already unwrapped, res.data is undefined
}

// CORRECT:
  return res as any  // pass through the already-unwrapped value
```

### Token Refresh Double-Deref

The same pattern breaks token refresh in TWO places:

```typescript
// handleUnauthorized (response interceptor, 401 handler):
const refreshRes = await axiosInstance.post('/api/admin/auth/refreshToken', {
  token: currentToken  // WRONG field name — backend expects 'refreshToken'
})
const newAccessToken = refreshRes.data.result  // WRONG — refreshRes is already unwrapped

// CORRECT:
const refreshRes: any = await axiosInstance.post('/api/admin/auth/refreshToken', {
  refreshToken: currentToken  // match backend RefreshTokenRequest record
})
const newAccessToken = refreshRes?.accessToken  // response is {accessToken, refreshToken} Map
```

### Silent Token Destruction

When `refreshRes.data.result` evaluates to `undefined`:
1. `userStore.token = undefined` → Pinia persistedstate writes to localStorage
2. `getStoredToken()` returns empty string on next request
3. No Authorization header is sent → backend returns 401
4. User appears "not logged in" despite having just logged in

This is especially insidious because:
- It only triggers when `isTokenExpiringSoon(token)` is true (within 5 min of expiry)
- The error is silent (try-catch logs a warning, continues)
- The symptom appears 5 minutes after login, not immediately

### Checklist After Modifying axios.ts

1. `request()` returns `res as any`, NOT `res.data`
2. Both token refresh calls use `refreshToken:` field name (not `token:`)
3. Both access `refreshRes?.accessToken` (not `refreshRes.data.result`)
4. The refresh endpoint returns `{accessToken, refreshToken}` Map, not a plain string

### Frontend vs Admin Separate localStorage

The bioplatform project has TWO independent Vue3 apps:
- `bioplatform-admin` (port 3000) — admin panel
- `bioplatform-front` (port 3001) — public-facing site

**They use DIFFERENT localStorage keys:**
- **Admin** (`bioplatform-admin`): stores token directly as `localStorage.getItem('access_token')` and refresh token as `localStorage.getItem('refresh_token')`. Uses raw axios interceptors.
- **Front** (`bioplatform-front`): stores token in `localStorage.getItem('bio_user')` as JSON `{ token, userInfo }` via `pinia-plugin-persistedstate`. Uses a different axios wrapper.

Logging in on admin does NOT log you in on front. When debugging "user is logged in but API says 401", check which port's localStorage has the token.

**Pitfall: Wrong token key in shared components**. When a component (e.g., FeedbackChat, agentApi) is used in BOTH frontends, it MUST read the token using the correct key for each frontend. Using `localStorage.getItem('bio_user')` in the admin context returns null → WebSocket never connects → "无法发送消息" with no error visible. The admin feedback WebSocket read `bio_user` instead of `access_token` and silently failed to connect for an entire debugging session.

```typescript
// WRONG — only works in front, returns null in admin
const stored = localStorage.getItem('bio_user')
const token = stored ? JSON.parse(stored).token : null

// CORRECT for admin components
const token = localStorage.getItem('access_token') || ''

// CORRECT for front components
const stored = localStorage.getItem('bio_user')
const token = stored ? JSON.parse(stored).token : ''
```

When writing code that touches auth tokens, always check which frontend the code runs in. The admin and front have completely separate auth flows despite sharing the same backend.

**Real mistake**: User said "前台明明已经登录了" but the agent's headless browser (on port 3001) showed no token. The user was logged in on admin (port 3000) but not on front (port 3001). The user had to explicitly say "不是已经登录了吗" before the agent checked the right frontend.

### LLM Config from Database (Not application.yml)

When the backend reads LLM config from `system_configs` table (not `application.yml`), changing the yml file has zero effect. The AgentServiceImpl reads:
```java
SystemConfig apiKeyConfig = systemConfigMapper.selectByKey("llm_api_key");
```

Config keys: `llm_api_key`, `llm_model`, `llm_base_url`. Update via admin panel or SQL:
```sql
UPDATE system_configs SET config_value = 'sk-...' WHERE config_key = 'llm_api_key';
```

## Element Plus Sidebar Collapse Pattern

Admin panels with `el-aside` sidebars should support collapse to give more space to the main content area. Both `bioplatform-admin` and `bioplatform-front` use this pattern for the Agent conversation sidebar.

### Implementation

```vue
<template>
  <el-aside :width="sidebarCollapsed ? '48px' : '280px'" class="sidebar" style="transition: width 0.2s;">
    <div class="sidebar-header">
      <span v-if="!sidebarCollapsed">Title</span>
      <div style="display: flex; gap: 4px; margin-left: auto;">
        <el-button v-if="!sidebarCollapsed" type="primary" size="small" @click="addItem">
          <el-icon><Plus /></el-icon>
        </el-button>
        <el-button size="small" circle @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon><component :is="sidebarCollapsed ? 'Expand' : 'Fold'" /></el-icon>
        </el-button>
      </div>
    </div>
    <div v-if="!sidebarCollapsed" class="sidebar-content">
      <!-- list content -->
    </div>
  </el-aside>
</template>

<script setup>
import { Expand, Fold } from '@element-plus/icons-vue'
const sidebarCollapsed = ref(false)
</script>
```

### Key details
- `:width` binding toggles between collapsed (48px) and expanded (280px)
- `transition: width 0.2s` for smooth animation
- Content wrapped in `v-if="!sidebarCollapsed"` to fully remove from DOM when collapsed
- Fold/Expand icons from `@element-plus/icons-vue` — must be imported
- Header title hidden when collapsed (`v-if="!sidebarCollapsed"`)

## Chat UI Error Handling Pattern

**User preference: NEVER show error details in the chat UI.** The user explicitly said "不要把错误放到用户的视线内". When the LLM call fails, the UI should silently return to its normal state.

### Correct Pattern (Silent Error Handling)

```typescript
// onError — silent, don't show error to user
(err) => {
  // If no tokens were received, remove the empty assistant message
  if (!messages.value[assistantIdx].content) {
    messages.value.splice(assistantIdx, 1)
  }
  loading.value = false
  scrollToBottom()
}
```

Backend also sends `{done:true}` instead of `{error:"..."}` on failure — the error is logged server-side only:
```java
} catch (Exception e) {
    log.error("流式消息发送失败: conversationId={}, userId={}, error={}", conversationId, userId, e.getMessage(), e);
    try {
        emitter.send(SseEmitter.event()
                .data("{\"done\":true,\"conversationId\":" + conversationId + "}"));
        emitter.complete();
    } catch (Exception ex) {
        emitter.complete();
    }
}
```

Key rules:
- Backend logs the full error with stack trace — always visible in server logs
- Frontend receives `{done:true}` — treats it as normal stream end
- Empty assistant message (no tokens received) is removed from the UI
- Partial responses (some tokens received) are kept as-is — the user sees what the LLM managed to produce
- No toast, no inline error, no warning icon — the UI just stops loading

### Why NOT show errors inline

Previous pattern showed `⚠️ error message` as an assistant message. User corrected this: technical errors like "LLM API调用失败: 500" or "API Key 为遮蔽值" are not useful to end users and make the chat feel broken. The errors should be in the backend logs where the developer can see them.

### Debugging When No Output Appears

When the user reports "no response at all" and backend logs show nothing:
1. Check if `fetch` includes the Authorization header (see fetch auth pitfall above)
2. Check if SseEmitter has a reasonable timeout (not `0L` — use `5 * 60 * 1000L`)
3. Check if the Thread name includes the conversationId for log tracing
4. The `new Thread()` catch block must ALWAYS send `done` + call `emitter.complete()` — if it dies silently, the client hangs forever

### Avatar Consistency

When admin and front-end share the same feature (e.g., AI chat), avatar styles must match. The bioplatform front-end uses gradient-circle icons:

```vue
<div class="msg-avatar" :class="msg.role">
  <el-icon><ChatDotRound v-if="msg.role === 'assistant'" /><User v-else /></el-icon>
</div>
```

```css
.msg-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}
.msg-avatar.assistant { background: linear-gradient(135deg, #409eff, #67c23a); color: #fff; }
.msg-avatar.user { background: linear-gradient(135deg, #67c23a, #409eff); color: #fff; }
```

The admin initially used `el-avatar` with text ("U" / "AI") — completely different look. Always check the other frontend's implementation when adding shared features.

### Typing Indicator

When waiting for LLM response, show a 3-dot typing animation:

```vue
<div v-if="sending" class="message-item assistant">
  <div class="msg-avatar assistant"><el-icon><ChatDotRound /></el-icon></div>
  <div class="message-content">
    <div class="typing-indicator"><span></span><span></span><span></span></div>
  </div>
</div>
```

```css
.typing-indicator { display: flex; gap: 4px; padding: 12px 16px; }
.typing-indicator span {
  width: 8px; height: 8px; border-radius: 50%; background: #c0c4cc;
  animation: typing 1.4s infinite ease-in-out;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
```

## SSE Streaming for LLM Chat (Spring Boot + Vue3)

When the backend calls an LLM API synchronously, the user waits for the full response before seeing anything. For long answers (10-30s), this feels broken. SSE streaming sends tokens as they arrive, giving instant feedback.

### Backend: SseEmitter + OkHttp Streaming

Add `stream: true` to the LLM request body and read the response line-by-line:

```java
// AgentService interface
SseEmitter streamChat(Long conversationId, String content, Long userId);

// AgentServiceImpl
@Override
public SseEmitter streamChat(Long conversationId, String content, Long userId) {
    SseEmitter emitter = new SseEmitter(5 * 60 * 1000L); // 5 minute timeout (0L hangs forever on error)
    // Save user message first
    messageMapper.insert(userMessage);
    // Get history (includes the just-saved user message)
    List<AgentMessage> history = messageMapper.selectRecentByConversationId(conversationId, 20);

    // CRITICAL: propagate SecurityContext to async thread
    SecurityContext securityContext = SecurityContextHolder.getContext();

    new Thread(() -> {  // name thread for log tracing: "sse-stream-" + conversationId
        SecurityContextHolder.setContext(securityContext);
        try {
            String fullContent = streamLlmApi(model, history, emitter);
            // Save complete assistant message after stream ends (only if non-empty)
            if (fullContent != null && !fullContent.isEmpty()) {
                assistantMessage.setContent(fullContent);
                messageMapper.insert(assistantMessage);
            }
            // Send done event
            emitter.send(SseEmitter.event().data("{\"done\":true,\"conversationId\":" + id + "}"));
            emitter.complete();
        } catch (Exception e) {
            log.error("Stream failed: {}", e.getMessage(), e);
            // On error: send done (NOT error) — error is logged server-side only
            try {
                emitter.send(SseEmitter.event().data("{\"done\":true,\"conversationId\":" + id + "}"));
                emitter.complete();
            } catch (Exception ex) {
                emitter.complete();
            }
        } finally {
            SecurityContextHolder.clearContext();
        }
    }).start();
    return emitter;
}
```

Key points:
- `SseEmitter(5 * 60 * 1000L)` = 5 minute timeout. `0L` (no timeout) causes the client to hang forever if the thread dies silently before sending any data.
- Save user message BEFORE starting the stream (so history includes it)
- Save assistant message AFTER stream completes (only if content is non-empty)
- `new Thread()` with named thread for log tracing; use `ExecutorService` for production
- `@EnableAsync` on the application class for `@Async` methods (e.g. title generation)
- On error: send `{done:true}` (not `{error:"..."}`) to silently end the stream
- Only save assistant message if `fullContent` is non-empty — skip DB insert on complete failure
- **Null delta guard**: LLM APIs (OpenAI-compatible) send `delta.content: null` during streaming (e.g., at the start of a response or between chunks). Jackson's `asText()` converts JSON null to the string `"null"`, which renders as "nullnullnull..." in the UI. Always check `!delta.get("content").isNull()` in addition to `delta.has("content")`:
  ```java
  // WRONG — has("content") is true even when value is null
  if (delta != null && delta.has("content")) {
      String token = delta.get("content").asText();  // returns "null" string
  }
  // CORRECT — also check isNull()
  if (delta != null && delta.has("content") && !delta.get("content").isNull()) {
      String token = delta.get("content").asText();
  }
  ```

### Backend: Controller Endpoint

```java
@PostMapping("/chat/stream")
public SseEmitter chatStream(@RequestBody Map<String, Object> params) {
    // Same param parsing as /chat, but return SseEmitter instead of ApiResponse
    // For errors before streaming starts, create a dummy emitter and send error:
    SseEmitter errEmitter = new SseEmitter();
    errEmitter.send(SseEmitter.event().data("{\"error\":\"消息内容不能为空\"}"));
    errEmitter.complete();
    return errEmitter;
}
```

### Backend: SSE Response Format

```
Content-Type: text/event-stream

data: {"delta":"你"}
data: {"delta":"好"}
data: {"delta":"，"}
data: {"done":true,"conversationId":123,"title":"RNA-seq分析问题"}
```

- `delta` events: incremental token text (append to UI)
- `error` events: error message (show in chat)
- `done` event: stream complete, includes conversationId and optional title

### Frontend: fetch + ReadableStream

axios does NOT support streaming. Use native `fetch`:

**CRITICAL PITFALL: `fetch` bypasses axios interceptors.** The JWT `Authorization` header is NOT added automatically. You MUST read the token from localStorage and add it manually. Without this, the backend returns 401 and the stream never starts — no error is visible in the browser console or backend logs.

```typescript
export function chatStream(
  data: ChatRequest,
  onToken: (token: string) => void,
  onDone: (info: { conversationId: string }) => void,
  onError: (err: string) => void
): AbortController {
  const abortController = new AbortController()
  // MUST manually add auth — fetch doesn't use axios interceptors
  const token = localStorage.getItem('access_token') || ''  // admin
  // const token = JSON.parse(localStorage.getItem('bio_user') || '{}').token || ''  // front
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  fetch(`/api/admin/agent/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
    signal: abortController.signal,
  }).then(async (response) => {
    const reader = response.body?.getReader()
    if (!reader) { onError('无法读取响应流'); return }
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // keep incomplete line in buffer
      for (const line of lines) {
        // CRITICAL: use 'data:' NOT 'data: ' — Spring SseEmitter may omit the space
        if (!line.startsWith('data:')) continue
        const jsonStr = line.slice(5).trim()  // handles both 'data:{...}' and 'data: {...}'
        if (!jsonStr) continue
        const obj = JSON.parse(jsonStr)
        if (obj.error) { onError(obj.error); return }
        if (obj.done) { onDone({ conversationId: String(obj.conversationId) }); return }
        if (obj.delta) { onToken(obj.delta) }
      }
    }
  }).catch(e => { if (e.name !== 'AbortError') onError(e.message) })
  return abortController
}
```

### Frontend: AgentView Streaming Render — Use Separate `streamingContent` Ref

**CRITICAL PITFALL: Do NOT push an empty assistant message and mutate it via `+=`.**

The "push empty message, then `messages.value[idx].content += token`" pattern FAILS in Vue3. Symptoms:
1. Empty message bubble visible before any tokens arrive (looks like a blank extra message)
2. Tokens accumulate but DOM doesn't update in real-time (Vue proxy doesn't track deep mutation in fetch callbacks)
3. Stream finishes, then ALL content appears at once
4. "null" rendered in the UI when content is undefined

**Root cause**: `messages.value[idx].content += token` in an async callback (fetch ReadableStream) goes through Vue's proxy, but the DOM update is deferred/batched in a way that doesn't reflect per-token. The proxy's reactivity tracking breaks across async boundaries from non-Vue sources (fetch, ReadableStream).

**Correct pattern — separate `streamingContent` ref:**

```typescript
const streamingContent = ref('')

// In template: render streaming content separately from messages array
// <div v-if="streamingContent" class="message-wrapper assistant-message">
//   <div class="message-text" v-html="renderStreamContent(streamingContent)"></div>
// </div>
// <div v-if="loading && !streamingContent" class="typing-indicator">...</div>

// In sendMessage:
streamingContent.value = ''
chatStream(
  { message: text, conversationId: conversationId.value || undefined },
  // onToken — mutate a simple ref, Vue guarantees reactivity
  (token) => {
    streamingContent.value += token
    scrollToBottom()
  },
  // onDone — transfer streaming content into messages array
  (info) => {
    if (streamingContent.value) {
      messages.value.push({
        role: 'assistant',
        content: streamingContent.value,
        timestamp: Date.now(),
      })
    }
    streamingContent.value = ''
    loading.value = false
  },
  // onError — silent, just clean up
  () => {
    streamingContent.value = ''
    loading.value = false
  }
)
```

**Why this works**: `streamingContent` is a top-level `ref('')`. Vue3 tracks `ref.value` mutations perfectly, even in async callbacks. The template's `v-if="streamingContent"` shows/hides the streaming bubble, and `v-html` re-renders on every `.value` change.

**Additional template rules:**
- `v-if="msg.content"` on messages — hides empty/null content from rendering
- Typing indicator: `v-if="loading && !streamingContent"` — hide once tokens start arriving
- `renderStreamContent()` needs `if (!content) return ''` null guard
- For admin: use simple `renderMarkdown()` with null check
- For front: use `marked.parse()` (same as ChatMessage component) — needs `import { marked }` in AgentView

**CSS for streaming bubble**: The streaming message div is in AgentView (not ChatMessage component), so it needs its own bubble styles. Copy `.message-bubble.assistant` styles from ChatMessage component into AgentView's `<style scoped>`.

### Pitfall: http.defaults Doesn't Exist on Custom Wrappers

When the project's axios.ts exports a custom wrapper object (not the axios instance), `http.defaults.baseURL` throws. Use relative URLs instead (`/api/...` — the dev server proxy handles routing).

### Pitfall: SseEmitter Async Thread Has No SecurityContext

When `SseEmitter` uses `new Thread()`, the worker thread has an empty `SecurityContextHolder`. When `emitter.complete()` triggers Tomcat async dispatch, Spring Security's `AuthorizationFilter` re-runs on a thread with no authentication → `AuthorizationDeniedException: Access Denied`.

**Error pattern**: Backend log shows `流式消息发送成功` (stream succeeded) immediately followed by `AuthorizationDeniedException`. The stream itself works, but the async dispatch after completion fails. The client may hang or get a broken connection.

**Root cause**: `SecurityContextHolder` uses `ThreadLocal`. The original request thread has the JWT authentication, but `new Thread()` starts with empty `ThreadLocal` values.

**Fix — propagate SecurityContext**:
```java
// In streamChat(), BEFORE creating the thread:
SecurityContext securityContext = SecurityContextHolder.getContext();

new Thread(() -> {
    SecurityContextHolder.setContext(securityContext);
    try {
        // ... stream LLM response ...
    } catch (Exception e) {
        // ... error handling ...
    } finally {
        SecurityContextHolder.clearContext();  // prevent memory leak
    }
}, "sse-stream-" + conversationId).start();
```

**Key points**:
- Capture `SecurityContext` in the calling thread (controller thread, has JWT auth)
- Set it at the start of the worker thread
- Clear it in `finally` to prevent `ThreadLocal` memory leaks in the thread pool
- This also applies to `LoginUserHolder` if it uses `ThreadLocal` (it does in bioplatform)

**Why NOT just permit the endpoint**: The endpoint needs authentication to know which user is sending the message. Permitting it would allow anonymous access.

**Second fix needed — SecurityConfig**: The `SecurityContext` propagation alone is NOT sufficient. Tomcat's async dispatch uses a DIFFERENT thread from the thread pool (not the worker thread). The `SecurityContextHolder` set on the worker thread is not visible to the dispatch thread. Configure `RequestAttributeSecurityContextRepository` in SecurityConfig to save the security context in request attributes (which persist across async dispatch):

```java
// In SecurityConfig.securityFilterChain():
http
    .securityContext(sc -> sc
        .securityContextRepository(new RequestAttributeSecurityContextRepository())
    )
    // ... rest of config
```

Import: `org.springframework.security.web.context.RequestAttributeSecurityContextRepository`

Without this, the log shows `流式消息发送成功` (stream succeeded) followed immediately by `AuthorizationDeniedException` on every SSE completion. The stream works fine for the client, but the log spam is annoying and indicates a real security gap.

### Pitfall: SSE + POST, Not GET

SSE is traditionally GET with `EventSource`, but chat needs a request body (message, conversationId). Use POST + fetch + ReadableStream instead. `EventSource` does not support POST.

## Conversation Auto-Naming

When all conversations show "新对话", the sidebar is useless. Generate titles from the user's first message (truncated) — no LLM call needed.

```java
private void generateTitle(AgentConversation conversation, String userMessage) {
    try {
        String title = userMessage.replaceAll("\\s+", " ").trim();
        if (title.length() > 20) title = title.substring(0, 20);
        conversation.setTitle(title);
        conversationMapper.updateById(conversation);
    } catch (Exception e) {
        log.warn("生成对话标题失败: {}", e.getMessage());
    }
}
```

Trigger in `streamChat` after saving the assistant message, BEFORE sending the `done` event:
```java
if ("新对话".equals(conversation.getTitle())) {
    generateTitle(conversation, userMessage);
}
// Then send done event — frontend receives title in loadConversations()
```

### Why NOT use @Async + LLM for title generation

1. **`@Async` doesn't work with self-invocation**: When `generateTitle()` is called from within the same bean (`AgentServiceImpl`), Spring's proxy doesn't intercept it — the method runs synchronously regardless of `@Async`. This is a fundamental Spring limitation.
2. **Extra LLM call adds latency**: Making a second API call to the LLM just for a 20-char title adds 1-3 seconds of blocking time.
3. **LLM calls can fail**: Network issues, rate limits, or API errors silently swallow the title. Simple truncation never fails.
4. **Truncation is good enough**: Users recognize their own messages. "RNA-seq 数据分析的标准流程" as a title is immediately recognizable.

### Frontend fallback

Both admin and front sidebar should show `conv.title || '新对话'` for backward compatibility with old conversations that have no title.

## Conversation List Delete Pattern

When a chat sidebar shows conversation items, each item should have a delete icon that appears on hover. The icon is hidden by default (`opacity: 0`) and fades in when the conversation item is hovered.

### Template

```vue
<div v-for="conv in conversations" :key="conv.id"
  class="conversation-item" :class="{ active: currentId === conv.id }"
  @click="selectConversation(conv.id)">
  <div class="conv-title">{{ conv.title || '新对话' }}</div>
  <div style="display: flex; align-items: center; gap: 4px;">
    <div class="conv-time">{{ conv.updatedAt }}</div>
    <el-icon class="conv-delete" @click.stop="handleDelete(conv.id)"><Delete /></el-icon>
  </div>
</div>
```

Key: `@click.stop` on the delete icon prevents the click from bubbling to the parent's `@click` (which would select the conversation).

### CSS

```css
.conv-delete {
  color: #c0c4cc;
  cursor: pointer;
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
}
.conversation-item:hover .conv-delete { opacity: 1; }
.conv-delete:hover { color: #f56c6c; }
```

### Handler

```typescript
import { ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

const handleDelete = async (id: string) => {
  try {
    await ElMessageBox.confirm('确定删除该对话？', '提示', { type: 'warning' })
  } catch { return }  // user cancelled
  await deleteConversation(id)
  if (currentId.value === id) {
    currentId.value = ''
    messages.value = []
  }
  await loadConversations()
}
```

Rules:
- Always confirm before delete (`ElMessageBox.confirm`)
- If the deleted conversation was the active one, clear the chat area
- Reload the conversation list after deletion
- `Delete` icon must be imported from `@element-plus/icons-vue`
- `ElMessageBox` needs manual CSS import in `main.ts` (see Element Plus Programmatic CSS Import section)

## OkHttp Connection Pooling for LLM Calls

When the backend makes repeated HTTP calls to the same LLM API host, use a connection pool to avoid TCP handshake overhead on each request:

```java
this.httpClient = new OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)    // fast fail on connect
        .readTimeout(120, TimeUnit.SECONDS)      // LLM responses can be slow
        .writeTimeout(10, TimeUnit.SECONDS)
        .connectionPool(new ConnectionPool(5, 5, TimeUnit.MINUTES))
        .retryOnConnectionFailure(true)
        .build();
```

Without the pool, each LLM call does a full TCP + TLS handshake (adds ~200-500ms per call). The pool keeps 5 idle connections alive for 5 minutes.

## Element Plus Programmatic CSS Import

(See also: Axios Response Interceptor Unwrapping Pitfall section above for the most common source of silent data-flow breaks in Spring Boot + Vue3 projects.)

`unplugin-vue-components` with `ElementPlusResolver` auto-imports CSS for template components only. Programmatic calls (`ElMessageBox.confirm()`, `ElMessage()`) need manual CSS import in `main.ts`:

```typescript
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-message.css'
```

Without these, `ElMessageBox` appears unstyled in the top-left corner with no overlay. Affects any Element Plus component used only via JS API.

## Logback Relative Path Creates Duplicate Log Directories

When `logback-spring.xml` uses a relative path like `logs/bioplatform.log`, the actual log file location depends on the **working directory** at JVM startup:

- Starting from `bioplatform-springboot/` (IDEA run) → creates `bioplatform-springboot/logs/`
- Starting from `bioplatform/` (Docker, terminal `cd` to root) → creates `bioplatform/logs/`

Both directories end up in git if `.gitignore` pattern is wrong. The fix is `.gitignore` with `**/logs` (already covers nested dirs) and `git rm -r --cached` to remove tracked log files.

**Prevention**: Use an absolute path or `${user.home}` in logback config to avoid ambiguity:
```xml
<file>${user.home}/logs/bioplatform.log</file>
```

## Remote Database Schema Drift

When code references columns that don't exist in the remote DB (e.g. `Unknown column 'is_top'`), the ALTER TABLE was never executed. MySQL runs inside Docker container `blog_mysql`:

```bash
ssh -p 20225 39.97.180.240 "docker exec blog_mysql mysql -uroot -p3rQndkCBaN3xqRTHE2f4 blog -e \"ALTER TABLE comments ADD COLUMN is_top TINYINT(1) DEFAULT 0 AFTER tag;\""
ssh -p 20225 39.97.180.240 "docker exec blog_mysql mysql -uroot -p3rQndkCBaN3xqRTHE2f4 blog -e \"ALTER TABLE comments MODIFY COLUMN tag TEXT DEFAULT NULL;\""
```

**Pattern**: Check remote column type vs schema definition — remote may have stale `varchar(32)` when schema says `TEXT`.

### `@RequestBody Map<String, Object>` Null-Safety Pitfall

When using `@RequestBody Map<String, Object>` instead of a typed DTO, `params.get("key")` returns `null` when the key is missing or the value is null. Calling `.toString()` on null throws NPE.

**Bug pattern:**
```java
String content = params.get("content").toString();  // NPE if "content" is missing
```

**Fix — always null-check:**
```java
Object contentObj = params.get("content");
if (contentObj == null || contentObj.toString().isBlank()) {
    return ApiResponse.error(400, "消息内容不能为空");
}
String content = contentObj.toString().trim();
```

**Also check field name alignment.** The frontend may send a different key than the backend reads. When using `Map<String, Object>`, there's no compile-time check. Accept multiple names if needed:
```java
Object contentObj = params.get("content");
if (contentObj == null) {
    contentObj = params.get("message");  // frontend uses this name
}
```

**Better alternative**: Use a typed DTO record instead of `Map<String, Object>` — catches field name mismatches at compile time.

### Empty String Passes Null Check But Breaks Long.valueOf

When the frontend sends `conversationId: ""` (empty string, e.g. from `ref('')`), `params.get("conversationId")` returns `""` (NOT null), so a `== null` check passes. Then `Long.valueOf("")` throws `NumberFormatException`.

**Bug pattern:**
```java
if (params.get("conversationId") == null) {
    return ApiResponse.error(400, "conversationId不能为空");
}
Long conversationId = Long.valueOf(params.get("conversationId").toString());  // NFE on ""
```

**Fix — check both null AND blank:**
```java
Long conversationId = null;
Object convIdObj = params.get("conversationId");
if (convIdObj != null && !convIdObj.toString().isBlank()) {
    conversationId = Long.valueOf(convIdObj.toString());
}
```

This pattern converts the "missing optional field" case into a `null` variable that downstream code can handle gracefully (e.g., auto-create a conversation).

**Real incident**: Admin agent chat endpoint required `conversationId` (returned 400 if missing), while the front agent endpoint auto-created conversations when `conversationId` was null. Admin frontend's `createConversation()` set `currentConversationId = ''` locally without calling the backend, so the first message sent `conversationId: ""` → NFE.

## Field Name Mismatch: Fix Frontend, NOT Backend

When backend DTO field name (e.g. `nickname`) doesn't match frontend type (e.g. `nickName`), **fix the frontend** — change the TypeScript interface + template. Never rename the backend DTO field. Other business logic, other pages, or other API consumers may depend on the existing backend field name.

## `comments` Table Dual Purpose

The `comments` table stores both regular comments AND "说说" (talks), distinguished by `type` column (`post`, `comment`, `talk`). The `tag` column stores talk images as a JSON array of image URLs. This JSON must follow the same relative-path convention as all other image fields.

### Type Semantics Pitfall

The `type` field represents **what the entity IS**, not **what it's ON**. Types: `post` (article root comment), `comment` (child comment at any depth), `talk` (the talk/说说 itself), `talk_comment` (talk root comment), `message` (message board entry).

When a user comments on a talk, the comment must have `type='talk_comment'` (root) or `type='comment'` (reply to a talk_comment), NOT `type='talk'`. Using `type='talk'` for a comment causes it to appear as a new independent talk.

In `ParentItem.vue`, the publish handler uses: `type: data.forId ? "comment" : props.type`. Root comments get `props.type` (e.g. `talk_comment`), child comments get `"comment"`.

**CommentConvertUtil.buildCommentTree()** must be updated when adding new types — it only recognizes specific type strings as root comments.

## Comment Tree Building for Shared-Table Architecture

When `comments` table stores both entities (talks, messages) AND comments on them (all with `type='comment'`), the tree builder must distinguish root comments from child comments by comparing `forId` and `rootId`:

```java
if ("post".equalsIgnoreCase(a.getType())) {
    roots.add(current);  // article top-level comment
} else if ("comment".equalsIgnoreCase(a.getType())) {
    if (a.getForId() != null && a.getForId().equals(a.getRootId())) {
        roots.add(current);  // direct comment on a talk/message (forId == rootId == entity id)
    } else {
        // reply to another comment (forId != rootId)
        FrontCommentResponse parent = idToComment.get(a.getForId());
        if (parent != null) parent.getChildComments().add(current);
    }
}
```

The `FrontArticleCommentResponse` DTO must include `rootId`, and the SQL query must select `c.root_id`.

### TypeScript Type Union Updates

When adding new string-union types (e.g. comment types, status types), ALL three layers must match:

1. TypeScript type definition (`types/comment.ts`): `"post" | "comment" | "talk" | "talk_comment"`
2. Component prop definition (`Comment/index.vue`): must match the union
3. Business logic that references the type (e.g. `ParentItem.vue` publish handler)

If any layer is out of sync, TypeScript build fails with `Type 'xxx' is not assignable`. The error points to the component prop, not the type definition — check both.

## art-table Selection Column Duplication

The `art-table` component's `selection` prop auto-adds a `<el-table-column type="selection" />`. If the page template also manually includes one, you get two checkbox columns side by side. **Use one or the other, never both.**

```vue
<!-- WRONG: selection prop + manual column = two checkbox columns -->
<art-table selection ...>
  <template #default>
    <el-table-column type="selection" />  <!-- DELETE THIS -->
    ...

<!-- CORRECT: use only the prop -->
<art-table selection ...>
  <template #default>
    <el-table-column prop="name" ... />
```

## Pagination Initial Value Bug

Backend `@Min(1)` validation on pagination `current` field means frontend must initialize with `ref(1)`, NOT `ref(0)`. Symptom: initial load returns empty/error, but switching filters (which reset `current` to 1) makes data appear.

## Comment Component `expand` Prop

The `<Comment>` component uses `isExpand` (default false) to control visibility of the comment list and input area. When `isShowToggle=false`, there's no "查看更多" button. For pages that should always show comments (like talk/说说), pass `:expand="true"`.

## Admin Comment Type Filter

Admin comment management page filters by `type` array. If a new comment type is added (e.g. `'talk'`), it won't appear in admin review until added to the filter:
```js
type: ['comment', 'post', 'talk']  // was ['comment', 'post']
```

## Schema-Driven Dynamic Forms

When the backend provides a JSON schema (e.g. `{ type, required, nullable, description, path, properties }`), the frontend can render forms dynamically via `SchemaForm.vue` + `SchemaFormItem.vue`. See `references/schema-driven-forms.md` for the full component architecture, schema-to-component mapping table, and workflow template import pattern. See `references/import-loop-and-config-display.md` for import error handling and structured config preview patterns.

**Important**: For complex, deeply nested configs (bioinformatics workflows with 3+ levels, dynamic keys, incomplete schemas), **JSON editor is a better fit than schema-driven forms**. The bioplatform project tried both and settled on JSON editor only. See `references/schema-driven-forms.md` for the decision guide.

For batch import error handling, silent skip diagnosis, and debug endpoint patterns, see `references/import-batch-debugging.md`.

### Pitfall: Omics schema uses short type names

The Omics repository uses `str`/`int`/`bool`/`dict`/`list`/`null` — NOT `string`/`integer`/`boolean`. SchemaFormItem's type detection must handle both:
```typescript
const isBool = computed(() => props.schema.type === 'boolean' || props.schema.type === 'bool')
const isNumber = computed(() => ['integer', 'int', 'number', 'float'].includes(props.schema.type))
const isString = computed(() => props.schema.type === 'string' || props.schema.type === 'str')
```

### Pitfall: Config template pre-fill must filter system fields

When loading a template's `configTemplate` as default form values, filter out fields that are auto-filled at execution time: `ROOT_DIR`, `indir`, `outdir`, `logdir`, `raw_files`, `outfiles`. These are computed from project context, not user input.

### Pitfall: `null` vs `undefined` for Element Plus component props

`vue-tsc` errors like `Type 'null' is not assignable to type 'string | number | boolean | undefined'` occur because EP component props accept `undefined` but not `null`. When initializing refs for form data that feeds EP components, use `undefined` not `null`:
```typescript
// WRONG: const selectedId = ref<number | null>(null)
// RIGHT: const selectedId = ref<number | undefined>(undefined)
```
This affects `el-radio-group` v-model, `el-select` v-model, and any prop typed with `| undefined`.

## Admin WorkTab (Multi-Tab Navigation)

Vue3 admin panels benefit from a tab-based navigation system where each visited route becomes a persistent tab. Users can switch between modules without losing form state (thanks to `keep-alive`).

### Architecture

Two core files:

1. **`stores/worktab.ts`** — Pinia store managing `opened: WorkTab[]` and `currentPath`. Actions: `openTab`, `closeTab`, `closeOtherTabs`, `closeLeftTabs`, `closeRightTabs`, `closeAllTabs`. Dashboard tab is always present and non-closable.

2. **`components/WorkTab.vue`** — Renders horizontal scrollable tab bar between header and main content. Features:
   - Mouse wheel horizontal scroll via `translateX` transform
   - Right-click context menu with `teleport to="body"` + `position: fixed`
   - Dropdown batch operations menu (close current/other/left/right/all)
   - Auto-position active tab into viewport on route change

3. **`AdminLayout.vue`** — Integrates WorkTab + keep-alive + refresh:
   ```vue
   <script setup lang="ts">
   import { ref, nextTick } from 'vue'
   const isRefresh = ref(true)
   function reload() {
     isRefresh.value = false
     nextTick(() => { isRefresh.value = true })
   }
   </script>

   <template>
     <el-header>
       <el-icon class="refresh-btn" @click="reload()"><Refresh /></el-icon>
       <!-- breadcrumb etc -->
     </el-header>
     <WorkTab />
     <el-main>
       <router-view v-if="isRefresh" v-slot="{ Component }">
         <keep-alive>
           <component :is="Component" />
         </keep-alive>
       </router-view>
     </el-main>
   </template>
   ```
   Route watcher calls `worktabStore.openTab()` on every navigation with `{ immediate: true }`.

### Page Refresh: use v-if, NOT keep-alive :exclude

The `keep-alive :exclude` approach does NOT work reliably (component name mismatch, unreliable exclude/clear cycle). Use `v-if` on `<router-view>` instead — destroy and recreate the view tree. Place the refresh button in the header bar (next to collapse, before breadcrumb), not in the tab bar. See `references/keepalive-refresh.md` for the full story.

### Key implementation details

- Router must export both default and named: `export { router }; export default router` — the store imports the named export for programmatic navigation on tab close.
- Tab closable flag: dashboard has `closable: false`, all others default to `true`.
- `keep-alive` preserves component state across tab switches. Without it, switching tabs re-renders and loses scroll position / form data / table pagination state.
- Context menu uses `<teleport to="body">` to avoid overflow clipping from the scroll container.
- Active tab auto-position watches `currentPath` and scrolls the tab bar so the active tab is always visible.
- Tab styling: 28px height, 12px font, active = `#409eff` solid bg, hover = `#ecf5ff`.

## Docker Deployment

Build → save → scp → load → recreate. Check `docker-compose` vs `docker compose` on remote.

## ImagePicker Component Pattern

When building an image library picker:
- `@select` event must return **full URL** (not relative path) for preview in editors
- Use `getImageDisplayUrl(filePath)` to prepend MinIO base URL
- `el-image` with `preview-src-list` blocks click selection — remove it for "click to select" behavior
- `NormalToolbar` in md-editor-v3 needs `trigger` prop with SVG icon to render visibly
- To add option to md-editor-v3's built-in image dropdown, use DOM injection (`onMounted` + `nextTick`)

## Favicon Public API

Frontend favicon needs to work for non-logged-in visitors. Create a dedicated endpoint:
```java
@GetMapping("/getFrontInfo")
public ApiResponse<SomeFrontInformation> getFrontInfo() {
    return blogSettingService.getSomeFrontInformationById(1L); // default user
}
```
Frontend `app-init.ts` calls this on load. `@MinioFile` annotation on the favicon field auto-converts relative path to full URL.

## Java Raw Generic Type Warnings

When a generic wrapper like `PageResult<T>` is used without its type parameter (`PageResult` instead of `PageResult<Project>`), the Java compiler emits raw type warnings. These are warnings, not errors — the code compiles and runs fine — but they indicate lost type safety.

### Pattern: Fix All Layers at Once

A raw type in a Spring Boot layered architecture typically appears in 3 places per method:

1. **Service interface** — `PageResult listPipelines(...)` → `PageResult<Pipeline> listPipelines(...)`
2. **Service implementation** — `public PageResult listPipelines(...)` → `public PageResult<Pipeline> listPipelines(...)`
3. **Controller** — `ApiResponse<PageResult> list(...)` + `PageResult result = ...` → `ApiResponse<PageResult<Pipeline>>` + `PageResult<Pipeline> result = ...`

### How to Identify the Correct Type Parameter

Look at the `PageResult.of(...)` call in the service impl — the 4th argument is the list, and its generic type is the correct parameter:

```java
List<Pipeline> pipelines = pipelineMapper.selectAll(param);
return PageResult.of(pageInfo.getTotal(), pageNum, pageSize, pipelines);  // → PageResult<Pipeline>
```

When the impl returns a DTO list instead of entity list:
```java
List<FrontProjectListDTO> dtoList = projects.stream().map(...).toList();
return PageResult.of(pageInfo.getTotal(), pageNum, pageSize, dtoList);  // → PageResult<FrontProjectListDTO>
```

### Batch Fix Strategy

When many files need the same treatment, use `execute_code` with a loop of `patch()` calls rather than individual tool calls. Group by layer (interfaces first, then impls, then controllers) to avoid confusion. Verify with `mvn compile -q` after all patches.

### Pitfall: patch() silently fails on multi-line edits

The `patch()` tool — both standalone and inside `execute_code` — silently fails when `old_string` doesn't match exactly (whitespace, indentation, line endings). The call returns `{"success": true}` but the file is unchanged.

**This is a recurring, session-proven problem.** In one session, patches to Pipeline.java, PipelineMapper.xml, PipelineServiceImpl.java, and AdminProjectController.java ALL failed silently — via both `execute_code` patches AND direct `patch` tool calls. Every single one required `write_file` for the complete file to fix.

**Diagnosis pattern**: After any patch, verify with grep:
```python
# In execute_code:
result = terminal("grep -c 'expected_new_text' target_file.java")
# If count is 0, patch failed
```

Or after standalone patch calls:
```bash
grep -c 'expected_new_text' /path/to/file.java
```

**When patches fail on a file**: Stop trying patches immediately. Use `write_file` to rewrite the entire file. This is always more reliable than debugging why old_string doesn't match. Read the current content first with `read_file`, then `write_file` the corrected version.

**Rule of thumb**: For critical Java files (controllers, services, entities, mappers), prefer `write_file` over `patch` when making multiple changes. The risk of silent failure + wasted debugging time outweighs the convenience of targeted edits.

### Import Pitfall

If the type parameter is a DTO not previously used in that file, add the import. Common case: `FrontProjectListDTO` imported in `ProjectServiceImpl` but missing from `ProjectService` interface and `FrontProjectController`.

## Full-Stack Feature Development Workflow

When adding a cross-cutting feature (e.g. linking Pipeline to Project), follow this sequence. Each step must pass before moving to the next.

### Step 1: Database Schema Change
```sql
ALTER TABLE pipelines ADD COLUMN project_id bigint DEFAULT NULL AFTER template_id;
ALTER TABLE pipelines ADD KEY idx_p_project (project_id);
```
Verify: `DESCRIBE pipelines;`

### Step 2: Backend Entity + Mapper + DTO + Service
1. Entity — add field: `private Long projectId;`
2. Mapper XML — add to resultMap, Base_Column_List, insert, selectAll (with filter), updateById
3. DTO — add field to CreateRequest and UpdateRequest records
4. Service impl — set field in create and update methods
5. Controller — if update uses a different DTO, pass the new field through the conversion

Verify: `mvn compile -q`

### Step 3: Frontend API Types
Align TypeScript interfaces with backend entity exactly. Do NOT invent fields.

Verify: `npx vue-tsc --noEmit`

### Step 4: Frontend Views
Update table columns, form fields, search filters to match the new types.

Verify: `npm run build`

### Step 5: UI Visibility Check
**Always verify the rendered page shows the changes.** Backend data changes alone are not enough — the user sees the frontend, not the database. Use `browser_navigate` + `browser_vision` to confirm:
- Table columns display the new fields
- Form dialogs include the new inputs
- Data from the API renders correctly in the UI

If the user says "I don't see any changes", the most common causes:
1. Docker container serving stale dist (rebuild image)
2. Changes were in create/edit dialog only, not in the visible table columns
3. New fields have no data yet (empty columns look unchanged)

### DTO Record Constructor Arity Mismatch

When adding fields to Java `record` DTOs, ALL call sites using `new RecordType(...)` must be updated. Unlike regular classes (which can have overloaded constructors or setters), records have exactly one positional constructor whose arity must match exactly.

**Real example**: Added `projectId`, `metaContent`, `metaType`, `extraParams` to `AdminPipelineCreateRequest`. The `AdminPipelineController.update()` method still used the old 8-arg constructor:
```java
// BROKEN — missing new fields:
new AdminPipelineCreateRequest(request.name(), request.type(), request.templateId(),
    request.description(), request.category(),
    request.configJson(), request.dockerImage(), request.timeout())

// FIXED — includes new fields:
new AdminPipelineCreateRequest(request.name(), request.type(), request.templateId(),
    request.projectId(), request.metaContent(), request.metaType(), request.extraParams(),
    request.description(), request.category(),
    request.configJson(), request.dockerImage(), request.timeout())
```

**Compiler error**: `The constructor AdminPipelineDTO.AdminPipelineCreateRequest(String, String, Long, String, String, String, String, Integer) is undefined`

**Fix strategy**: After modifying a record DTO, grep for all `new RecordName(` call sites and update each one. The order of arguments must match the record's field declaration order exactly.

### Pitfall: Router patch silently fails — always verify with grep

The `patch()` tool fails silently on router files just like any other file. Adding a route after an existing route entry requires exact string matching on multi-line YAML-like structures. If the patch returns success but the route wasn't actually added, the page component exists but is unreachable — the user sees no error, just no page.

**Diagnosis**: After adding a route, always verify:
```bash
grep -q "your-new-path" src/router/index.ts && echo "OK" || echo "MISSING"
```

**Fix**: If the route is missing after a patch, use `write_file` to rewrite the entire router file. Read the current content first.

**Real example**: `projects/:id` route patch succeeded (`"success": true`) but the route was never added. The ProjectDetailView.vue component existed and compiled, but navigating to `/projects/10` showed a blank page or redirect. Fixed by rewriting the full router file.

### Pitfall: Adding a FK column requires a visible table column

When adding a foreign key (e.g. `project_id`) to an entity, the table view must show the related entity name. Just adding the field to the create/edit dialog is not enough — the user won't see the relationship. The table needs a column that resolves the FK to a display name (via a lookup list loaded on mount).

```vue
<!-- Pipeline table showing project name from FK -->
<el-table-column label="所属项目" width="120">
  <template #default="{ row }">
    <span v-if="getProjectName(row.projectId)">{{ getProjectName(row.projectId) }}</span>
    <span v-else class="text-muted">-</span>
  </template>
</el-table-column>

<script setup>
const getProjectName = (projectId: number | undefined) => {
  if (!projectId) return ''
  const p = projectList.value.find(p => p.id === projectId)
  return p ? p.name : ''
}
</script>
```

User feedback: "从后台来看,我没看出项目管理部分修改了什么" — the changes were in the dialog only, not in the visible table.

### Frontend Type Drift Pitfall

When the frontend `api/*.ts` type interface has fields that don't exist in the backend entity, the app builds and runs but data silently doesn't flow. Common pattern:

```typescript
// WRONG — invented fields that don't match backend:
export interface Project {
  species: string      // backend has 'organism'
  sampleCount: number  // backend doesn't have this
  type: string         // backend doesn't have this
  status: string       // backend has number (0/1/2)
}

// CORRECT — matches backend entity exactly:
export interface Project {
  organism: string
  genomeVersion: string
  status: number       // 0=draft, 1=active, 2=archived
  isPrivate: boolean
}
```

**Diagnosis**: If the table shows data but columns are empty, check whether the frontend field names match the JSON keys returned by the API. Use browser devtools Network tab to inspect the actual response.

## Project-Level Analysis Workflow

When a platform needs "create analysis from project" (project selects template → inputs data → executes), the architecture is:

### Data Model

Pipeline entity stores both the config AND the input metadata:
```java
private Long projectId;      // FK to projects
private Long templateId;     // FK to workflow_templates
private String metaContent;  // TSV text or server file path
private String metaType;     // "text" | "path"
private String extraParams;  // JSON dot-notation overrides
private String configJson;   // full config from template (copied at creation)
```

### Backend: Create Analysis Endpoint

```java
@PostMapping("/{projectId}/analyses")
public ApiResponse<Pipeline> createAnalysis(@PathVariable Long projectId,
                                            @RequestBody CreateAnalysisRequest request) {
    // 1. Look up workflow template by name
    // 2. Create Pipeline: copy configJson from template, set projectId, meta, etc.
    // 3. Return Pipeline
}
```

The `CreateAnalysisRequest` record:
```java
public record CreateAnalysisRequest(
    String workflowTemplateName,  // lookup key, not ID
    String name,                  // optional, defaults to template name + "-分析"
    String metaContent,           // TSV text or path
    String metaType,              // "text" or "path"
    String extraParams,           // optional JSON overrides
    String description            // optional
) {}
```

### Frontend: Multi-Step Analysis Dialog

Use `el-steps` with 3 steps:
1. **Select template** — radio-button cards from `listTemplates()`
2. **Input meta** — tab switch between "TSV text" (textarea) and "Server path" (input)
3. **Override params** (optional) — JSON editor for dot-notation overrides

The dialog lives in the **project detail page** (`/projects/:id`), not in the pipeline page. The project detail page shows:
- Project info card (name, organism, genome version, status)
- Analyses list (pipelines filtered by projectId)
- "New Analysis" button

### Data Upload in Project Detail

When the project detail page needs file management, add a "数据文件" card between the project info and the analysis list. Use the existing `dataFileApi.ts` functions:

```vue
<!-- Upload button -->
<el-upload :show-file-list="false" :before-upload="handleUpload">
  <el-button type="primary" size="small">上传文件</el-button>
</el-upload>

<!-- Import server files button -->
<el-button size="small" @click="showImportDialog">导入服务器文件</el-button>
```

The upload handler must return `false` to prevent el-upload's default behavior:
```typescript
const handleUpload = async (file: File) => {
  await uploadFile(file, projectId)
  ElMessage.success('上传成功')
  loadFiles()
  return false  // prevent el-upload default
}
```

Import from server uses `importLocalFiles(dirPath, projectId)` — the user enters an absolute path on the server.

**Pitfall**: `DataFile` entity uses `fileName` not `name`, `filePath` not `path`. Frontend templates must use `row.fileName`, not `row.name`.

### Route Config

```typescript
{ path: 'projects/:id', name: 'ProjectDetail',
  component: () => import('@/views/project/ProjectDetailView.vue'),
  meta: { title: '项目详情' } }
```

### Pitfall: PipelineView table needs FK resolution column

When Pipeline gets `projectId`, the PipelineView table must show the project name. Add a column with a lookup function:
```vue
<el-table-column label="所属项目" width="120">
  <template #default="{ row }">
    <span>{{ getProjectName(row.projectId) || '-' }}</span>
  </template>
</el-table-column>
```

Load the lookup list on mount: `listProjects({ page: 1, size: 100 })`.


## Bioplatform Execution Architecture

The Omics workflow engine uses a specific execution chain: meta TSV → MetadataUtils → config template merge → snakemake. When building features around project management or pipeline execution, always reference this architecture. See `references/bioplatform-execution-architecture.md` for the full flow, meta TSV formats, data model hierarchy, and system fields.

### Pitfall: Don't create test data to mask logic problems

When the user points out that backend logic is broken (e.g. "数据从哪里来" / "后台逻辑不对"), **fix the logic first**. Creating test data to make the UI look populated is a distraction — it hides the structural problem. The user sees through it immediately: "没让你造测试数据,而是后台逻辑不对".

Correct response: analyze the actual data flow, identify the broken link, present the architectural gap, then propose a fix.

## Spring Boot ConditionalOnProperty Import

`@ConditionalOnProperty` is in `org.springframework.boot.autoconfigure.condition`, NOT `org.springframework.context.annotation`. The compiler error `cannot find symbol: class ConditionalOnProperty` means the wrong package was used.

```java
// WRONG
import org.springframework.context.annotation.ConditionalOnProperty;

// CORRECT
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
```

This is a common mistake when writing `@ConditionalOnProperty` with a fully-qualified annotation (e.g. `@org.springframework.context.annotation.ConditionalOnProperty(...)`) — the compiler doesn't recognize it.

## StorageStrategy Pattern for Multi-Server Architecture

When a platform needs to support both shared storage (NFS) and distributed storage (files on internal Worker servers), use a strategy interface:

```java
public interface StorageStrategy {
    String getType();
    String store(MultipartFile file, Long projectId, String fileName);
    String storeBytes(byte[] data, Long projectId, String fileName);
    Path resolve(String storagePath);
    void delete(String storagePath);
    boolean exists(String storagePath);
}
```

Two implementations with `@ConditionalOnProperty`:
- `SharedStorageStrategy` — reads/writes to NFS mount path
- `WorkerStorageStrategy` — routes to specific Worker via HTTP, storage path format: `{workerId}:{remotePath}`

Config in `application.yml`:
```yaml
bioplatform:
  storage:
    type: shared  # or "worker"
    shared-path: /data/shared/bioplatform
```

DataFileServiceImpl injects `StorageStrategy` (the interface) — Spring auto-selects the active implementation based on config. All file operations go through the strategy, so switching storage mode requires zero code changes.

### WorkerStorageStrategy Path Format

Store path as `{workerId}:{projectId}/{filename}` (e.g., `worker-abc:3/sample.fastq`). Parse with `indexOf(':')` to split worker ID from remote path. Gateway stores only metadata (DB records); Workers store actual files.

### Worker File Transfer API

Workers expose `/worker/storage/upload`, `/worker/storage/download`, `/worker/storage/delete`, `/worker/storage/exists` endpoints. Files transferred as Base64-encoded JSON payloads. Gateway's WorkerClient adds these methods alongside task execution methods.

## Distributed Worker Architecture

When the platform has internal compute servers that can't be reached from the public internet, use SSH reverse tunnels + Worker pattern:

1. **SSH reverse tunnel**: Internal server connects TO public server: `ssh -N -R 18081:localhost:8081 user@public-ip`
2. **Gateway maps tunnels**: `localhost:18081` on public server = internal Worker
3. **WorkerRegistry**: Tracks Worker health via periodic `/worker/health` checks
4. **TaskScheduler**: Selects Worker (lowest load), submits task, polls status asynchronously
5. **StorageStrategy**: Routes file I/O to the correct Worker

Key files:
- `WorkerRegistry.java` — Worker health tracking, dynamic registration
- `WorkerClient.java` — HTTP client for Worker API calls
- `TaskScheduler.java` — Task dispatch + async status polling
- `bioplatform-worker/` — Standalone Spring Boot app for internal servers

### Worker Health Check

```java
@Scheduled(fixedDelay = 30000)
public void checkAllHealth() {
    for (WorkerInfo info : workers.values()) {
        String response = HttpUtil.get(info.getUrl() + "/worker/health");
        JsonNode node = objectMapper.readTree(response);
        info.setHealthy("UP".equals(node.path("status").asText()));
        info.setCpuCores(node.path("cpuCores").asInt(0));
        info.setFreeMemoryMB(node.path("freeMemoryMB").asLong(0));
    }
}
```

### Task Polling Pattern

After dispatching to Worker, poll status asynchronously with `@Async`:
- Poll every 10 seconds
- Max 3600 polls (1 hour)
- On COMPLETED → update execution status to SUCCESS
- On FAILED → update to FAILED with error log
- On timeout → update to FAILED

## Git Operations: Use the Simplest Tool

**User correction**: When asked to "remove a file from git history", the agent used `git filter-branch` which rewrote ALL history, caused untracked files to disappear, required `--force` push, and confused the user. The correct action was simply `git rm`.

**Rules:**
1. **`git rm` + commit** — remove a tracked file from the repo. This is sufficient 99% of the time.
2. **`git rm --cached`** — untrack a file but keep it on disk (for .gitignore additions).
3. **`git filter-branch` / BFG** — rewrite ALL history to purge sensitive data (passwords, keys). Only use when the file contains secrets that must not exist in any commit.
4. **Never `filter-branch` for normal file deletion.** It rewrites every commit, changes SHAs, breaks `git pull` for collaborators, and requires `--force` push.

Also: when the user says "项目不是博客" (the project is not a blog), don't rename directories to "blog". Use domain-appropriate names like `docs/tech/`.

## Debugging Tips

### MyBatis LIKE in Duplicate Check Causes Data Corruption

When a mapper's `selectAll` uses `LIKE '%name%'` for name matching, and the import logic uses it for duplicate checking, substring matches cause the wrong record to be updated instead of inserting a new one.

**Real example**: Importing "RNAseq" with `LIKE '%RNAseq%'` matched "scRNAseq" and overwrote its config. The log showed "导入模板: RNAseq" but the data went into scRNAseq's row. The insert was never executed.

**Fix**: Use exact match (`= #{name}`) for duplicate-check queries. Keep LIKE only for user-facing search endpoints.

```xml
<!-- WRONG for duplicate checking -->
<if test="name != null and name != ''">
    AND `name` LIKE CONCAT('%', #{name}, '%')
</if>

<!-- CORRECT for duplicate checking -->
<if test="name != null and name != ''">
    AND `name` = #{name}
</if>
```

**Diagnosis**: Check `updated_at` timestamp on suspected records — if it matches the import log time, the update path was taken instead of insert.

### Entity-Mapper Column Alignment Pitfall

When the mapper XML selects a column (e.g. `updated_at`) but the entity class doesn't have the corresponding field (e.g. `updatedAt`), MyBatis throws `ReflectionException: There is no setter for property named 'updatedAt'`. The code compiles fine — the error only appears at runtime when the query executes.

**Real example**: `PipelineExecutionMapper.xml` selected `updated_at` with `property="updatedAt"`, but `PipelineExecution.java` only had `createdAt`, not `updatedAt`. All other entities (Pipeline, Project, etc.) had both fields, so the mapper was copy-pasted correctly — but the entity was incomplete.

**Pattern**: When adding new columns to one entity's mapper, check that ALL entities referenced by that mapper have the matching Java fields. The error only surfaces at runtime, not compile time.

**Fix**: Add the missing field to the entity:
```java
private LocalDateTime createdAt;
private LocalDateTime updatedAt;  // was missing
```

### cat -A Backtick Display Issue
`cat -A` displays backticks as `***`. When inspecting TypeScript template literals like `` `Bearer ${token}` ``, use:
```python
python3 -c "
with open('file.ts') as f:
    lines = f.readlines()
print(repr(lines[N]))  # shows actual content
"
```
Or hex dump: `hexdump -C file.ts | grep -A2 "Authorization"`

## Testing Workflow

- **Test on actual environment** — if the issue is on remote, test on remote, not locally
- **Verify with actual output** — don't claim fix works until you've confirmed the API returns success
- **Verify UI visibility** — after frontend changes, check the rendered page with `browser_vision` to confirm columns/forms/data are visible. Backend changes that don't show up in the UI are invisible to the user.
- **Use logical deduction** — if other APIs work but one doesn't, the problem is specific to that API, not the shared infrastructure
- **Use existing scripts** — `remote_publish.sh` exists for deployment, don't manually compose commands
- **"停止" = stop immediately** — no verification, no rebuild attempts
- **Speed matters** — don't overthink, act. If stuck in a loop, break out
- **Use curl with real tokens** — test APIs directly, don't rely on browser automation for API testing

## LLM Provider Configuration

When integrating LLM providers, keep it simple: hardcoded provider list in frontend, all config in DB, strict validation with clear errors for missing values. See `references/llm-provider-config-pattern.md` for the provider dropdown → auto-fill pattern, anti-patterns (duplicate config sources, fallback chains), and the ConfigView implementation.

## Public vs Admin Frontend

The bioplatform (and similar projects) has TWO separate Vue3 frontends:
- **`bioplatform-admin`** — 后台管理 (admin panel, requires auth)
- **`bioplatform-front`** — 前台 (public-facing, no auth required for most pages)

When the user says "前台" they mean the public frontend. When they say "后台" they mean the admin panel. **Never confuse the two.** If the user reports "前台数据显示不对", check `bioplatform-front`, NOT `bioplatform-admin`.

Each frontend has its own `api/`, `views/`, `components/`, and `router/` directories. Changes to one do NOT affect the other. The admin frontend uses `/api/admin/*` endpoints; the public frontend uses `/api/front/*` endpoints.

**Critical: Separate localStorage.** The two frontends run on different ports and have INDEPENDENT localStorage. Logging in on the admin panel (port 3000) does NOT log you in on the public frontend (port 3001). Each has its own `bio_user` key in localStorage (via pinia-plugin-persistedstate). When debugging "user is logged in but API says 401", verify which frontend's localStorage actually has the token:
```javascript
// In browser console on the correct port:
JSON.parse(localStorage.getItem('bio_user'))?.token
```

**Anonymous user FK constraint pitfall.** When a controller sets `userId = 0L` for anonymous users and then inserts into a table with `FOREIGN KEY (user_id) REFERENCES users(id)`, the insert fails because `users` has no row with `id=0`. Options:
1. Require login (return 400/401) — preferred for features that persist data
2. Insert a system user with `id=0` — only if anonymous persistence is truly needed
3. Make the column nullable and remove the FK — last resort

**Real mistake**: User said "前台的项目没有内容". Agent kept checking `bioplatform-admin` (which showed data correctly) instead of `bioplatform-front` (which had parameter name mismatches). The user had to explicitly ask "你知道什么是前台吗" and "你老是查看后台干啥".

### Frontend Parameter Name Alignment

When the frontend API sends params that don't match the backend `@RequestParam` names, the backend uses defaults (usually page=1, size=10) — which may return data but not what the user expects, or return empty if the default page is wrong.

**Real example**: Frontend sent `{ pageNum: 1, pageSize: 6 }` but backend expected `page` and `size`. The backend used defaults (page=1, size=10) which happened to work, but the frontend's pagination was disconnected from the actual request.

**Always check**: `@RequestParam(defaultValue = "1") int page` — the param name in the annotation MUST match what the frontend sends.

### Pitfall: Hardcoded Stats and Categories

Homepage stats (project count, pipeline count) and category lists should NEVER be hardcoded. They go stale immediately and the user notices.

**Wrong** (hardcoded):
```html
<span class="stat-number">100+</span>
<span class="stat-label">公开项目</span>
```

**Correct** (from API):
```typescript
const [projRes, pipeRes] = await Promise.all([
  listPublicProjects({ page: 1, size: 1 }),
  listPipelines({ page: 1, size: 1 })
])
projectCount.value = projRes.total
pipelineCount.value = pipeRes.total
```

For categories, the backend should query `SELECT DISTINCT category FROM pipelines WHERE category IS NOT NULL` — not return a hardcoded English list that doesn't match the Chinese categories in the database.

### Pitfall: Frontend Type Interface Must Match Backend Entity Exactly

When the frontend TypeScript interface has fields that don't exist in the backend entity, the app builds and runs but data silently doesn't flow. Columns appear empty.

**Checklist after changing a backend entity**:
1. Update the frontend `api/*.ts` interface to match
2. Update ALL components that reference the interface fields
3. If the backend field is a number (e.g. `status: 0/1/2`), the frontend must use `number` not `string`
4. If a field was removed from the backend (e.g. `sampleCount`), remove it from the frontend interface AND all components

**Real example**: Frontend `Project` interface had `status: string` with values like `'active'`, `'archived'` — but backend returns `status: number` (0/1/2). The status column showed the raw number instead of labels.

## README Security

Never include server IPs, SSH ports, deployment scripts, or credentials in public README.
Don't list gitignored directories in the project structure — they don't exist in the repo.

## Shell Config Anti-Pattern

When building admin system config pages, avoid creating form fields that have no corresponding database records. The ConfigView.vue may render nicely, but if the backend `system_configs` table doesn't have the matching keys, the config is a "shell" — it looks real but does nothing.

### Symptoms

1. Config page has tabs (基础配置, 安全配置, 通知配置, etc.) with many form fields
2. Frontend initializes reactive objects with hardcoded defaults: `const basicConfig = reactive({ adminEmail: 'admin@example.com', ... })`
3. `loadConfigs()` reads from API but the keys don't match — the `else` branch silently falls through
4. Save sends all keys to the API, but the backend either ignores unknown keys or stores them without any consumer
5. Frontend features (like footer contact email) never read these configs

### Real Example (bioplatform)

ConfigView.vue had 4 config tabs with ~20 form fields. Database `system_configs` table had only 5 rows: `site_name`, `llm_api_key`, `llm_model`, `llm_base_url`, `upload_max_size`. The "管理员邮箱", "Token过期时间", "SMTP服务器" etc. were all frontend-only reactive variables with hardcoded defaults.

The save function sent keys like `basic.adminEmail`, `security.tokenExpireMinutes` to the API — which stored them — but NO code anywhere read them back. The frontend footer showed a hardcoded email, not the configured one.

### Prevention Rules

1. **Don't create config UI for features that don't exist.** If the footer doesn't read `basic.adminEmail`, don't create the form field.
2. **Match config keys end-to-end.** For each form field: does the backend store it? Does any code consume it? If either answer is no, remove the field.
3. **Use a single config namespace.** Mixing `basic.platformName` (dot-separated) with `llm_api_key` (underscore) creates two parsing paths in `loadConfigs()`. Pick one convention.
4. **Audit after building.** After adding config tabs, verify each key exists in the database AND has a consumer (frontend component or backend service that reads it).
5. **New config keys need seed data AND consumer.** When adding `site_contact_email`, `site_github_url`, `site_description` to the config page, also: (a) add INSERT seed SQL, (b) create the public API endpoint that reads them, (c) wire the frontend footer/about page to call that endpoint. If any step is missing, the config is dead.

### Footer Dead Links

Frontend footer sections with `href="#"` links (使用文档, 常见问题, 意见反馈) are placeholders that confuse users. Either implement the feature or remove the link. A footer with 3 dead links looks like an abandoned project.

**Rule**: Footer links must resolve to real pages. If the feature isn't built, don't show the link. Users will click them and get confused when nothing happens.

## WebSocket Customer Service Chat Pattern

When the platform needs "在线反馈" (online feedback/support), don't redirect to another page or use a simple form. Users expect a **floating chat widget** (like Intercom/Tawk.to) that works on every page.

**User correction**: Initial proposal was to redirect "在线反馈" to the AI agent page. User explicitly said: "在线反馈需要采用类似点击能够展示客户对话框那种,采用websocket,类似于聊天室" — they want a real-time chat dialog, not a page redirect.

### Architecture

- **Backend**: Spring WebSocket handler at `/ws/feedback`
- **Frontend (user side)**: Floating bubble (bottom-right) → opens chat drawer
- **Frontend (admin side)**: Feedback management page with session list + real-time reply
- **Persistence**: `feedback_sessions` + `feedback_messages` tables

### Backend: WebSocket Handler

Spring Boot already has `spring-boot-starter-websocket` dependency. The handler manages two groups:

```java
@Component
public class FeedbackWebSocketHandler extends TextWebSocketHandler {
    // User sessions: Map<userId, WebSocketSession>
    private final Map<Long, WebSocketSession> userSessions = new ConcurrentHashMap<>();
    // Admin sessions (can see all conversations)
    private final Set<WebSocketSession> adminSessions = ConcurrentHashMap.newKeySet();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        // Extract JWT from query param: ws://host/ws/feedback?token=JWT
        String token = extractTokenFromQuery(session.getUri().getQuery());
        // Validate with JwtTokenProviderUtil
        Long userId = jwtTokenProviderUtil.getUserIdFromToken(token);
        String role = getUserRole(userId);
        if ("admin".equals(role)) {
            adminSessions.add(session);
        } else {
            userSessions.put(userId, session);
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        // Protocol: { "type": "message", "sessionId": 1, "content": "..." }
        // 1. Persist to feedback_messages
        // 2. Forward to recipient (admin→user or user→admin)
        // 3. Broadcast to all admin sessions if new session created
    }
}
```

### Backend: Registration

```java
// WebMvcConfig implements WebSocketConfigurer
@Override
public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
    registry.addHandler(feedbackWebSocketHandler, "/ws/feedback")
            .setAllowedOrigins("*");
}
```

SecurityConfig already whitelists `/ws/**` — no changes needed.

### Database Tables

```sql
CREATE TABLE `feedback_sessions` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT DEFAULT NULL,
    `user_name` VARCHAR(64) DEFAULT '匿名用户',
    `status` TINYINT NOT NULL DEFAULT 0 COMMENT '0=open, 1=closed',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    INDEX `idx_fs_user` (`user_id`),
    INDEX `idx_fs_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `feedback_messages` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `session_id` BIGINT NOT NULL,
    `sender_type` VARCHAR(16) NOT NULL COMMENT 'user/admin/system',
    `sender_name` VARCHAR(64) DEFAULT NULL,
    `content` TEXT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    INDEX `idx_fm_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Frontend: Floating Chat Widget Component

`FeedbackChat.vue` — a fixed-position component placed in `MainLayout.vue`:

```vue
<template>
  <!-- Floating bubble -->
  <div class="feedback-chat">
    <div class="chat-bubble" @click="toggleChat" :class="{ open: isOpen }">
      <el-icon :size="24"><ChatDotRound /></el-icon>
      <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount }}</span>
    </div>

    <!-- Chat drawer (slides up from bubble) -->
    <transition name="slide-up">
      <div v-if="isOpen" class="chat-drawer">
        <div class="chat-header">
          <span>在线客服</span>
          <el-icon @click="isOpen = false"><Close /></el-icon>
        </div>
        <div class="chat-messages" ref="messagesRef">
          <div v-for="msg in messages" :key="msg.id" class="msg-item" :class="msg.senderType">
            <div class="msg-content">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.createdAt }}</div>
          </div>
        </div>
        <div class="chat-input">
          <el-input v-model="inputText" @keydown.enter="sendMessage" placeholder="输入消息..." />
          <el-button type="primary" @click="sendMessage">发送</el-button>
        </div>
      </div>
    </transition>
  </div>
</template>
```

CSS: Fixed position bottom-right (right: 24px, bottom: 24px). Chat drawer: 360px wide, 500px tall, white background, rounded corners, shadow.

### Frontend: WebSocket Connection

```typescript
const ws = ref<WebSocket | null>(null)

function connectWs() {
  const token = getStoredToken() // from localStorage bio_user
  if (!token) return // not logged in

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws.value = new WebSocket(`${protocol}//${location.host}/ws/feedback?token=${token}`)

  ws.value.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (data.type === 'message') {
      messages.value.push(data)
      if (!isOpen.value) unreadCount.value++
      scrollToBottom()
    }
  }

  ws.value.onclose = () => {
    // Auto-reconnect after 3 seconds
    setTimeout(connectWs, 3000)
  }
}
```

### Pitfalls

1. **JWT auth for WebSocket**: WebSocket can't use Authorization header. Pass token as query param: `ws://host/ws/feedback?token=JWT`. Validate in `afterConnectionEstablished`.
2. **Reconnection death spiral**: Never use immediate reconnect (delay=0) in `ws.onclose`. Always use backoff with max retry count. See `references/websocket-pitfalls.md` for complete patterns.

2. **Heartbeat keepalive**: WebSocket connections are silently dropped by proxies, load balancers, and NAT gateways after 30-60s of inactivity. The connection appears OPEN but messages don't arrive. Add a client-side ping every 25 seconds, and a server-side pong response:

   ```typescript
   // Frontend: start heartbeat on ws.onopen, clear on ws.onclose
   let heartbeatTimer: ReturnType<typeof setInterval> | null = null

   ws.onopen = () => {
     wsConnected.value = true
     reconnectDelay = 1000
     heartbeatTimer = setInterval(() => {
       if (ws && ws.readyState === WebSocket.OPEN) {
         ws.send(JSON.stringify({ type: 'ping' }))
       }
     }, 25000)
   }

   ws.onclose = (e) => {
     wsConnected.value = false
     ws = null
     if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
     if (e.code !== 1000) scheduleReconnect(true)  // immediate
   }
   ```

   ```java
   // Backend: respond to ping in handleTextMessage
   if ("ping".equals(type)) {
       session.sendMessage(new TextMessage("{\"type\":\"pong\"}"));
       return;
   }
   ```

   **Why 25 seconds**: Most proxies/NATs have a 60-second idle timeout. 25s ensures activity well within that window. Clear the timer on close to prevent leaked intervals.

3. **Reconnection — NEVER use delay=0 (death spiral)**: WebSocket connections drop on network issues. The initial approach of `scheduleReconnect(true)` with `delay=0` creates an **infinite tight loop**: `onclose → reconnect(delay=0) → fail → onclose → reconnect(delay=0) → ...` — this freezes the browser and kills the **entire admin page** (not just the chat widget). The `reconnectDelay` variable never increases when `immediate=true`, so backoff is bypassed. This was the #1 production bug in bioplatform's feedback module — user reported "后台界面加载很久了,加载不出来" and "用户反馈模块存在莫名其妙的卡点,会导致整个后台卡死,然后白屏".

   **Recommended approach — NO auto-reconnect, manual button only**:

   After multiple iterations, the cleanest solution removes auto-reconnect entirely. Show connection status + a "重新连接" button. This eliminates ALL possibility of death spirals, resource exhaustion, or browser freezes:

   ```typescript
   let ws: WebSocket | null = null
   let heartbeatTimer: ReturnType<typeof setInterval> | null = null

   ws.onopen = () => {
     wsConnected.value = true
     if (heartbeatTimer) clearInterval(heartbeatTimer)
     heartbeatTimer = setInterval(() => {
       if (ws?.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
     }, 25000)
   }

   ws.onclose = () => {
     wsConnected.value = false
     ws = null
     if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
     // NO auto-reconnect — user clicks button to reconnect
   }

   function doConnect() {
     if (ws) { ws.onclose = null; ws.close(); ws = null }
     // ... create new WebSocket
   }
   ```

   Template shows status + reconnect button when disconnected:
   ```vue
   <div v-if="!wsConnected" class="reconnect-bar">
     <span>连接已断开</span>
     <el-button size="small" type="primary" link @click="doConnect">重新连接</el-button>
   </div>
   <el-input :disabled="!wsConnected" placeholder="请先连接" />
   ```

   **Why this is better than auto-reconnect with backoff**: Even with exponential backoff + max retries, the reconnect logic adds complexity and edge cases (timer leaks, counter resets, concurrent reconnect attempts). A manual button is simpler, more honest about connection state, and never causes performance issues. For customer service chat, a 1-second delay to click "reconnect" is acceptable.

   Show connection status in the chat header (green dot = connected, red = disconnected) so the user knows whether sending will work.

3. **Session persistence**: When the user refreshes the page, the WebSocket reconnects but the chat history should persist. Use REST API (`GET /api/front/feedback/messages?sessionId=X`) to load history on drawer open, WebSocket only for real-time new messages.

4. **Admin must be online**: If no admin WebSocket session is connected, user messages should still be persisted (so admin can see them later). The handler should check `adminSessions.isEmpty()` before forwarding.

5. **Unread badge**: Track unread messages when chat drawer is closed. Clear on open.

6. **Vite WebSocket proxy**: The Vite dev server proxy only handles HTTP by default. WebSocket endpoints need a separate proxy entry with `ws: true`:
   ```typescript
   // vite.config.ts
   server: {
     proxy: {
       '/api': { target: 'http://localhost:8080', changeOrigin: true },
       '/ws':  { target: 'ws://localhost:8080', ws: true, changeOrigin: true },
     }
   }
   ```
   Without this, WebSocket connections in dev mode fail silently (the proxy forwards the HTTP upgrade but not the WS frames). In production (Docker nginx), use `proxy_pass` with the `Upgrade` headers instead.

7. **`defineExpose` must call init logic**: When a parent component calls `ref.openChat()` via `defineExpose`, the exposed function must NOT just set `chatVisible = true`. It must also initialize the WebSocket connection and load history. Otherwise the chat window opens but `ws` is null → user types but send silently does nothing.

   ```typescript
   // WRONG — window opens but WS never connects
   defineExpose({ openChat: () => { chatVisible.value = true } })

   // CORRECT — also initialize connection
   function openChat() {
     chatVisible.value = true
     unreadCount.value = 0
     nextTick(() => { ensureConnected() })
   }
   defineExpose({ openChat })
   ```

8. **Don't disable input on `connecting` state**: Using a `connecting` ref to disable BOTH textarea AND send button breaks UX. WebSocket connection is async — `connecting` is set `false` at end of `initChat()`, but `ws.readyState` is still `CONNECTING` (not `OPEN`). User can type but clicking send silently does nothing.

   **Fix**: Track `wsConnected` separately (set in `ws.onopen`/`ws.onclose`). Never disable the textarea. Only show connection status indicator. On send, if WS not open, attempt reconnect instead of silently returning.

9. **`sendMessage` must not silently return**: When `ws.readyState !== WebSocket.OPEN`, returning silently gives zero feedback. Instead, attempt reconnect. The user said "不行" (doesn't work) because send silently did nothing:

   ```typescript
   function sendMessage() {
     const content = inputText.value.trim()
     if (!content) return
     if (!ws || ws.readyState !== WebSocket.OPEN) {
       connectWebSocket()  // attempt reconnect
       return              // message stays in input, user can retry
     }
     // ... send and clear input
   }
   ```

10. **WebSocket handler `handleTextMessage` needs try-catch**: If JSON parsing fails (malformed payload), the exception propagates and Spring closes the WebSocket connection. Wrap the entire handler:

    ```java
    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        try {
            Map<String, Object> data = objectMapper.readValue(message.getPayload(), Map.class);
            // ... process
        } catch (Exception e) {
            log.error("处理WebSocket消息异常: {}", e.getMessage(), e);
            // Connection stays open — don't rethrow
        }
    }
    ```

11. **Admin feedback page needs the same fixes as user chat**: When implementing both sides of a WebSocket chat (user floating widget + admin management page), ALL the same pitfalls apply to both sides. Don't fix one side and leave the other with the original broken patterns. The admin FeedbackView had the exact same bugs: missing `wsConnected` tracking, silent `sendMessage` return, no reconnect cleanup on unmount.

12. **`handleKeydown` type must be `Event | KeyboardEvent`**: Element Plus `el-input` `@keydown` event passes `Event | KeyboardEvent`, not just `KeyboardEvent`. If the handler signature uses only `KeyboardEvent`, TypeScript build fails:

    ```typescript
    // WRONG — TypeScript error
    function handleKeydown(e: KeyboardEvent) { ... }

    // CORRECT — cast inside
    function handleKeydown(e: Event | KeyboardEvent) {
      const keyEvent = e as KeyboardEvent
      if (keyEvent.key === 'Enter' && !keyEvent.shiftKey) {
        keyEvent.preventDefault()
        sendMessage()
      }
    }
    ```

11. **`Map.of()` null safety — use `HashMap` instead**: `Map.of()` throws NPE on null values and doesn't allow null keys. In WebSocket handlers where message fields might be null (createdAt, userName, sessionId), always use `HashMap`:

    ```java
    // WRONG — NPE if any value is null, and Map.of() doesn't tolerate it
    Map.of("createdAt", msg.getCreatedAt() != null ? msg.getCreatedAt().toString() : "")

    // CORRECT — HashMap tolerates null values
    Map<String, Object> msgData = new HashMap<>();
    msgData.put("type", "message");
    msgData.put("sessionId", sessionId);
    msgData.put("createdAt", msg.getCreatedAt() != null ? msg.getCreatedAt().toString() : "");
    String msgJson = objectMapper.writeValueAsString(msgData);
    ```

    Also guard Integer comparisons: `if (fbSession.getStatus() != null && fbSession.getStatus() == 0)` — auto-unboxing null Integer throws NPE.

12. **Database DDL must be executed against running DB**: Adding CREATE TABLE to `bioplatform.sql` only affects fresh `docker-compose up`. For running Docker MySQL, execute manually:

    ```bash
    docker exec -i bioplatform-mysql mysql -uroot -pPASSWORD dbname < /tmp/init.sql
    # Verify:
    docker exec bioplatform-mysql mysql -uroot -pPASSWORD dbname -e "SHOW TABLES LIKE 'feedback%';"
    ```

### Public Site Config Endpoint

When the frontend footer needs to display configurable info (email, GitHub URL, platform description), create a dedicated public endpoint that returns ONLY non-sensitive configs:

```java
@GetMapping("/api/front/site-config")
public ApiResponse<Map<String, String>> siteConfig() {
    Map<String, String> config = new HashMap<>();
    config.put("siteName", systemService.getConfigValue("site_name"));
    config.put("siteDescription", systemService.getConfigValue("site_description"));
    config.put("contactEmail", systemService.getConfigValue("site_contact_email"));
    config.put("githubUrl", systemService.getConfigValue("site_github_url"));
    return ApiResponse.success(config);
}
```

**Never expose** `llm_api_key` or other secrets through this endpoint. Only include configs that are safe for public viewing.

Config keys use `site_` prefix in the database to distinguish from internal configs.

## Cross-Component Communication via Custom Events

When sibling components in different layout regions need to trigger each other (e.g., a "意见反馈" link in the footer needs to open a FeedbackChat widget floating outside the footer), Vue 3 provides no direct prop/event path. Use `window.dispatchEvent(new CustomEvent(...))` as a decoupled bridge.

### Pattern

**Sender** (AboutView, footer link, any component):
```vue
<script setup>
function openFeedback() {
  window.dispatchEvent(new CustomEvent('open-feedback-chat'))
}
</script>
<template>
  <a @click="openFeedback">意见反馈</a>
</template>
```

**Receiver** (MainLayout, the component that owns the target widget):
```vue
<script setup>
import FeedbackChat from '@/components/FeedbackChat.vue'
const feedbackChatRef = ref()

function openFeedback() {
  if (feedbackChatRef.value) feedbackChatRef.value.openChat()
}

onMounted(() => {
  window.addEventListener('open-feedback-chat', openFeedback)
})
onUnmounted(() => {
  window.removeEventListener('open-feedback-chat', openFeedback)
})
</script>
<template>
  <FeedbackChat ref="feedbackChatRef" />
</template>
```

**Target component** (FeedbackChat) exposes methods via `defineExpose`. The exposed function must call init logic (WebSocket connect, history load), NOT just toggle visibility — otherwise the chat opens but can't send messages:
```vue
<script setup>
function openChat() {
  chatVisible.value = true
  unreadCount.value = 0
  nextTick(() => { ensureConnected() })
}
defineExpose({ openChat })
</script>
```

### When to use
- Footer links triggering floating widgets (chat, feedback, help)
- Any "open X from Y" where X and Y are not parent/child
- Login modal triggered from anywhere (bioplatform uses `show-login-modal` event)

### When NOT to use
- Parent-child communication (use props/events)
- Frequent data passing (use Pinia store instead)
- More than 2-3 events (consider a store)

## Design Principles (User-Corrected)

### No Duplicate Config Sources

When a setting can be stored in multiple places (JSON file + database, yml + database), **pick ONE source of truth**. Having both causes confusion about which one is authoritative and requires sync logic.

**User correction**: "不要做重复的配置,比如json和数据库". The LLM provider config initially used both a `llm-providers.json` file AND the `system_configs` database table. User demanded consolidation to database-only.

### No Silent Fallback Chains

When a required config is missing, **throw a clear error** telling the user what to configure. Don't silently fall back to defaults across 3-4 layers — it makes debugging impossible.

**User correction**: "不要大量fall back,不好排查错误". The `callLlmApi` method initially had: provider→baseUrl→model fallback across JSON file, database, and hardcoded defaults. Simplified to: read 3 values from DB, throw specific error for each missing one.

### Keep UI Config Simple

Admin config pages should feel like Hermes config — select provider, enter key, done. Don't over-engineer with dynamic provider loading from APIs when a hardcoded dropdown works.

## Sensitive Config Encryption

When the admin system config page manages API keys or secrets, encrypt at rest with AES-GCM. See `references/sensitive-config-encryption.md` for the full pattern: AesEncryptUtil, service layer encrypt/mask/decrypt rules, frontend ConfigView password input pattern, client-side encryption before HTTP send, and the pitfall of reading encrypted values directly from mapper instead of service.

### Frontend New File HMR Limitation

Vite HMR may not pick up newly created files (like a new `crypto.ts` utility). After adding new files to a Vite project, the user must hard refresh (Ctrl+Shift+R) or restart the dev server. HMR works for modifications to existing files but not always for new file additions.
