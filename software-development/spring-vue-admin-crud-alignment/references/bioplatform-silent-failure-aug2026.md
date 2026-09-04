# Bioplatform Frontend Silent Failures — August 2026

## Symptom chain

1. "公开项目" page shows no projects, "分析流程" page shows no pipelines
2. AI assistant returns "消息内容不能为空" even when user sends a message
3. AI assistant returns "请先登录后再使用 AI 助手" despite user being logged in
4. Login button works but dialog doesn't close after successful login
5. LLM API returns 401 → then 400 after key fix
6. "前端怎么传送的还是明文" — API key still plaintext in network tab

## Root causes found

### 1. Axios double-unwrap (empty lists)
- Response interceptor returns `Promise.resolve(response.data.result)` for code 200
- `request()` helper does `return res.data as T` — but `res` is already the unwrapped result, not AxiosResponse
- `res.data` = undefined → all API calls return undefined → lists empty
- Fix: `return res as any` (matching admin pattern)

### 2. Frontend/backend field name mismatch (AI chat NPE)
- Frontend sends `{ message: "..." }` (AgentView.vue line 120)
- Backend reads `params.get("content")` → null → NPE on `.toString()`
- Fix: backend reads both: `Object val = params.get("content"); if (val == null) val = params.get("message");`

### 3. Token refresh clearing the token
- Two bugs in proactive + reactive refresh:
  - Field name: sends `{token: ...}` but backend expects `{refreshToken: ...}`
  - Response access: `refreshRes.data.result` → undefined (interceptor already unwraps, response is Map `{accessToken, refreshToken}`)
  - `userStore.token = undefined` → Pinia persist writes undefined to localStorage → token gone
- Fix: `{refreshToken: currentToken}`, `refreshRes?.accessToken`

### 4. Anonymous user FK constraint
- `userId=0L` for anonymous users → no user with id=0 in `users` table → FK violation
- Fix: return 400 "请先登录" instead of using 0L

### 5. Hardcoded model name "gpt-4" causing 400
- `FrontAgentController` creates conversations with `createConversation(userId, null, "新对话", "gpt-4")`
- `callLlmApi` uses this model name to override system config
- DeepSeek/MiMo APIs don't recognize "gpt-4" → 400 Bad Request
- Fix: pass `null` for model name, let system config determine it

### 6. API key plaintext leak in secondary code path
- `handleSave` correctly encrypts API key before sending
- BUT `testLlmConnection` ("测试连接" button) was NOT patched — still sent `llmConfig.apiKey` as plaintext
- User tested with "测试连接", saw plaintext in network tab, reported "根本没有变化"
- Lesson: after fixing one code path, `grep -rn 'field_name' src/` to find ALL places that send the value

### 7. LLM config over-engineering (3 iterations)
- Iteration 1: JSON file + LlmProviderConfig class + database → user said "不要重复的配置"
- Iteration 2: hardcoded model lists in frontend → user said "模型都不全"
- Iteration 3 (final): provider list hardcoded (name + base_url only), models fetched via `/v1/models` API
- User frustration: "不要大量fallback, 不好排查错误" → strict errors, no fallback chains

### 8. AES encryption for sensitive config
- User demanded end-to-end encryption, not just response masking
- Frontend: `crypto.ts` using Web Crypto API (AES-256-GCM)
- Backend: `AesEncryptUtil.java` with `ENC:` prefix detection
- `updateConfig()` MUST decrypt first, then check for `***` — the encrypted form `ENC:Base64...` never contains `***`, so checking the raw value is useless. This caused masked values to be encrypted and stored, leading to 401 on LLM calls.
- `getConfigValue()` decrypts for internal use
- `getAllConfigs()` returns masked display value
- `callLlmApi()` checks `apiKey.contains("***")` as final defense — throws clear error "LLM API Key 为遮蔽值"

## Key lessons

- **Always check ALL code paths** — fixing `handleSave` but missing `testLlmConnection` wasted a debugging cycle
- **Don't over-engineer** — user wants simple, single-source-of-truth solutions
- **Don't use fallback chains** — strict errors are easier to debug
- **Dynamic > hardcoded** — fetch model lists from provider API, don't maintain static lists
- **User frustration is a signal** — "能不能动动脑子" means stop and re-examine, don't repeat the same explanation

## Files changed

- `bioplatform-front/src/utils/http/axios.ts` — request() return, token refresh
- `bioplatform-front/src/api/agentApi.ts` — silent flag on chat
- `bioplatform-front/src/views/agent/AgentView.vue` — login prompt in catch
- `bioplatform-springboot/.../FrontAgentController.java` — null check, field fallback, 401 for anon, null model name
- `bioplatform-springboot/.../AgentServiceImpl.java` — use SystemService.getConfigValue(), strict errors
- `bioplatform-springboot/.../SystemServiceImpl.java` — AES encrypt/decrypt/mask, getConfigValue
- `bioplatform-springboot/.../AesEncryptUtil.java` — new AES utility
- `bioplatform-springboot/.../SystemService.java` — getConfigValue interface
- `bioplatform-springboot/.../AdminSystemController.java` — fetch-models endpoint with isChatModel filter
- `bioplatform-admin/src/utils/crypto.ts` — new frontend AES utility
- `bioplatform-admin/src/views/system/config/ConfigView.vue` — LLM config tab with dynamic model fetching
- `bioplatform-admin/src/api/systemApi.ts` — fetchLlmModels API
