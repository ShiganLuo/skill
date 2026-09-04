# Axios Interceptor + UI Error Display Pattern

## Problem

When the axios response interceptor already shows `ElMessage.error()` for non-200 business codes, the UI component must NOT show its own error message. Otherwise the user sees two toasts for one failure.

## Wrong Pattern (two toasts)

```typescript
// axios interceptor (in utils/http/axios.ts):
if (code !== 200) {
  ElMessage.error(msg || '请求失败')  // ← toast 1
  return Promise.reject(new Error(msg))
}

// LoginView.vue:
try {
  const success = await userStore.login(form)
  if (!success) {
    ElMessage.error('登录失败，请检查用户名和密码')  // ← toast 2 (duplicate!)
  }
} catch (error) {
  ElMessage.error('登录失败，请稍后重试')  // ← toast 3 (triplicate!)
}
```

Result: user sees "用户不存在" AND "登录失败，请检查用户名和密码" simultaneously.

## Correct Pattern (one toast)

```typescript
// LoginView.vue:
try {
  const success = await userStore.login(form)
  if (success) {
    ElMessage.success('登录成功')
    router.push(redirect)
  }
  // Failure: axios interceptor already showed the specific error
} catch {
  // Axios interceptor already showed the error message
}
```

## Rule

If the axios interceptor handles error display, the UI layer should only handle success. The interceptor has the actual error message from the backend (e.g., "用户不存在", "密码错误") which is more specific than generic messages like "登录失败".

## When to Apply

- Login/register forms
- Any form submission where the backend returns specific error messages
- API calls where the interceptor shows `ElMessage.error()`

## When NOT to Apply

- If the interceptor uses `silent: true` (no auto-toast), the UI must handle errors
- If the interceptor only handles HTTP errors (4xx/5xx), not business errors (code !== 200)
