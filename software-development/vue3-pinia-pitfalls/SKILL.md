---
name: vue3-pinia-pitfalls
description: "Use when Vue3+Pinia role checks fail after page refresh."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [vue3, pinia, spa, state-management, router, debugging]
    related_skills: [vue3-frontend-debugging, spring-vue-fullstack-patterns, debugging]
triggers:
  - "admin page redirects to dashboard after refresh"
  - "role check fails despite being logged in"
  - "userInfo is null after page refresh"
  - "menu items hidden for admin user"
  - "Pinia state lost on F5"
---

# Vue3 + Pinia Pitfalls

## When to Use

- User reports "I'm logged in as admin but can't access [role-protected page]"
- Vue3 page works after login but shows empty/default state after F5 refresh
- Menu items with `v-if="hasRole()"` are hidden despite user having the role
- Header/avatar shows fallback text instead of actual user info after refresh

---

## Pinia State Lost After Page Refresh — Role/Permission Checks Fail

**THE most common cause of "admin can't access admin pages after F5 refresh".**

### Root Cause

Pinia state does NOT persist across page refreshes by default. If the app manually saves `userInfo` to localStorage (e.g., `localStorage.setItem('userInfo', JSON.stringify(res))`) and has a restore function (e.g., `initUserInfo()`), but **never calls the restore function on app startup**, then after page refresh:

1. Token exists in localStorage → `isAuthenticated()` returns true → user stays on the page
2. `userInfo` in Pinia is `null` (Pinia state reset on refresh)
3. `hasRole('ROLE_ADMIN')` returns `false` (because `!userInfo.value` → false)
4. Route guard redirects role-protected routes to `/dashboard`
5. Menu items with `v-if="userStore.hasRole('ROLE_ADMIN')"` are hidden
6. Header shows fallback text like `'管理员'` — user thinks they're logged in as admin

**Key tell**: User says "I'm logged in as admin but can't access system config." The header shows a fallback name, the dashboard works, but all role-protected pages redirect.

### Diagnosis

```bash
# 1. Check if initUserInfo exists but is never called
grep -rn 'initUserInfo' src/
# If it's ONLY in stores/user.ts (definition + export) but NOT in main.ts, App.vue, or router — that's the bug

# 2. Check if router guard has role-based redirects
grep -n 'hasRole\|meta.roles' src/router/index.ts

# 3. Check if menu visibility depends on role
grep -n "v-if.*hasRole" src/layout/*.vue
```

### Fix: Restore userInfo in Router Guard

```typescript
// router/index.ts
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth !== false) {
    if (!userStore.isAuthenticated()) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }

    // Page refresh: token exists but Pinia userInfo is null.
    // Restore from localStorage immediately, then fetch fresh from server.
    if (!userStore.userInfo) {
      userStore.initUserInfo()       // synchronous: reads localStorage
      userStore.fetchUserInfo()      // async: fetches latest from server (fire-and-forget)
    }
  }

  // Role-based route guard (now userInfo is populated from localStorage)
  const requiredRoles = to.meta.roles as string[] | undefined
  if (requiredRoles?.length) {
    const hasRole = requiredRoles.some(role => userStore.hasRole(role))
    if (!hasRole) {
      next({ path: '/dashboard' })
      return
    }
  }

  next()
})
```

**Why `initUserInfo()` before `fetchUserInfo()`**: `initUserInfo()` is synchronous (reads localStorage) so `userInfo` is populated immediately for the role check. `fetchUserInfo()` is async — by the time the next navigation happens, fresh server data will be in the store.

### Alternative: Use pinia-plugin-persistedstate

If the project uses `pinia-plugin-persistedstate`, the store automatically persists to localStorage and restores on creation. No manual `initUserInfo()` needed. Verify:

```bash
grep -rn 'persistedstate\|pinia-plugin-persist' src/main.ts src/stores/
```

If NOT using the plugin, manual localStorage save/restore is needed — and the restore MUST be called in the router guard.

### Pitfall — async router guard

The `beforeEach` callback must be `async` if you call async functions inside it (like `fetchUserInfo`). Without `async`, the guard proceeds before the function completes. But `initUserInfo()` is synchronous, so the role check works immediately after it.

### Pitfall — misleading fallback UI

The header showing `'管理员'` as fallback (`userStore.userInfo?.nickname || '管理员'`) makes the user think they're properly logged in as admin, when actually `userInfo` is null. This makes debugging harder — the user reports "I'm admin" but the store disagrees. Always check `localStorage.getItem('userInfo')` in the browser console to verify.

---

## Double-unwrap in Axios Interceptor

See the `vue3-frontend-debugging` skill for the full double-unwrap pattern. Summary:

When the response interceptor returns `response.data.result` AND the `request()` helper also accesses `.data`, the second unwrap produces `undefined`. Components receive `undefined` → empty lists, silent failures.

**Quick check**: `grep 'response.data.result' src/utils/http/axios.ts` + `grep 'res\.data' src/utils/http/axios.ts`. If BOTH exist, that's the bug.

---

## Token Refresh Race with Pinia Persist

When Axios interceptor refreshes a token and sets `userStore.token = newToken`, the `pinia-plugin-persistedstate` writes to localStorage asynchronously (microtask). If a raw `fetch` call reads localStorage immediately after, it may get the OLD token.

**Fix**: Read token from Pinia store first, localStorage as fallback. See `vue3-frontend-debugging` skill for the full `getAccessToken()` pattern.

---

## Pitfalls

- **`write_file` corrupts .vue files**: ALWAYS use `patch` tool for Vue SFC edits.
- **HMR doesn't reload interceptor changes**: After editing `axios.ts`, user must hard-refresh (F5).
- **`watch(dialogVisible)` race condition**: State cleanup in watchers can race with Vue's async flush. Prefer explicit handlers over watchers for dialog close logic.
