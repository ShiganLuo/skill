# LLM Provider Configuration Pattern

When building a platform with LLM integration, the config management approach matters.

## Anti-Pattern: Over-Engineered Provider Resolution

Initial approach had 3 layers of fallback:
1. `llm_provider` DB field → resolve via JSON file → get base_url
2. `llm_base_url` DB field as fallback
3. Model name auto-matching as final fallback

**User correction**: "不要大量fall back,不好排查错误" (don't use lots of fallbacks, hard to debug errors).

## Correct Approach: Strict Config with Clear Errors

```java
String apiKey = systemService.getConfigValue("llm_api_key");
String model = systemService.getConfigValue("llm_model");
String baseUrl = systemService.getConfigValue("llm_base_url");

if (apiKey == null || apiKey.isBlank()) {
    throw new RuntimeException("LLM API Key 未配置，请在后台系统配置中设置");
}
if (baseUrl == null || baseUrl.isBlank()) {
    throw new RuntimeException("LLM Base URL 未配置，请在后台系统配置中设置");
}
if (model == null || model.isBlank()) {
    throw new RuntimeException("LLM 模型名称未配置，请在后台系统配置中设置");
}
```

Each missing config gets a specific error message telling the user exactly what to configure.

## Anti-Pattern: Duplicate Config Sources

Using both `llm-providers.json` AND `system_configs` table for the same settings creates confusion about which is authoritative.

**User correction**: "不要做重复的配置,比如json和数据库".

**Solution**: Hardcode provider list in frontend ConfigView (it's just UI options), store actual config in database only.

```typescript
const llmProviders = [
  { key: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', models: ['deepseek-chat', 'deepseek-coder'], defaultModel: 'deepseek-chat' },
  { key: 'mimo', name: 'Xiaomi MiMo', baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1', models: ['mimo-v2.5-pro'], defaultModel: 'mimo-v2.5-pro' },
  { key: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'], defaultModel: 'gpt-4o-mini' },
  { key: 'custom', name: '自定义', baseUrl: '', models: [], defaultModel: '' },
]
```

Selecting a provider auto-fills baseUrl and model dropdown. User can still manually edit. All saved to `system_configs` table.

## Anti-Pattern: Hardcoded Model Names in Controller

```java
// WRONG: hardcodes model that may not exist on the target provider
agentService.createConversation(userId, null, "新对话", "gpt-4");

// CORRECT: use null, let the system config determine the model
agentService.createConversation(userId, null, "新对话", null);
```

## Config Keys

All stored in `system_configs` table with flat keys:
- `llm_provider` — provider key (e.g., "deepseek", "mimo")
- `llm_api_key` — encrypted API key
- `llm_model` — model name (e.g., "mimo-v2.5-pro")
- `llm_base_url` — API base URL

## UI Pattern: Provider Select → Auto-Fill

```vue
<el-select v-model="llmConfig.provider" @change="handleProviderChange">
  <el-option v-for="p in llmProviders" :key="p.key" :label="p.name" :value="p.key" />
</el-select>
<el-select v-model="llmConfig.model">
  <el-option v-for="m in currentModels" :key="m" :label="m" :value="m" />
</el-select>
<el-input v-model="llmConfig.apiKey" type="password" show-password @input="apiKeyDirty = true" />
<el-input v-model="llmConfig.baseUrl" /> <!-- auto-filled, can override -->
```

```typescript
function handleProviderChange(providerKey: string) {
  const p = llmProviders.find(p => p.key === providerKey)
  if (p) {
    llmConfig.baseUrl = p.baseUrl
    llmConfig.model = p.defaultModel
  }
}
```
