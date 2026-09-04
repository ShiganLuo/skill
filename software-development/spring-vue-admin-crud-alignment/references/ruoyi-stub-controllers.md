# RuoYi Template Stub Controllers

## Problem

RuoYi-Vue-Plus admin template frontend calls ~90 endpoints across `/system/*`, `/monitor/*`, `/tool/*` modules (dept, role, menu, config, dict, post, notice, job, cache, server, logininfor, operlog, online, gen). These modules require 10+ database tables and extensive CRUD logic. For a blog project, these are unnecessary but their absence causes 404 warnings and can trigger token refresh loops.

## Solution

Create stub controllers in `controller/stub/` package that return empty/default data. Each controller handles one module's CRUD endpoints.

## Modules to Stub (16 controllers)

| Module | Base Path | Response Shape |
|--------|-----------|----------------|
| Notice | `/api/system/notice` | `{rows: [], total: 0}` |
| Role | `/api/system/role` | `{rows: [], total: 0}` + `authUser/*`, `optionselect`, `deptTree/{id}` |
| Dept | `/api/system/dept` | `List<Map>` directly (no wrapper) |
| Menu | `/api/system/menu` | `List<Map>` for list/treeselect; `{checkedKeys, menus}` for roleMenuTreeselect |
| Config | `/api/system/config` | `{rows: [], total: 0}` + `refreshCache` DELETE |
| Post | `/api/system/post` | `{rows: [], total: 0}` |
| Dict Type | `/api/system/dict/type` | `{rows: [], total: 0}` + `optionselect`, `refreshCache` |
| Dict Data | `/api/system/dict/data` | Standard CRUD |
| User (extras) | `/api/system/user` | Only stubs NOT in AdminUserController |
| Server | `/api/monitor/server` | `{cpu, mem, jvm, sys, sysFiles}` |
| Cache | `/api/monitor/cache` | `{info, commandStats}` + `getNames`, `getKeys`, `getValue`, `clearCache*` |
| Logininfor | `/api/monitor/logininfor` | `{rows, total}` + `clean`, `unlock/{userName}` |
| Operlog | `/api/monitor/operlog` | `{rows, total}` + `clean` |
| Online | `/api/monitor/online` | `{rows, total}` + `forceLogout/{tokenId}` |
| Job | `/api/monitor/job` | `{rows, total}` + `changeStatus`, `run/{id}`, `jobLog/*` |
| Tool Gen | `/api/tool/gen` | `{rows, total}` + `db/list`, `importTable`, `createTable`, `batchGenCode` |
| Auth | `/api/getInfo`, `/api/logout` | `{user, roles: ["admin"], permissions: ["*:*:*"]}` |

## Critical Pitfalls

1. **Response shapes differ per module**: `dept/list` and `menu/list` return `List<Map>` directly; `role/list` and `notice/list` return `{rows: [], total: 0}`. If the frontend table renders empty, check which shape it expects.

2. **HTTP methods matter**: `dict/type/refreshCache` and `config/refreshCache` are DELETE, not POST. `role/authUser/cancelAll` and `selectAll` use `@RequestParam`, not `@RequestBody`.

3. **Auth stub `/api/getInfo`** must return `roles` and `permissions` arrays or the frontend permission system breaks.

4. **`tool/gen/batchGenCode`** returns a file download (void return with response output stream), not `ApiResponse`.

5. **Dict data API path**: Frontend calls `/admin/settings/getDictSetting/{type}` (already implemented) for list, but `/system/dict/data/{dictCode}` for get-by-id.

## Frontend API Path Alignment

For blog-specific APIs, the frontend template may use paths like `/blog/tag/admin/tags` that don't match the actual backend at `/api/admin/tags/list`. Fix the **frontend API files** (`src/api/blog/*.ts`) to match backend controller paths — it's less invasive than changing backend controllers.

Common mismatches:
- Frontend: `/blog/tag/admin/tags` → Backend: `/api/admin/tags/list` (POST), `/api/admin/tags/create` (POST), `/api/admin/tags/{id}` (DELETE)
- Frontend: `/blog/category/admin/categories` → Backend: `/api/admin/categories/list` (POST), `/api/admin/categories/create` (POST), `/api/admin/categories/{id}` (DELETE)
- Frontend: `/blog/article/admin/delete` → Backend: `/api/admin/articles/updateArticlesDeletedStatus` (POST)
- Frontend: `/blog/photo/admin/photos` → Backend: `/api/front/images/getAllAlbum` (GET), `/api/admin/image/uploadImage` (POST)

## Verification

```bash
# Backend compiles
cd blog-springboot && mvn compile

# Count stub controllers
find src/main/java/.../controller/stub -name '*.java' | wc -l
# Should be >= 15

# Frontend APIs point to correct paths
grep -q '/admin/tags/list' blog-vue3-back/src/api/blog/tagApi.ts
```
