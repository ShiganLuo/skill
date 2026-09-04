# Sensitive Config Encryption (API Keys, Secrets)

When a system config page manages API keys or secrets, storing them as plaintext in the database is a security risk.

## Backend: AES-GCM Encrypt at Rest

Create `AesEncryptUtil.java` in `common/util/`:

```java
public static String encrypt(String plaintext) {
    byte[] iv = new byte[12]; // GCM recommended IV length
    new SecureRandom().nextBytes(iv);
    // AES/GCM/NoPadding, 128-bit tag
    return "ENC:" + Base64.getEncoder().encodeToString(ivPlusCiphertext);
}

public static String decrypt(String ciphertext) {
    if (!ciphertext.startsWith("ENC:")) return ciphertext; // backward compat
    // extract IV (first 12 bytes), decrypt remainder
}

public static String mask(String value) {
    String real = isEncrypted(value) ? decrypt(value) : value;
    if (real.length() <= 8) return "********";
    return real.substring(0, 3) + "***" + real.substring(real.length() - 4);
}
```

Key source: env var `BIOPLATFORM_AES_KEY` (32 bytes for AES-256). Dev fallback hardcoded.

## Backend: Service Layer Rules

1. **`getAllConfigs()`** — sensitive keys return **masked** values (`sk-***here`)
2. **`getConfigValue(key)`** — returns **decrypted** plaintext (for LLM API calls, etc.)
3. **`updateConfig(key, value)`** — if value contains `***`, skip (user didn't change). Otherwise encrypt before storing.

```java
private boolean isSensitiveKey(String key) {
    String lower = key.toLowerCase();
    return lower.contains("key") || lower.contains("secret")
        || lower.contains("password") || lower.contains("token");
}
```

## Frontend: ConfigView Pattern

Password-type inputs show masked values. On save:
- Masked value (with `***`) → backend skips (user didn't touch it)
- New real value → backend encrypts and stores

```vue
<el-input v-model="llmConfig.apiKey" type="password" show-password placeholder="sk-..." />
```

## Migration: Old Plaintext Data

`decrypt()` returns plaintext as-is when no `ENC:` prefix. No migration script needed.

## Pitfall: AgentService Must Use getConfigValue, Not Direct Mapper

When the service layer encrypts configs, `systemConfigMapper.selectByKey(key).getConfigValue()` returns the encrypted blob (`ENC:...`). Use `systemService.getConfigValue(key)` which decrypts automatically.

**Real mistake**: `AgentServiceImpl.callLlmApi()` read directly from `systemConfigMapper` → got `ENC:...` → sent encrypted blob as API key → LLM provider returned 401.

**Fix**: Inject `SystemService` (not `SystemConfigMapper`), call `systemService.getConfigValue("llm_api_key")`.

## Pitfall: Don't Log Sensitive Values

```java
// WRONG: log.info("更新系统配置: key={}, value={}", key, value);
// RIGHT: log.info("更新系统配置: key={}", key);
```

## Frontend: Client-Side Encryption Before HTTP Send

When the user enters an API key in the browser, the HTTP request body still shows it as plaintext in DevTools Network tab. For true end-to-end protection, encrypt on the frontend before sending.

### crypto.ts Utility

Create `src/utils/crypto.ts` using Web Crypto API (AES-GCM, same algorithm as backend):

```typescript
const SECRET_KEY = 'your-shared-key-32-bytes!!'  // must match backend BIOPLATFORM_AES_KEY

export async function encrypt(plaintext: string): Promise<string> {
  const keyBytes = new TextEncoder().encode(SECRET_KEY).slice(0, 32)
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, ['encrypt'])
  const encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, tagLength: 128 }, key, new TextEncoder().encode(plaintext))
  const combined = new Uint8Array(iv.length + encrypted.byteLength)
  combined.set(iv)
  combined.set(new Uint8Array(encrypted), iv.length)
  return 'ENC:' + btoa(Array.from(combined).map(b => String.fromCharCode(b)).join(''))
}

export function isEncrypted(value: string): boolean {
  return value != null && value.startsWith('ENC:')
}
```

### ConfigView Integration

1. **Track dirty state**: `const apiKeyDirty = ref(false)` + `@input="apiKeyDirty = true"` on the input
2. **Only send when modified**: `if (apiKeyDirty.value && apiKey && !apiKey.includes('***'))`
3. **Encrypt before push**: `const encryptedKey = await encrypt(apiKey)` → push to allConfigs
4. **Backend recognizes `ENC:` prefix**: `updateConfig` checks `AesEncryptUtil.isEncrypted(value)` → store directly, don't re-encrypt

### Pitfall: ALL code paths that send the key must encrypt

When there's a "test connection" button AND a "save" button, BOTH must encrypt. The `testLlmConnection` function was sending plaintext while `handleSave` was encrypting. User caught this: "前端怎么传送的还是明文".

**Checklist**: grep the ConfigView for every HTTP call that includes the API key — each one must go through `encrypt()` first. This includes:
- `updateConfig` (save button)
- `fetchLlmModels` (fetch models button) — this was missed initially, user reported "还是在传输明文api key"
- Any "test connection" endpoint

**Fix for fetch-models**: encrypt before sending:
```typescript
async function handleFetchModels() {
  let keyToSend = llmConfig.apiKey
  if (keyToSend && !keyToSend.includes('***')) {
    keyToSend = await encrypt(keyToSend)
  }
  const models = await fetchLlmModels({ baseUrl: llmConfig.baseUrl, apiKey: keyToSend })
}
```

Backend `AdminSystemController.fetchModels()` already handles `ENC:` prefix — it decrypts before using.

## Pitfall: Decrypt BEFORE Checking for Masked Values

When the frontend encrypts a masked value (`sk-***here` → `ENC:Base64...`), the backend's `updateConfig` receives `ENC:...` which does NOT contain `***`. The naive check `value.contains("***")` passes, and the encrypted masked value gets stored. Later, `decrypt()` returns `sk-***here` — the masked value, not the real key.

**Root cause**: Frontend encrypts the masked value before sending (because `apiKeyDirty` was set to true by some interaction, and the `!includes('***')` check happened before encryption but the value was already masked from the DB load).

**Fix — decrypt before checking**:
```java
if (isSensitiveKey(key)) {
    String realValue = AesEncryptUtil.isEncrypted(value)
            ? AesEncryptUtil.decrypt(value) : value;
    if (realValue.contains("***")) {
        log.debug("跳过未修改的敏感配置: key={}", key);
        return;  // masked value, skip
    }
    String storedValue = AesEncryptUtil.isEncrypted(value)
            ? value : AesEncryptUtil.encrypt(value);
    saveOrUpdate(key, storedValue);
}
```

**Also add a check in the consumer** (`callLlmApi` etc.):
```java
if (apiKey.contains("***")) {
    throw new RuntimeException("LLM API Key 为遮蔽值，请在后台重新输入真实的 API Key");
}
```

This is a **three-layer defense**:
1. Frontend: `!includes('***')` before encrypt
2. Backend updateConfig: decrypt then check for `***`
3. Backend consumer: check decrypted value for `***`

**Real mistake**: User saved config page → frontend encrypted `tp-***dso9` → backend stored `ENC:...` → `callLlmApi` decrypted to `tp-***dso9` → sent to LLM provider → 401. User said "我确认模型和api正确,为什么调用失败".

## Pitfall: Warn User When Masked Value Detected on Save

When the frontend detects the API key input contains `***` (masked value from DB), show a warning instead of silently skipping:
```typescript
if (llmConfig.apiKey && llmConfig.apiKey.includes('***')) {
  ElMessage.warning('API Key 为遮蔽值未更新，请先输入真实的 API Key 再保存')
} else if (apiKeyDirty.value && llmConfig.apiKey) {
  const encryptedKey = await encrypt(llmConfig.apiKey)
  allConfigs.push({ key: 'llm_api_key', value: encryptedKey })
}
```

Silent skip confuses users — they think the key was saved but it wasn't.
