---
name: vue3-element-plus-integration
description: Fix Element Plus CSS, el-upload auth, dialog styling.
trigger: Use when working with Vue3 + Element Plus projects, especially auto-import plugins, el-upload, programmatic dialogs, or markdown editors.
---

# Vue3 + Element Plus Integration Pitfalls

## Element Plus Full Registration (CRITICAL)

When using Element Plus WITHOUT auto-import (`unplugin-vue-components`), you MUST call `app.use(ElementPlus)` in `main.ts`. Without it, **ALL `el-*` components silently fail to render** — the page appears completely blank with no errors.

**Symptom**: `<div id="app" data-v-app=""><!----></div>` — Vue mounts but renders nothing. No console errors. Chrome `--dump-dom` shows empty `<div id="app">`.

**Root cause**: `element-plus/dist/index.css` provides styles, `@element-plus/icons-vue` provides icons, but the actual component registration ONLY happens via `app.use(ElementPlus)`.

**Correct `main.ts`**:
```typescript
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)
app.use(ElementPlus)  // ← THIS IS REQUIRED
app.use(pinia)
app.use(router)
app.mount('#app')
```

**Common mistake** — missing the `app.use(ElementPlus)` line while having the CSS import and icon registration. This is especially easy to miss because:
1. CSS imports make it look like Element Plus is configured
2. Icon registration (`app.component(key, component)`) works independently
3. No runtime error is thrown — components just don't render

**Verification**: After building, check the rendered DOM with headless Chrome:
```bash
google-chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=10000 --dump-dom "https://your-site/" 2>/dev/null | grep -c "el-"
```
If count is 0, Element Plus is not registered.

## CSS Auto-Import Limitation

`unplugin-vue-components` with `ElementPlusResolver` only auto-imports CSS for components used **in templates**. Programmatic calls need manual CSS imports in `main.ts`:

```typescript
// Required for ElMessageBox.confirm(), ElMessage(), ElNotification()
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-message.css'
```

**Symptom**: Dialog/message appears in top-left corner, no styling, broken layout.

## el-upload Modes

### `:action` mode (native upload)
Sends request directly via browser, **bypasses axios interceptors**. No Authorization header unless explicitly passed:

```vue
<el-upload :action="uploadUrl" :headers="authHeaders" ...>
```

Where `authHeaders` must be computed with the current token.

### `:http-request` mode (custom upload)
Gives you full control, can use axios. Preferred when auth is needed:

```vue
<el-upload :http-request="customUpload" ...>
```

## Programmatic vs Template Components

| Pattern | CSS Auto-imported? | Fix |
|---------|-------------------|-----|
| `<el-button>` in template | Yes | None |
| `ElMessage.success()` | No | Manual import in main.ts |
| `ElMessageBox.confirm()` | No | Manual import in main.ts |
| `ElNotification()` | No | Manual import in main.ts |

## md-editor-v3 Customization

The built-in image toolbar dropdown (upload/link/crop) **cannot be extended via props or slots**. Options:

1. **DOM injection**: After editor mounts, find the dropdown `<ul>` and append a custom `<li>` with click handler
2. **Replace with DropdownToolbar**: Hide built-in image button, create custom dropdown with all options
3. **Use NormalToolbar**: Add separate button next to image dropdown

## MinIO URL Handling Pattern

When using MinIO for file storage with relative paths in DB:

- **Write path**: Strip domain prefix before storing (`UrlNormalizeUtil.stripUrlPrefix`)
- **Read path**: Use `@MinioFile` annotation + `ResponseAdvice` to auto-prepend base URL
- **Frontend display**: Prepend `VITE_MINIO_URL` env var for relative paths
- **Ensure `/` prefix**: `stripUrlPrefix` must guarantee result starts with `/`

## Collapsible el-aside Sidebar Pattern

When an `el-aside` sidebar (e.g. conversation list, file tree, nav menu) takes up too much horizontal space, add collapse/expand support:

