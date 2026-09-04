# Vue Router Component Reuse & Form Draft Patterns

## Component Reuse Pitfall (CRITICAL)

When navigating between routes using the **same component** (e.g. `/projects/1` → `/projects/2`), Vue Router **reuses the component instance**. One-time assignments in `<script setup>` become stale:

```ts
// WRONG: STALE on navigation
const projectId = Number(route.params.id)

// RIGHT: computed + watch
const projectId = computed(() => Number(route.params.id))

watch(() => route.params.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    pagination.page = 1
    loadProject()
    loadList()
  }
})
```

Also fix reactive objects that captured the old value:
```ts
// WRONG
const form = reactive({ id: 0, projectId, name: '' })
// RIGHT
const form = reactive({ id: 0, projectId: projectId.value, name: '' })
```

**Diagnostic**: Detail page shows previous item's data after navigation → check bare `route.params.xxx` assignments.

## localStorage Form Draft Auto-Save

Auto-save dialog form to localStorage on close, restore on reopen:

```ts
const DRAFT_KEY = 'my_form_draft'

watch(dialogVisible, (newVal, oldVal) => {
  if (oldVal === true && newVal === false) saveDraft()
})

const saveDraft = () => {
  const draft = { name: form.name, description: form.description }
  if (draft.name || draft.description) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  }
}
const restoreDraft = () => {
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return false
  try { Object.assign(form, JSON.parse(raw)); return true } catch { return false }
}
const clearDraft = () => localStorage.removeItem(DRAFT_KEY)
```

**Rules**: Only save non-empty forms; clear on success; skip in edit mode; toast when restored.
