# Vue3 UI Patterns

## Inline Table Editing (No prompt/confirm/alert)

Browser-native `prompt()` is ugly and breaks Element Plus UI consistency. Never use `prompt()`, `alert()`, or `confirm()` in Vue/Element Plus apps.

### Add Column Without Prompt

```vue
// WRONG
const addColumn = () => {
  const colName = prompt('请输入列名:')
  if (!colName) return
  columns.value.push(colName)
}

// CORRECT: direct action, user edits inline
const addColumn = () => {
  columns.value.push('new_col')
  rows.value.forEach(row => row.push(''))
}
```

### Editable Table Headers

Replace `<span>{{ col }}</span>` with inline `<input>`:

```vue
<th v-for="(col, ci) in columns" :key="ci">
  <input v-model="columns[ci]" class="header-input" :disabled="isFixedColumn(col)" />
</th>
```

CSS:
```css
.header-input {
  border: 1px solid transparent;
  outline: none;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  width: 100%;
  min-width: 60px;
  padding: 2px 4px;
  border-radius: 3px;
}
.header-input:hover { border-color: #c0c4cc; }
.header-input:focus { border-color: #409eff; background: #fff; }
.header-input:disabled { color: #606266; cursor: not-allowed; }
```

## Multi-Delimiter Text Parsing

When accepting pasted table data (sample metadata, etc.), don't force exact TSV format. Auto-detect the delimiter from the first line:

```typescript
const detectDelimiter = (line: string): string => {
  const candidates = ['\t', ',', ';', '|']
  let best = '\t'
  let maxCount = 0
  for (const d of candidates) {
    const count = line.split(d).length - 1
    if (count > maxCount) {
      maxCount = count
      best = d
    }
  }
  return best
}

// Usage
const delimiter = detectDelimiter(lines[0])
const cells = line.split(delimiter).map(s => s.trim())
```

**UI labels**: Don't call it "TSV编辑" — use "文本编辑" with placeholder "支持制表符、逗号、分号、竖线等常见分隔符".

## Form Dialog Draft Auto-Save (localStorage)

When a create/edit dialog has many fields, closing it (accidentally or intentionally) loses all input. Save draft to localStorage on close, restore on reopen.

### Pattern

```typescript
const DRAFT_KEY = 'entity_create_draft'

const saveDraft = () => {
  if (isEdit.value) return  // NEVER save drafts for edit mode
  const draft = { name: formData.name, description: formData.description /* ... */ }
  // Only save if there's actual content
  if (draft.name || draft.description) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  }
}

const restoreDraft = (): boolean => {
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return false
  try {
    const draft = JSON.parse(raw)
    formData.name = draft.name || ''
    formData.description = draft.description || ''
    // ... restore all fields
    return true
  } catch { return false }
}

const clearDraft = () => { localStorage.removeItem(DRAFT_KEY) }

// Watch dialog close — save draft automatically
watch(dialogVisible, (newVal, oldVal) => {
  if (oldVal === true && newVal === false) saveDraft()
})
```

### Usage in handleCreate

```typescript
const handleCreate = () => {
  isEdit.value = false
  // Clear all fields first
  formData.name = ''
  formData.description = ''
  // Then try restoring draft
  restoreDraft()
  if (formData.name || formData.description) {
    ElMessage({ message: '已恢复上次未提交的草稿', type: 'info', duration: 2000 })
  }
  dialogVisible.value = true
}
```

### Clear on success

```typescript
// In handleSubmit, after successful creation:
await createProject(formData)
ElMessage.success('创建成功')
clearDraft()  // Only clear after successful submission
```

### Key rules
- **Edit mode never saves drafts** — only create mode
- **Only save non-empty drafts** — don't pollute localStorage with blank entries
- **Clear on success** — draft is consumed when creation succeeds
- **Show toast on restore** — user should know their input was recovered
- **Per-entity keys** — each entity type gets its own DRAFT_KEY (e.g. `project_create_draft`, `pipeline_create_draft`)
