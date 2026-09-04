# LLM Provider Configuration Pattern

When integrating LLM providers, keep it simple: single source of truth (database only), strict errors, dynamic model fetching.

## Anti-patterns (learned the hard way)

1. **Don't create JSON config files AND database config** — duplicate sources drift. User will ask "why two places?"
2. **Don't use fallback chains** — `if X null try Y, if Y null try Z` makes errors invisible. If a config is missing, throw a clear error telling the user what to set.
3. **Don't hardcode model lists** — providers update models frequently. Use `/v1/models` API to fetch dynamically.
4. **Don't hardcode model names in controller code** — `"gpt-4"` causes 400 on DeepSeek/MiMo.

## Architecture (final)

```
Frontend ConfigView.vue
  ├── Provider dropdown (hardcoded: just name + base_url, NO models)
  ├── "获取模型" button → POST /api/admin/system/llm/fetch-models
  ├── Model dropdown (filterable + allow-create, populated from API)
  ├── API Key (password input, AES encrypted before send)
  └── Base URL (auto-filled from provider, editable)
       ↓
system_configs table (single source of truth)
  ├── llm_provider (e.g. "deepseek")
  ├── llm_api_key (AES encrypted, ENC: prefix)
  ├── llm_model (e.g. "deepseek-chat")
  └── llm_base_url (e.g. "https://api.deepseek.com/v1")
       ↓
AgentServiceImpl.callLlmApi()
  ├── Read apiKey, model, baseUrl from DB
  ├── If any is blank → throw RuntimeException with specific field name
  └── Use baseUrl directly (no resolution, no fallback)
```

## Frontend: provider list (hardcoded, no API call)

```typescript
const llmProviders = [
  { key: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1' },
  { key: 'mimo', name: 'Xiaomi MiMo', baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1' },
  { key: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { key: 'qwen', name: '通义千问', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { key: 'zhipu', name: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  { key: 'custom', name: '自定义', baseUrl: '' },
]
```

Selecting a provider auto-fills baseUrl. Model list is empty until user clicks "获取模型".

## Backend: fetch-models endpoint

```java
@PostMapping("/llm/fetch-models")
public ApiResponse<List<String>> fetchModels(@RequestBody Map<String, String> params) {
    String baseUrl = params.get("baseUrl");
    String apiKey = params.get("apiKey");
    // If apiKey is masked (***  or ENC:), read from DB
    if (apiKey.contains("***") || AesEncryptUtil.isEncrypted(apiKey)) {
        apiKey = systemService.getConfigValue("llm_api_key");
    }
    // Call GET {baseUrl}/models with Bearer auth
    // Filter response: only keep chat models (exclude embedding/tts/whisper/dall-e/etc.)
    // Return sorted model ID list
}
```

Filter out non-chat models with `isChatModel()` — exclude: embedding, embed, tts, whisper, dall-e, image, audio, speech, moderation, instruct, babbage, davinci, ada, curie.

## Backend: callLlmApi (strict, no fallback)

```java
String apiKey = systemService.getConfigValue("llm_api_key");
String model = systemService.getConfigValue("llm_model");
String baseUrl = systemService.getConfigValue("llm_base_url");

if (apiKey == null || apiKey.isBlank()) throw new RuntimeException("LLM API Key 未配置");
if (baseUrl == null || baseUrl.isBlank()) throw new RuntimeException("LLM Base URL 未配置");
if (model == null || model.isBlank()) throw new RuntimeException("LLM 模型名称未配置");
```

No `if null then default to gpt-3.5-turbo`. No `resolveBaseUrl(model)`. Just read DB and use directly.

## Pitfalls

- **User says "不要大量 fallback, 不好排查错误"** — they want strict errors, not silent fallbacks. If config is missing, say WHICH field is missing.
- **User says "不要重复的配置"** — single source of truth. If you have a JSON file AND database, pick one.
- **User says "你这个行不行"** — they're comparing to Hermes which fetches models dynamically via `/v1/models`. Don't hardcode model lists.
- **`/v1/models` returns non-chat models** — always filter. Different providers return different model types.
- **Some providers may not support `/v1/models`** — the endpoint returns 404 or empty. Handle gracefully, let user type model name manually (`allow-create` on el-select).
- **API Key may be masked or encrypted when user clicks "获取模型"** — backend must detect and read real key from DB.