```vue
<el-aside :width="sidebarCollapsed ? '48px' : '280px'" style="transition: width 0.2s;">
  <div class="sidebar-header">
    <span v-if="!sidebarCollapsed">标题</span>
    <div style="display: flex; gap: 4px; margin-left: auto;">
      <el-button v-if="!sidebarCollapsed" type="primary" size="small" @click="createItem">
        <el-icon><Plus /></el-icon>
      </el-button>
      <el-button size="small" circle @click="sidebarCollapsed = !sidebarCollapsed">
        <el-icon><component :is="sidebarCollapsed ? 'Expand' : 'Fold'" /></el-icon>
      </el-button>
    </div>
  </div>
  <div v-if="!sidebarCollapsed" class="sidebar-content">
    <!-- list content -->
  </div>
</el-aside>

<script setup>
import { Expand, Fold } from '@element-plus/icons-vue'
const sidebarCollapsed = ref(false)
</script>
```

Key points:
- Use `:width` binding (dynamic) not `width` (static) on `el-aside`
- `transition: width 0.2s` for smooth animation
- `v-if="!sidebarCollapsed"` on content div to fully hide (not just CSS overflow)
- Header buttons hidden when collapsed via `v-if="!sidebarCollapsed"`
- Collapse/expand button always visible (no v-if on it)
- Icons: `Expand` (collapsed → expand) / `Fold` (expanded → fold)
- Both icons must be imported from `@element-plus/icons-vue`

## el-upload as Local File Reader (No Upload)

Use `before-upload` + `FileReader` + `return false` to read file content client-side without sending to server. Common for importing TSV/CSV/text data:

```vue
<el-upload :show-file-list="false" :before-upload="handleFileRead" accept=".tsv,.csv,.txt">
  <el-button>导入文件</el-button>
</el-upload>
```

```ts
const handleFileRead = (file: File) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result as string
    if (!content?.trim()) {
      ElMessage.warning('文件内容为空')
      return
    }
    // Use content (e.g. fill form, preview, parse TSV)
    formContent.value = content.trim()
    formName.value = file.name.replace(/\.(tsv|csv|txt)$/i, '')
  }
  reader.readAsText(file)
  return false // CRITICAL: prevents el-upload from uploading
}
```

**Key**: `return false` in `before-upload` prevents the actual HTTP upload. Without it, el-upload tries to POST the file.

**Drag-drop variant** — use `<el-upload drag>` inside a dialog for a drop zone:

```vue
<el-dialog v-model="visible" title="导入文件">
  <div v-if="!content">
    <el-upload drag :show-file-list="false" :before-upload="handleFileRead" accept=".tsv,.csv,.txt">
      <el-icon style="font-size: 40px; color: #c0c4cc"><Upload /></el-icon>
      <div>拖拽文件到此处，或点击上传</div>
    </el-upload>
  </div>
  <div v-else>
    <div>已读取：{{ fileName }}（{{ content.split('\n').length }} 行）</div>
    <el-input v-model="content" type="textarea" :rows="8" readonly />
  </div>
</el-dialog>
```

## el-dialog @close Handler for Draft Save/Restore

When implementing draft auto-save in an `el-dialog`, the `@close` event is critical. Element Plus dialogs can close via:
1. Clicking the X button
2. Clicking the overlay (mask)
3. Setting `v-model` to false programmatically

**Problem**: Button click handlers (`@click="handleCancel"`) only fire for the cancel button. X button and overlay click set `dialogVisible = false` directly WITHOUT triggering the cancel handler. Draft is not saved.

**Pattern**:
```vue
<el-dialog v-model="dialogVisible" @close="handleDialogClose">
```

```ts
const submitted = ref(false)

// Called by cancel button
const handleCancel = () => {
  if (!isEdit.value && !submitted.value) saveDraft()
  dialogVisible.value = false
}

// Called by X button / overlay / programmatic close
const handleDialogClose = () => {
  if (!isEdit.value && !submitted.value) saveDraft()
}

// On successful submit, set flag BEFORE clearing draft
const handleSubmit = async () => {
  // ... API call ...
  submitted.value = true  // Must be before clearDraft()
  clearDraft()
  dialogVisible.value = false
}

// Reset flag when opening dialog
const handleCreate = () => {
  submitted.value = false
  // ... clear form, restore draft ...
}
```

