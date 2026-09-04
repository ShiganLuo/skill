# Bioplatform AI Assistant Integration Patterns

## Entity object returned directly — field name mismatch

Backend `FrontAgentController.chat()` returns `ApiResponse<AgentMessage>` where `AgentMessage` has field `content`. After axios interceptor unwraps, frontend gets the `AgentMessage` object directly.

**Wrong**: `data.reply` (field doesn't exist on AgentMessage)
**Correct**: `data.content`

Same issue in admin `AgentView.vue`: `response.message` doesn't exist. Use `response.content || response.message || response`.

**Rule**: When backend returns an entity object (not a DTO), always read the Java entity fields, not assumed field names. Check `AgentMessage.java` for actual field names.

## Conversation creation — don't hardcode model name

```java
// WRONG — hardcodes gpt-4, fails on DeepSeek/MiMo with HTTP 400
agentService.createConversation(userId, null, "新对话", "gpt-4");

// CORRECT — use null, let callLlmApi resolve from DB config
agentService.createConversation(userId, null, "新对话", null);
```

`callLlmApi` reads model from DB (`llm_model`). If `modelName` is non-null, it overrides DB config. Hardcoding `gpt-4` means the system always tries to use gpt-4 regardless of what's configured.

## LLM config — three-field validation, no fallback chains

```java
String apiKey = systemService.getConfigValue("llm_api_key");
String model = systemService.getConfigValue("llm_model");
String baseUrl = systemService.getConfigValue("llm_base_url");

if (apiKey == null || apiKey.isBlank()) throw new RuntimeException("LLM API Key 未配置");
if (apiKey.contains("***")) throw new RuntimeException("LLM API Key 为遮蔽值");
if (baseUrl == null || baseUrl.isBlank()) throw new RuntimeException("LLM Base URL 未配置");
if (model == null || model.isBlank()) throw new RuntimeException("LLM 模型名称未配置");
```

No fallback chains. Each missing field gets a clear, specific error message telling the user exactly which field to fix.

## Dynamic model fetching via /v1/models

Don't hardcode model lists. Call `GET {baseUrl}/models` with Bearer auth:

```java
String url = baseUrl.replaceAll("/+$", "") + "/models";
Request request = new Request.Builder()
    .url(url)
    .addHeader("Authorization", "Bearer " + apiKey)
    .get().build();
```

Response: `{data: [{id: "model-name", ...}, ...]}`. Extract `data[].id`.

Frontend: `el-select` with `filterable` + `allow-create` — supports both dropdown selection and manual input.

## "获取模型" = connection test

If `/v1/models` returns successfully, the API key, base URL, and network are all valid. A separate "测试连接" button is redundant. Remove it.

## Provider switch — friendly prompts, not force-clear

When user switches LLM provider in admin config:
- Auto-fill base_url from provider definition
- Clear model list (different providers have different models)
- Do NOT clear API key (user may reuse keys across providers)
- Show hint: "切换提供商后请确认 API Key 是否匹配"
- If user saves without changing key and it's a masked value, show warning

## Conversation history — load on mount

Add API endpoints:
- `GET /api/front/agent/conversations` — list user's conversations
- `GET /api/front/agent/conversations/{id}/messages` — get messages

Frontend `onMounted`: fetch latest conversation → load its messages → render in chat area.

## AES encryption for API keys — full chain

See `references/e2e-sensitive-config-encryption.md` for the complete pattern.

Key points specific to LLM config:
1. Frontend encrypts with Web Crypto API before sending (`ENC:Base64...`)
2. Backend `updateConfig` decrypts first, checks for `***`, then stores (re-encrypts if plaintext, stores directly if already `ENC:`)
3. Backend `getConfigValue` decrypts for internal use
4. Backend `getAllConfigs` masks for display
5. Frontend `apiKeyDirty` flag prevents sending unmodified masked values
6. Three-layer defense: frontend checks `***` before encrypt, backend checks decrypted value for `***` in both `updateConfig` and `callLlmApi`

## Admin vs Front controller behavior drift

When admin and front controllers implement the same conceptual endpoint (e.g. chat), they must handle optional fields consistently. If the front controller auto-creates resources when an ID is missing, the admin controller should too — or vice versa.

**Real incident**: `FrontAgentController.chat()` auto-created a conversation when `conversationId` was null. `AdminAgentController.chat()` returned 400. Admin frontend's `createConversation()` only cleared local state (`currentConversationId = ''`), so the first message sent `conversationId: ""` → NFE on the backend.

**Fix pattern**: When a controller uses `@RequestBody Map<String, Object>`, always handle optional Long fields with null-and-blank check:
```java
Long conversationId = null;
Object convIdObj = params.get("conversationId");
if (convIdObj != null && !convIdObj.toString().isBlank()) {
    conversationId = Long.valueOf(convIdObj.toString());
}
if (conversationId == null) {
    // auto-create resource, matching front controller behavior
    AgentConversation conv = agentService.createConversation(userId, null, "新对话", null);
    conversationId = conv.getId();
}
```

**Rule**: After adding a new controller endpoint, compare its behavior with the equivalent endpoint in the other frontend (admin vs front). Missing fields, error responses, and auto-creation logic should be symmetric unless there's a deliberate reason to differ.
