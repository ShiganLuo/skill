# End-to-End Sensitive Config Encryption

Pattern for encrypting API keys and secrets so they never appear in plain text — not in browser DevTools, not in DB, not in API responses.

## Architecture

```
Frontend Input → Web Crypto AES-GCM encrypt → "ENC:Base64..." → HTTP POST
                                                                    ↓
Backend updateConfig() ← detects "ENC:" prefix ← stores as-is in DB
                                                                    ↓
Backend getConfigValue() ← AesEncryptUtil.decrypt() ← reads from DB
                                                                    ↓
Backend getAllConfigs() ← AesEncryptUtil.mask() → "sk-***here" → Frontend display
```

## Key components

### Backend: `AesEncryptUtil.java`

- AES-256-GCM with 12-byte IV, 128-bit auth tag
- Key from `BIOPLATFORM_AES_KEY` env var (fallback default for dev)
- Encrypt: `ENC:` + Base64(iv + ciphertext + tag)
- Decrypt: strip `ENC:` prefix, split iv/ciphertext, AES-GCM decrypt
- `isEncrypted(value)`: checks `ENC:` prefix — used to avoid double-encryption
- `mask(value)`: decrypt if encrypted, then show first 3 + `***` + last 4 chars

### Frontend: `crypto.ts`

- Uses Web Crypto API (`crypto.subtle.encrypt` with AES-GCM)
- Same key derivation as backend (UTF-8 encode, truncate/pad to 32 bytes)
- Same output format: `ENC:` + Base64(iv + ciphertext)
- `isEncrypted(value)`: same `ENC:` prefix check

### Backend: `SystemServiceImpl`

- `getAllConfigs()`: sensitive keys (containing "key"/"secret"/"password"/"token") → `mask()` for display
- `getConfigValue(key)`: always returns decrypted plaintext for internal use
- `updateConfig(key, value)`: 
  - **MUST decrypt first, then check for `***`** — the encrypted form `ENC:Base64...` never contains `***`, so checking the raw value is useless
  - If decrypted value contains `***` → skip (user didn't change masked field)
  - If `isEncrypted(value)` → store directly (frontend already encrypted)
  - Otherwise → `encrypt(value)` then store

### Frontend: `ConfigView.vue`

- `apiKeyDirty` ref tracks whether user actually typed in the API key field
- `@input="apiKeyDirty = true"` on the password input
- On save: only include API key in request if `apiKeyDirty && !value.includes('***')`
- Encrypt before sending: `const encryptedKey = await encrypt(llmConfig.apiKey)`

## Pitfalls

- **Double encryption**: If backend always calls `encrypt()` without checking `isEncrypted()`, the value gets encrypted twice → decryption fails → LLM calls get 401
- **Mask detection**: `contains("***")` is a heuristic. Works because `mask()` always produces `***`. But legitimate values containing `***` would be incorrectly skipped — acceptable for API keys
- **Key must match**: Frontend `SECRET_KEY` constant must equal backend `BIOPLATFORM_AES_KEY`. Mismatch → frontend encrypts with key A, backend decrypts with key B → garbled plaintext
- **vue-tsc ref auto-unwrap**: In Vue template `@input`, refs are auto-unwrapped. Use `apiKeyDirty = true` not `apiKeyDirty.value = true` in templates. Use `.value` in `<script>` section only
