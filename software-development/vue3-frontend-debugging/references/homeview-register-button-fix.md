# HomeView "免费注册" Button Fix (2026-08-20)

## Symptom
Clicking "免费注册" (Free Register) button on homepage did nothing.

## Root Cause
`HomeView.vue` dispatched `window.dispatchEvent(new Event('show-login-modal'))` but NO component listened for it. The event fired into the void.

Additionally, the event used plain `Event` which cannot carry payload — so even if a listener existed, it couldn't receive the desired mode (register vs login).

## Files Changed

### `views/home/HomeView.vue` — Dispatcher
```ts
// BEFORE: plain Event, no payload
function showLogin() {
  window.dispatchEvent(new Event('show-login-modal'))
}

// AFTER: CustomEvent with register mode
function showLogin() {
  window.dispatchEvent(new CustomEvent('show-login-modal', { detail: 'register' }))
}
```

### `layout/MainLayout.vue` — Listener + prop pass-through
```ts
// Added imports
import { ref, computed, onMounted, onUnmounted } from 'vue'

// Added state + handler
const loginModalMode = ref<'login' | 'register'>('login')

function handleShowLoginModal(e: Event) {
  const mode = (e as CustomEvent).detail
  loginModalMode.value = mode || 'login'
  showLoginModal.value = true
}

onMounted(() => {
  window.addEventListener('show-login-modal', handleShowLoginModal)
})
onUnmounted(() => {
  window.removeEventListener('show-login-modal', handleShowLoginModal)
})

// Template updated
// <LoginModal v-model:visible="showLoginModal" :mode="loginModalMode" />
```

### `components/LoginModal.vue` — Accept mode prop
```ts
// Added mode prop
const props = defineProps<{
  visible: boolean
  mode?: 'login' | 'register'
}>()

// isLogin now respects mode prop
const isLogin = ref(props.mode !== 'register')
watch(() => props.mode, (val) => {
  if (val) isLogin.value = val !== 'register'
})
```

## Verification
- `npx vue-tsc --noEmit` — passed
- `npm run build` — passed
- Targeted grep checks for all 3 files — all passed
