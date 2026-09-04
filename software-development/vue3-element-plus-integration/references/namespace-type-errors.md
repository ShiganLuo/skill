# Element Plus TypeScript Namespace Errors (vue-tsc)

In Element Plus 2.9+ with `vue-tsc` 2.2+, certain type imports are treated as namespaces rather than types:

```
error TS2709: Cannot use namespace 'FormInstance' as a type.
error TS2709: Cannot use namespace 'UploadInstance' as a type.
error TS2709: Cannot use namespace 'UploadFile' as a type.
```

**Affected types**: `FormInstance`, `FormRules`, `UploadInstance`, `UploadFile`, `FormContext`.

This is a known compatibility issue between Element Plus type exports and vue-tsc's type resolution.

**Fix**: Replace with `any` or inline types:

```typescript
// WRONG — vue-tsc treats these as namespaces
import type { FormInstance, FormRules } from 'element-plus'
const formRef = ref<FormInstance>()
const formRules: FormRules = { ... }

// CORRECT — use any or inline types
const formRef = ref<any>()
const formRules: Record<string, any[]> = { ... }
```

For `UploadFile` as function parameter type:
```typescript
const handleFileChange = (file: any) => { ... }
```

For `validate` callback parameter:
```typescript
// WRONG
await formRef.value.validate(async (valid) => { ... })

// CORRECT — explicit type
await formRef.value.validate(async (valid: boolean) => { ... })
```

## el-tag :type Return Type

Functions used as el-tag `:type` binding must return an explicit union, not `string`:

```typescript
// WRONG — returns string, vue-tsc rejects
const getStatusType = (status: string) => {
  const map: Record<string, string> = { SUCCESS: 'success', FAILED: 'danger' }
  return map[status] || 'info'
}

// CORRECT — explicit union return type
const getStatusType = (status: string): 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    SUCCESS: 'success', RUNNING: 'warning', FAILED: 'danger', PENDING: 'info'
  }
  return map[status] || 'info'
}
```

The `''` (empty string) is NOT a valid el-tag type — omit it from the union.

## el-table DefaultRow Type Casting

In el-table template slots, `row` is typed as `DefaultRow` (internal Element Plus type), not your entity type. Cast it in template event handlers:

```vue
<!-- WRONG — DefaultRow not assignable to DataFile -->
<el-button @click="handleDelete(row)">删除</el-button>

<!-- CORRECT — cast to entity type -->
<el-button @click="handleDelete(row as DataFile)">删除</el-button>
```

This applies to ALL el-table-column template `#default="{ row }"` slots that pass `row` to typed function parameters.

## null vs undefined for Optional Props

Element Plus props typed as `T | undefined` reject `null`. When using `number | null` for reactive form data that feeds into API calls:

```typescript
// WRONG — null not assignable to number | undefined
const formData = reactive({ timeout: null as number | null })

// CORRECT — use undefined
const formData = reactive({ timeout: undefined as number | undefined })
```

When spreading searchForm into API params, convert null to undefined:
```typescript
const res = await listFiles({
  projectId: searchForm.projectId ?? undefined,
  fileName: searchForm.fileName
})
```
