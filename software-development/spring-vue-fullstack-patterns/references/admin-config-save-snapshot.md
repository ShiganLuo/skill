# Admin Config Save: Snapshot-Based Diff

## Problem: Saving All Configs Overwrites Unmodified Values

When a system config page has a single "Save" button, the naive approach sends ALL config values to the backend. This causes:

1. **Unnecessary API calls** — N configs = N requests, even if nothing changed
2. **Accidental overwrite of sensitive values** — API keys, passwords sent back as masked values
3. **Race conditions** — another admin changes a value, first admin's save overwrites it

## Pattern: Snapshot Diffing

### Frontend

```typescript
// Original values loaded from backend
let originalSnapshot: Record<string, string> = {}

function collectSnapshot(): Record<string, string> {
  const snap: Record<string, string> = {}
  for (const [k, v] of Object.entries(basicConfig)) snap[`basic.${k}`] = String(v)
  for (const [k, v] of Object.entries(securityConfig)) snap[`security.${k}`] = String(v)
  // ... all config groups
  snap['llm_provider'] = llmConfig.provider
  snap['llm_base_url'] = llmConfig.baseUrl
  snap['llm_model'] = llmConfig.model
  snap['site_contact_email'] = contactConfig.contactEmail
  snap['site_github_url'] = contactConfig.githubUrl
  return snap
}

// After loading configs from backend
const loadConfigs = async () => {
  // ... populate reactive objects ...
  originalSnapshot = collectSnapshot()  // save baseline
}

// On save
const handleSave = async () => {
  const currentSnapshot = collectSnapshot()
  const changedConfigs: { key: string; value: string }[] = []

  for (const [key, value] of Object.entries(currentSnapshot)) {
    if (originalSnapshot[key] !== value) {
      changedConfigs.push({ key, value })
    }
  }

  // API Key special handling (separate dirty flag + encryption)
  if (apiKeyDirty.value && llmConfig.apiKey && !llmConfig.apiKey.includes('***')) {
    const encryptedKey = await encrypt(llmConfig.apiKey)
    changedConfigs.push({ key: 'llm_api_key', value: encryptedKey })
  }

  if (changedConfigs.length === 0) {
    ElMessage.info('没有配置被修改')
    return
  }

  // Only send changed items
  for (const config of changedConfigs) {
    await updateConfig(0, { key: config.key, value: config.value })
  }

  // Update snapshot after successful save
  originalSnapshot = collectSnapshot()
  apiKeyDirty.value = false
  ElMessage.success(`配置保存成功（更新了 ${changedConfigs.length} 项）`)
}
```

### Rules

1. **Snapshot on load** — capture after `loadConfigs()` completes
2. **Diff on save** — compare current vs original, only send differences
3. **Update snapshot after save** — so subsequent saves don't re-send
4. **API Key separate** — keep `apiKeyDirty` flag, don't include in snapshot diff (it's masked)
5. **No change = no request** — show "没有配置被修改" message

### Pitfall: API Key Must NOT Be in Snapshot

The snapshot collects plain config values. The API key is masked in the UI (`sk-***cdef`), so comparing it with the snapshot is meaningless. Use the separate `apiKeyDirty` flag instead.

## Site-Config: Remove Hardcoded Fallbacks

The `FrontConfigController` returns site config for the public frontend. When database has no value, the fallback should be empty (not a hardcoded email/URL):

```java
// WRONG — shows fake email even when admin hasn't configured it
config.put("contactEmail", safeValue("site_contact_email", "support@bioplatform.com"));
config.put("githubUrl", safeValue("site_github_url", "https://github.com/bioplatform"));

// CORRECT — empty fallback, frontend v-if hides the element
config.put("contactEmail", safeValue("site_contact_email", ""));
config.put("githubUrl", safeValue("site_github_url", ""));
```

Admin configures these via the admin panel's system config (`site_contact_email`, `site_github_url`).
