---
name: vue3-performance-debugging
description: "Use when a Vue3 page is slow or loads excessive data."
tags: [vue3, frontend, performance, debugging, api-optimization]
---

# Vue3 Performance Debugging

Diagnose and fix Vue3 pages that are slow compared to siblings —
excessive API calls on mount, heavy child components in list loops,
unnecessary re-renders, and bloated initial payloads.

Related: `vue3-frontend-debugging` covers interaction bugs (buttons
not working, events not firing). This skill covers SLOW pages.

## Diagnosis Framework

When a user reports "page X is slow but page Y is fine":

1. Count API calls on page load (browser DevTools Network tab)
2. Compare with a fast sibling page's API call count
3. If the slow page has N× more requests, look for the N+1 pattern
4. Check component mount lifecycle for eager data fetching

## Pattern 1: N+1 API Calls from List Rendering

**THE most common cause of "this page is slow compared to others."**

A page renders a list of items. Each item mounts a child component
that fetches data in `onMounted` or via `watch(immediate: true)`.
N items = N additional API calls on page load.

### Concrete Example (Blog talk/说说 page)

```vue
<!-- talk.vue — list renders Comment for EACH talk item -->
<template>
  <div v-for="talk in talkList" :key="talk.id">
    <MdPreview :modelValue="talk.content" />
    <!-- EVERY item mounts Comment → fires 2 API calls -->
    <Comment :id="talk.id" :expand="true" />
  </div>
</template>
```

```vue
<!-- Comment/index.vue — fires on mount regardless of expand state -->
<script setup>
onMounted(() => {
  getCommentTotal()  // API call 1 per item
})

// expand=true triggers ParentItem which fetches immediately:
watch(() => props.id, () => { getComment() }, { immediate: true })
// API call 2 per item — loads ALL comments with nested replies
</script>
```

**Result**: 5 talk items → 1 (list) + 5 (comment totals) + 5 (comment lists)
= 11 concurrent API calls. Other pages make 1-2.

### Diagnosis

```bash
# Find child components with onMounted data fetching
grep -rn 'onMounted\|immediate:\s*true' src/components/Comment/
# Count how many times the child is used in a v-for
grep -n 'v-for.*Comment\|<Comment' src/views/talk/talk.vue
```

### Fix: Lazy-Load Child Data

**Option A — Collapse by default (simplest)**:
```vue
<!-- Before: always expanded, always fetching -->
<Comment :id="talk.id" :expand="true" :is-show-toggle="false" />

<!-- After: collapsed, fetches only on user click -->
<Comment :id="talk.id" :expand="false" :is-show-toggle="true" />
```

**Option B — v-if gate on the child component**:
```vue
<Comment v-if="talk._commentsLoaded" :id="talk.id" />
<button @click="talk._commentsLoaded = true">查看评论</button>
```

**Option C — Intersection Observer (viewport-triggered)**:
```vue
<!-- Only mount when scrolled into view -->
<div v-if="talk.inView">
  <Comment :id="talk.id" />
</div>
<!-- Use IntersectionObserver to set talk.inView = true -->
```

**Option D — Backend aggregation (eliminates extra calls)**:
Have the list API return comment counts inline:
```json
{ "id": 1, "content": "...", "commentCount": 3 }
```
Then `getCommentTotal()` calls are unnecessary — read from list data.

### Impact Measurement

Always count before/after:
```
Before: N API calls on page load (N = items × child fetches)
After:  1 + M API calls (M = items the user actually interacts with)
```

## Pattern 2: Heavy Component Mount in Loops

Each instance of a heavy component (markdown renderer, chart, rich
editor) in a `v-for` loop mounts and initializes independently.
10 items × 150ms init = 1.5s just for component setup.

### Diagnosis
- Chrome DevTools → Performance tab → look for long "Recalculate Style"
  or "Update Layer Tree" phases during mount
- Component init time appears in the flame chart as deep call stacks
  under the parent's mount

### Fixes
- **Virtual scrolling** (vue-virtual-scroller): only mount visible items
- **Lazy rendering**: render content on expand/interaction, not on mount
- **Throttle initial load**: reduce page size (e.g., `size: 5` → `size: 3`)

## Pattern 3: Unnecessary Reactive Overhead

Large reactive objects or deeply nested reactive data that Vue tracks
but never triggers re-renders for.

### Signs
- `reactive()` wrapping a 1000-item array that's only read, never mutated
- Deep `watch()` on a complex object when only one field matters

### Fixes
- Use `shallowRef()` for large read-only data
- Use `shallowReactive()` when only top-level keys change
- Narrow `watch()` targets: `watch(() => obj.specificField, ...)`

## Pitfalls

- **`:expand="true"` on every list item** — This is the #1 trap. If a
  child component fetches data when expanded, setting `expand=true` on
  all items causes N concurrent fetches. Default to `false`, let users
  expand on demand.
- **`watch(immediate: true)` in child components** — Fires on mount,
  before the parent can control whether the child should fetch. If the
  child is inside a `v-for`, this creates N parallel requests.
- **Confusing "total count" with "full data"** — Showing a comment count
  badge is lightweight; loading all comments with nested replies is not.
  Keep the count fetch, defer the data fetch.
- **Don't optimize the wrong thing** — If a page makes 3 API calls and
  is slow, the bottleneck is server-side (DB queries, N+1 in the
  backend). Frontend optimization only helps when the page makes many
  client-side requests.
- **Nginx reload after web container deploy** — After deploying a new
  frontend container (e.g., `blog_web`), run
  `docker exec nginx-proxy nginx -s reload` on the remote server to
  ensure the reverse proxy resolves the new container. Without reload,
  stale connections may persist.

## Verification

After fixing:
```bash
# TypeScript check
npx vue-tsc --noEmit
# Build check
npm run build
# Manual: open Network tab, load the page, count requests
# Compare with a known-fast sibling page
```
