# Config Snapshot Save Pattern

When a settings page has many fields and a single "save all" button, sending ALL fields every time risks overwriting sensitive values (API keys) and wastes requests.

## Pattern

### 1. Define snapshot collector

```typescript
function collectSnapshot(): Record<string, string> {
  const snap: Record<string, string> = {}
  for (const [k, v] of Object.entries(basicConfig)) snap[`basic.${k}`] = String(v)
  for (const [k, v] of Object.entries(llmConfig)) snap[`llm_${k}`] = String(v)
  // ... all config groups
  return snap
}
```

### 2. Save snapshot after load

```typescript
let originalSnapshot: Record<string, string> = {}

const loadConfigs = async () => {
  // ... populate reactive state from API
  originalSnapshot = collectSnapshot()
}
```

### 3. Compare on save

```typescript
const handleSave = async () => {
  const currentSnapshot = collectSnapshot()
  const changedConfigs: { key: string; value: string }[] = []

  for (const [key, value] of Object.entries(currentSnapshot)) {
    if (originalSnapshot[key] !== value) {
      // Skip masked sensitive values (e.g., "sk-***cdef")
      if (isSensitiveKey(key) && value.includes('***')) continue
      changedConfigs.push({ key, value })
    }
  }

  if (changedConfigs.length === 0) {
    ElMessage.info('没有配置被修改')
    return
  }

  // Encrypt sensitive fields before sending
  for (const config of changedConfigs) {
    let sendValue = config.value
    if (isSensitiveKey(config.key)) {
      sendValue = await encrypt(config.value)
    }
    await updateConfig({ key: config.key, value: sendValue })
  }

  // Update snapshot after successful save
  originalSnapshot = collectSnapshot()
  ElMessage.success(`配置保存成功（更新了 ${changedConfigs.length} 项）`)
}
```

## Key decisions

- **No per-field dirty flags** — `apiKeyDirty` etc. are eliminated. Everything uses the same snapshot comparison.
- **Sensitive fields**: snapshot stores the masked value from backend. If user doesn't touch it, it stays identical → skipped. If user enters a new real value, it differs → encrypted and sent.
- **No "save all" requests** — only changed items are sent, reducing API calls and avoiding accidental overwrites.
- **Snapshot updates after save** — so subsequent saves without further edits produce zero changes.
