# Admin App Initialization Timing

## The Problem

The admin app (`blog-vue3-back`) has a race condition between three initialization phases that can cause a blank page on first visit from the frontend.

## Initialization Sequence

```
1. main.ts → initStore(app) → initRouter(app) → app.mount('#app')
2. Store constructor: getFrontendToken() reads frontend localStorage → sets accessToken
3. Router beforeEach guard fires (before any component mounts):
   - Checks userStore.accessToken → found (from step 2)
   - isRouteRegistered = false → calls getMenuData()
   - getMenuData() shows ElLoading overlay + 300ms setTimeout
4. During the 300ms delay, App.vue onMounted fires:
   - initState() → validateStorageData()
   - If localStorage empty (first visit): calls logOut() → clears token!
5. After 300ms: guard calls next() → navigation completes
6. Next navigation: guard sees no token → redirects to login → blank page
```

## Key Files

- `src/store/modules/user.ts` — Store constructor with `getFrontendToken()`
- `src/utils/storage.ts` — `validateStorageData()` and `initState()`
- `src/App.vue` — `onMounted` calls `initState()`
- `src/router/index.ts` — `beforeEach` guard with `getMenuData()`
- `src/api/menuApi.ts` — `getMenuList()` with 300ms loading delay

## Token Sharing Between Front and Admin

The admin reads the frontend's token from localStorage:
- Frontend stores: `Base64.encode('accessToken')` → `Base64.encode(JSON.stringify(token))`
- Admin reads via `getFrontendToken()` using the same Base64 encoding scheme
- Admin also has its own storage: `sys-v${version}` with prefix `blog-vu3-back`

## Fix Applied (validateStorageData timing)

In `storage.ts`, `validateStorageData()`: when localStorage is empty (no `sys-v*` data), return `true` instead of calling `logOut()`. Empty localStorage is normal on first visit.

## Fix Applied (getMenuData try-finally)

In `router/index.ts`, `getMenuData()`: added `try { ... } finally { closeLoading() }` around route registration. Previously, if `registerAsyncRoutes()` threw, the `ElLoading.service({lock: true})` overlay was never closed, blocking the entire page permanently. Also fixed missing `return` after `logOut()` in the empty-menuList check (execution continued to `registerAsyncRoutes` with empty list).

## Diagnosis Pattern

When admin shows blank page but works after refresh:
1. Check if `validateStorageData()` calls `logOut()` on empty localStorage
2. Trace the initialization order: store constructor → router guard → App.vue onMounted
3. The guard's async operation (getMenuData with 300ms delay) creates a window where onMounted can interfere
4. Check if `closeLoading()` is guaranteed to execute — if route registration throws without try-finally, ElLoading overlay stays forever
