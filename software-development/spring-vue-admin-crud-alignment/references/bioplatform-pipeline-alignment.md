# Bioplatform Pipeline Module Alignment Fix

## Symptom
Admin pipeline page: "新建流程" shows "创建成功" but the table is always empty.

## Root Causes (3 independent mismatches)

### 1) PageResult record field names
Backend `PageResult` Java record:
```java
public record PageResult<T>(long total, int pageNum, int pageSize, List<T> list)
```
Frontend TS `PageResult<T>`:
```typescript
{ records: T[]; total: number; page: number; size: number }
```
Axios interceptor unwraps `response.data.result` → frontend receives `{total, pageNum, pageSize, list}` → `res.records` is `undefined` → table empty.

**Fix**: Rename Java record components: `list→records, pageNum→page, pageSize→size`. This affects ALL modules since `PageResult` is shared.

### 2) Controller @RequestParam naming
All controllers used `@RequestParam(defaultValue="1") int pageNum` / `int pageSize`.
Frontend sends `?page=1&size=10`.
Spring silently uses defaults (1, 10) — no error, but filtering/pagination doesn't work as expected.

**Fix**: Rename in ALL controllers at once:
- `AdminPipelineController`
- `AdminProjectController`
- `AdminExecutionController`
- `AdminDataFileController`
- `AdminLogController`
- `AdminUserController`
- `FrontPipelineController`
- `FrontProjectController`

### 3) DTO field completeness
`AdminPipelineCreateRequest` had only `(name, description, projectId)`.
Backend entity `Pipeline` has: `id, name, description, category, configJson, dockerImage, timeout, ownerId, createdAt, updatedAt`.
Frontend form sent `category`, `configJson`, `dockerImage`, `timeout` — all silently ignored by Jackson.

**Fix**: Expand DTO to include all entity fields, update both `createPipeline()` and `updatePipeline()` service methods, and fix controller's update handler that manually constructs CreateRequest from UpdateRequest.

### 4) Frontend TS interface mismatch
Frontend `Pipeline` interface had `version`, `config`, `status`, `createTime`, `updateTime` — none exist in the entity.
Correct fields: `configJson`, `dockerImage`, `timeout`, `ownerId`, `createdAt`, `updatedAt`.

**Fix**: Update `pipelineApi.ts` Pipeline interface, update `PipelineView.vue` table columns and form fields.

## Verification
```bash
cd bioplatform-springboot && mvn compile -q          # backend
cd bioplatform-vue3/bioplatform-admin && npm run build  # admin frontend
cd bioplatform-vue3/bioplatform-front && npm run build  # public frontend
```

## Key lesson
When one admin module's CRUD is broken, audit ALL modules — the same class of error (field name mismatch, param naming) typically affects every module sharing the same DTO/interceptor pattern.

## Phase 2: Workflow Template Redesign

After the initial CRUD fix, the pipeline module was redesigned to support template-driven creation:

### New table: `workflow_templates`
```sql
CREATE TABLE workflow_templates (
    id BIGINT AUTO_INCREMENT, name VARCHAR(128), description TEXT,
    type VARCHAR(16),          -- 'task' or 'pipeline'
    category VARCHAR(64),      -- 转录组, 变异检测, etc.
    config_template JSON,      -- from Omics/config/{Name}.json
    schema_json JSON,          -- from Omics/config/{Name}.schema.json
    snakemake_path VARCHAR(255), icon VARCHAR(64), sort_order INT,
    enabled TINYINT(1), created_at DATETIME(6), updated_at DATETIME(6)
);
```

### `pipelines` table additions
```sql
ALTER TABLE pipelines ADD COLUMN type VARCHAR(16) NOT NULL DEFAULT 'pipeline' AFTER name;
ALTER TABLE pipelines ADD COLUMN template_id BIGINT DEFAULT NULL AFTER type;
ALTER TABLE pipelines ADD CONSTRAINT fk_pipelines_template FOREIGN KEY (template_id) REFERENCES workflow_templates(id);
```

### Full-stack changes
- Backend: new `WorkflowTemplate` entity/DTO/mapper/service/controller
- Backend: `Pipeline` entity/DTO/service updated with `type` + `templateId`
- Frontend: `templateApi.ts`, `SchemaForm.vue`, `SchemaFormItem.vue`, `TemplateView.vue`
- Frontend: `PipelineView.vue` rewritten with 3-step create flow (type → template → form)
- Router: new route `/system/templates` in system management submenu

### Pitfall: ALTER TABLE on running Docker MySQL
After updating `bioplatform.sql`, the actual Docker MySQL doesn't auto-migrate. Must run:
```bash
docker exec bioplatform-mysql mysql -uroot -p'bioplatform123' bioplatform -e "ALTER TABLE ..."
docker exec bioplatform-mysql mysql -uroot -p'bioplatform123' bioplatform -e "CREATE TABLE IF NOT EXISTS ..."
```
Verify with `DESCRIBE pipelines;` and `DESCRIBE workflow_templates;`.

### Pitfall: vue-tsc null vs undefined for EP props
`el-radio-group` v-model and `el-select` v-model reject `null` — use `undefined`:
```typescript
// WRONG: ref<number | null>(null)
// RIGHT: ref<number | undefined>(undefined)
```
Also affects `el-button :disabled` with boolean expressions that can be `null | boolean`.

### Pitfall: el-table DefaultRow cast
`el-table` template `#default="{ row }"` types `row` as `DefaultRow`, not the custom entity type. Cast in template:
```vue
<el-button @click="handleEdit(row as Pipeline)">编辑</el-button>
```

### Terminology
User preference: use English `task`/`pipeline` in UI, not Chinese translations (单任务/流水线).
