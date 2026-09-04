# LLM Configuration Fool-Proofing Patterns

Session: 2026-08-25 bioplatform AI assistant + LLM config page.

## The encrypted-masked-value bypass bug

**Symptom**: API key stored as encrypted garbage, LLM calls return 401 even after user "saved" a valid key.

**Root cause chain**:
1. Frontend loads config page → backend returns masked key `sk-***here`
2. User doesn't modify the key field, clicks "保存配置"
3. Frontend's `apiKeyDirty` check somehow passes (or user touches field briefly)
4. Frontend encrypts the masked value: `encrypt("sk-***here")` → `ENC:Base64...`
5. Backend `updateConfig` receives `ENC:Base64...` — does NOT contain `***` (it's encrypted!)
6. Backend stores the encrypted masked value
7. `callLlmApi` decrypts → gets `sk-***here` → sends to LLM → 401

**Fix — three-layer defense**:

```java
// Layer 1: Backend updateConfig — decrypt BEFORE checking ***
if (isSensitiveKey(key)) {
    String realValue = AesEncryptUtil.isEncrypted(value)
            ? AesEncryptUtil.decrypt(value) : value;
    if (realValue.contains("***")) {
        log.debug("跳过未修改的敏感配置: key={}", key);
        return;
    }
    // encrypt and store
}

// Layer 2: Backend callLlmApi — check decrypted key before calling
if (apiKey.contains("***")) {
    throw new RuntimeException("LLM API Key 为遮蔽值，请在后台重新输入真实的 API Key");
}
```

```javascript
// Layer 3: Frontend handleSave — check BEFORE encrypting
if (llmConfig.apiKey && llmConfig.apiKey.includes('***')) {
    ElMessage.warning('API Key 为遮蔽值未更新，请先输入真实的 API Key 再保存')
} else if (apiKeyDirty.value && llmConfig.apiKey) {
    const encryptedKey = await encrypt(llmConfig.apiKey)
    allConfigs.push({ key: 'llm_api_key', value: encryptedKey })
}
```

**Key lesson**: When you encrypt a value before checking it, the check is useless. Always check the DECRYPTED value for sensitive fields.

## Silent skip vs user feedback

When `updateConfig` silently skips a masked value, the user sees "配置保存成功" but the API key wasn't actually updated. Next time they use the AI assistant, it fails with 401 and they don't know why.

**Rule**: When skipping a sensitive value, ALWAYS show a warning:
```javascript
ElMessage.warning('API Key 为遮蔽值未更新，请先输入真实的 API Key 再保存')
```

Don't silently succeed when data wasn't actually saved.

## Removing redundant UI elements

The "测试连接" button was redundant because:
1. It just saved config and said "go test on the frontend AI assistant"
2. "获取模型" already proves the connection works (key + url + network all valid)

**Rule**: If button A's success implies button B's success, delete button B. Don't keep dead-end buttons that add no value.

## Dynamic model fetching via /v1/models

Don't hardcode model lists — providers update models frequently. Pattern:

```java
// Backend endpoint
@PostMapping("/llm/fetch-models")
public ApiResponse<List<String>> fetchModels(@RequestBody Map<String, String> params) {
    String url = baseUrl.replaceAll("/+$", "") + "/models";
    // Call provider's /v1/models with Bearer auth
    // Return list of model IDs
}
```

```vue
<!-- Frontend: filterable + allow-create for manual input -->
<el-select v-model="llmConfig.model" filterable allow-create>
  <el-option v-for="m in availableModels" :key="m" :label="m" :value="m" />
</el-select>
<el-button @click="handleFetchModels">获取模型</el-button>
```

## Provider switch UX

- Clear model list (provider-specific, different providers have different models)
- Keep API key (user may reuse keys across providers)
- Show hint text: "切换提供商后请确认 API Key 是否匹配"
- Don't force-clear the key — it's aggressive and annoying
