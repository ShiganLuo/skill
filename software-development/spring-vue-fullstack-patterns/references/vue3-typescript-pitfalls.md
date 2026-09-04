# Vue3 + Element Plus TypeScript Pitfalls

## Element Plus Namespace Errors (vue-tsc)

In Element Plus 2.9+ with `vue-tsc`, certain type imports are treated as namespaces rather than types:

```
error TS2709: Cannot use namespace 'FormInstance' as a type.
error TS2709: Cannot use namespace 'UploadInstance' as a type.
error TS2709: Cannot use namespace 'UploadFile' as a type.
```

**Affected types**: `FormInstance`, `FormRules`, `UploadInstance`, `UploadFile`, `FormContext`.

**Fix**: Replace with `any` or inline types:
```typescript
// WRONG
import type { FormInstance, FormRules } from 'element-plus'
const formRef = ref<FormInstance>()
const formRules: FormRules = { ... }

// CORRECT
const formRef = ref<any>()
const formRules: Record<string, any[]> = { ... }
```

For `UploadFile` as function parameter type, use `any`:
```typescript
const handleFileChange = (file: any) => { ... }
```

## el-table DefaultRow Type Casting

el-table's `#default` slot provides `row` as `DefaultRow`, NOT as your entity type. All event handlers in the template must cast:

```vue
<!-- WRONG — DefaultRow not assignable to Pipeline -->
<el-button @click="handleEdit(row)">编辑</el-button>

<!-- CORRECT — cast to entity type -->
<el-button @click="handleEdit(row as Pipeline)">编辑</el-button>
```

This applies to every `#default="{ row }"` slot in every `el-table-column`. Cast ALL rows used in click handlers, `@change`, etc.

## el-tag `:type` Return Type

Functions returning el-tag type must use the exact union, not `string`:

```typescript
// WRONG — returns string, not assignable to el-tag :type
const getStatusType = (status: string) => {
  const map: Record<string, string> = { SUCCESS: 'success', ... }
  return map[status] || 'info'
}

// CORRECT — explicit return type
const getStatusType = (status: string): 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = { ... }
  return map[status] || 'info'
}
```

## `null` vs `undefined` in Element Plus Props

Element Plus props use `undefined` for "not set", not `null`. TypeScript strict mode catches `null` assignable to `undefined`:

```typescript
// WRONG
:disabled="storageInfo && !storageInfo.canUpload"  // evaluates to null | boolean

// CORRECT — coerce null to boolean
:disabled="!!storageInfo && !storageInfo.canUpload"
```

For reactive form data, use `undefined` instead of `null`:
```typescript
// WRONG
const formData = reactive({ timeout: null as number | null })

// CORRECT
const formData = reactive({ timeout: undefined as number | undefined })
```

## PageResult Contract: Frontend-Backend Alignment

The `PageResult` pagination wrapper is shared across ALL list endpoints. Field names MUST match between backend Java record and frontend TypeScript interface.

**Backend** (`PageResult.java`):
```java
public record PageResult<T>(long total, int page, int size, List<T> records) {
    public static <T> PageResult<T> of(long total, int page, int size, List<T> records) {
        return new PageResult<>(total, page, size, records);
    }
}
```

**Frontend** (`projectApi.ts` / `pipelineApi.ts` / etc.):
```typescript
export interface PageResult<T> {
  records: T[]
  total: number
  page: number
  size: number
}
```

**Controller `@RequestParam` names must also match** — frontend sends `page`/`size`, backend must accept `page`/`size`:
```java
@GetMapping("/list")
public ApiResponse<PageResult> list(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "10") int size) { ... }
```

**Common mistake**: Backend uses `pageNum`/`pageSize` and `list`, frontend uses `page`/`size` and `records`. The frontend silently gets `undefined` for `res.records` → table shows empty with no error. Symptom: "创建成功但无法查看记录".

**Fix approach**: Align backend to frontend convention (`records`, `page`, `size`) since the frontend API types are consistent across all modules. One change to `PageResult.java` + all controllers fixes everything.

## Axios Interceptor Unwrap Anti-Pattern

When the axios response interceptor already unwraps `ApiResponse.result` (returns `response.data.result`), the API functions return the unwrapped data directly. Code like `res?.result || res` is WRONG — `res` has no `.result` property, so TypeScript errors fire.

```typescript
// WRONG — res is already unwrapped by interceptor
const data = res?.result || res
token.value = data.accessToken

// CORRECT — use res directly
token.value = res.accessToken
```

Also, **API type interfaces must use camelCase** to match Spring Boot's default Jackson serialization. `access_token` in the TypeScript interface when the backend sends `accessToken` causes silent failures.