**Why `submitted` flag is needed**: Setting `dialogVisible = false` programmatically in `handleSubmit` ALSO triggers `@close`. Without the flag, `handleDialogClose` would re-save the draft after clearing it.

## Multi-Select with Comma-Separated Storage

When a field needs to store multiple values (e.g. multiple organisms, genome versions) but the database uses a single VARCHAR column:

**Backend**: Store as comma-separated string (e.g. `"mouse,human"`).

**Frontend**: Use a parallel array field for the multi-select binding:

```ts
const formData = reactive({
  organism: '',           // comma-separated string (API/DB)
  organismArray: [] as string[],  // array (el-select binding)
})

// Edit: parse string to array
formData.organismArray = row.organism ? row.organism.split(',').filter(Boolean) : []

// Create: reset both
formData.organism = ''
formData.organismArray = []

// Submit: convert array back to string
const submitData = { ...formData, organism: formData.organismArray.join(',') }

// Draft save: use array
const draft = { organism: formData.organismArray.join(',') }

// Draft restore: parse back
formData.organismArray = draft.organism ? draft.organism.split(',').filter(Boolean) : []
```

**Template**: Use `multiple` on el-select. When many options may accumulate, add `collapse-tags` to prevent the form from expanding:
```vue
<el-select v-model="formData.organismArray" filterable allow-create multiple
  collapse-tags collapse-tags-tooltip :max-collapse-tags="2">
```
- `collapse-tags` — collapses extra tags into a "+N" counter
- `collapse-tags-tooltip` — shows all selected items on hover
- `:max-collapse-tags="2"` — show at most2tags before collapsing

**Display**: Split and iterate:
```vue
<el-tag v-for="org in project.organism.split(',').filter(Boolean)" :key="org">
  {{ org.trim() }}
</el-tag>
```

## Pitfalls

- Don't use `headers: { 'Content-Type': undefined }` in el-upload HTTP requests — it may interfere with Authorization header injection
- `ElMessage` positioning: default is top-center. If it appears elsewhere, check for CSS overrides on `.el-message` or `.el-overlay`
- When replacing `ElNotification` with `ElMessage`, also clean up `h()` virtual DOM imports if no longer needed
- **Checkbox alignment**: Custom `el-checkbox__inner::after` styles with `left:0; right:0; top:0; bottom:4px; margin:auto` cause vertical misalignment. Use `left:50%; top:50%; transform:translate(-50%, -60%) rotate(45deg)` instead.
- **ElNotification → ElMessage migration**: `ElNotification` creates card-style popups in the corner. For operation feedback, use `ElMessage.success/error/warning` (lightweight toast, top center). Remove `h()` imports if no longer needed. Check for duplicate `import { ElMessage }` after batch replacement.
- **Table row selection indicator**: If a table row's selection highlight line appears misaligned (too high), add CSS to remove the bottom border on selected rows: `td.el-table__cell { border-bottom: none !important; }` scoped under `.el-table__body-wrapper .el-table__row`.
- **el-image "加载失败"**: When `el-image` shows "加载失败" (load failed), the `src` is likely a relative path (e.g. `/my-bucket/xxx.jpg`) without the full domain. For MinIO-stored images, prepend the base URL: `getFullUrl(item.filePath)` where `getFullUrl` adds `VITE_MINIO_URL` env var. Check `.env.production` has the variable properly set (no missing newlines from `echo >>` appends).
- **Field naming after API migration**: When switching from old API to new API, field names may differ (e.g. `photoSrc` → `filePath`, `photoName` → `fileName`). After changing API endpoints, grep the template for ALL `item.xxx` field references and verify they match the new response structure.
