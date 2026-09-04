# Admin Config Save: Snapshot-Based Change Detection

Problem: saving ALL configs on every save overwrites unmodified sensitive fields (API keys, tokens).

## Pattern: Snapshot Diff

```typescript
// 1. Load configs → save original snapshot
let originalSnapshot: Record<string, string> = {}

function collectSnapshot(): Record<string, string> {
  const snap: Record<string, string> = {}
  for (const [k, v] of Object.entries(basicConfig)) snap[`basic.${k}`] = String(v)
  for (const [k, v] of Object.entries(securityConfig)) snap[`security.${k}`] = String(v)
  // ... all config groups + flat keys like llm_api_key
  return snap
}

const loadConfigs = async () => {
  // ... populate reactive objects from API ...
  originalSnapshot = collectSnapshot()
}

// 2. On save: compare current vs original, only send changed items
const handleSave = async () => {
  const currentSnapshot = collectSnapshot()
  const changedConfigs: { key: string; value: string }[] = []

  for (const [key, value] of Object.entries(currentSnapshot)) {
    if (originalSnapshot[key] !== value) {
      // Skip masked sensitive values (e.g. "sk-***cdef")
      if (key === 'llm_api_key' && value.includes('***')) continue
      changedConfigs.push({ key, value })
    }
  }

  if (changedConfigs.length === 0) {
    ElMessage.info('没有配置被修改')
    return
  }

  for (const config of changedConfigs) {
    // Encrypt sensitive fields before sending
    let sendValue = config.value
    if (config.key === 'llm_api_key') sendValue = await encrypt(config.value)
    await updateConfig(0, { key: config.key, value: sendValue })
  }

  // Update snapshot after successful save
  originalSnapshot = collectSnapshot()
}
```

## Backend: Skip Masked Values

```java
public void updateConfig(String key, String value) {
    if (isSensitiveKey(key)) {
        String realValue = isEncrypted(value) ? decrypt(value) : value;
        if (realValue.contains("***")) {
            log.debug("跳过未修改的敏感配置: key={}", key);
            return;  // Don't overwrite with masked value
        }
        saveOrUpdate(key, isEncrypted(value) ? value : encrypt(value));
    } else {
        saveOrUpdate(key, value);
    }
}
```

## Key Rules

1. NEVER special-case one field type — all configs use the same snapshot diff
2. API Key is NOT special — it's just another config with encrypted storage
3. Masked values (`***`) are skipped at both frontend and backend
4. Snapshot is updated only after successful save
5. "No changes" → no API calls at all (saves network + prevents accidental overwrites)
