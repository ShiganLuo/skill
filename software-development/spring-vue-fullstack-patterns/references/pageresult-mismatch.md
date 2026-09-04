# PageResult Field Name Mismatch (Critical)

Backend Java `PageResult` record fields must match what the frontend TypeScript `PageResult` interface expects. If they diverge, **all list pages silently return empty data** (no error, just `undefined`).

**Symptom**: Creation succeeds ("创建成功"), table shows nothing. Pagination shows `total: 0`.

**Root cause**: The axios interceptor unwraps `ApiResponse.result`, so the frontend receives the `PageResult` record directly. If the record field names don't match the TS interface, `res.records` is `undefined`.

**The bioplatform convention**:
- Backend `PageResult` record: `(long total, int page, int size, List<T> records)`
- Frontend TS interface: `{ records: T[], total: number, page: number, size: number }`
- Controller `@RequestParam`: `page` and `size` (NOT `pageNum`/`pageSize`)

**When adding a new list endpoint**, verify all three match:
1. `PageResult.of(total, page, size, list)` — Java record field order
2. `@RequestParam(defaultValue = "1") int page` — controller param names
3. `records: T[]` in the TS `PageResult` interface — frontend field name

If any module's `api/*.ts` still uses `pageNum`/`pageSize` or `list`, fix it to `page`/`size`/`records`.

# Plan-First Workflow for Major Redesigns

For **major feature redesigns** (new modules, architecture changes, multi-file refactors), the user prefers to review a written plan before any code changes. Write the plan to a markdown file (e.g. `docs/workflow-redesign.md`), present it, and wait for approval.

For **bug fixes and small improvements**, proceed directly — don't ask for plan approval.
