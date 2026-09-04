# Page Refresh in keep-alive Layouts (v-if Pattern)

## Why NOT keep-alive :exclude

The `keep-alive :exclude` approach was tried first and **failed silently**:
- Component names must match exactly — route names vs component names drift
- The exclude/clear cycle on `nextTick` is unreliable — sometimes the component doesn't re-create
- Debugging is painful: no error, just "nothing happens"

**Do NOT use `keep-alive :exclude` for page refresh.** Use the `v-if` pattern below.

## Solution: v-if on router-view

Destroy and re-render the entire router-view subtree. Simple, reliable, no component-name matching needed.

### 1. Layout (`AdminLayout.vue`)

```vue
<script setup lang="ts">
import { ref, nextTick } from 'vue'

const isRefresh = ref(true)

function reload() {
  isRefresh.value = false
  nextTick(() => {
    isRefresh.value = true
  })
}
</script>

<template>
  <el-header>
    <!-- Refresh button in header, next to collapse btn, BEFORE breadcrumb -->
    <el-icon class="refresh-btn" @click="reload()"><Refresh /></el-icon>
    <el-breadcrumb separator="/">
      <!-- ... -->
    </el-breadcrumb>
  </el-header>

  <WorkTab />

  <el-main>
    <router-view v-if="isRefresh" v-slot="{ Component }">
      <keep-alive>
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </el-main>
</template>

<style scoped>
.refresh-btn {
  font-size: 18px;
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;
}
.refresh-btn:hover {
  color: #409eff;
}
</style>
```

### 2. No store changes needed

Unlike the exclude approach, this needs NO Pinia store changes. The `isRefresh` ref and `reload()` function live entirely in the layout component.

### 3. WorkTab.vue — NO refresh button here

The refresh button goes in the **header bar** (next to collapse button, before breadcrumb), NOT in the tab bar. This matches the blog backend's layout convention.

## How It Works

1. User clicks refresh → `isRefresh = false`
2. `v-if="isRefresh"` destroys the `<router-view>` and all its children
3. `nextTick` fires → `isRefresh = true`
4. Vue re-creates `<router-view>` fresh — component state reset, data re-fetched

## Pitfalls

- **State loss is intentional**: Form inputs, scroll positions, local refs are all reset. This IS the desired "hard refresh" behavior.
- **keep-alive still works**: Components are still cached for tab switches. The `v-if` only destroys when explicitly refreshing.
- **Import Refresh icon**: Add `Refresh` to the `@element-plus/icons-vue` import in AdminLayout.
- **No import needed for Refresh in WorkTab**: Don't add Refresh to WorkTab.vue — the button isn't there anymore.
