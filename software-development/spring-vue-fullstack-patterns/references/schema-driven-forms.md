# Schema-Driven Dynamic Form Rendering

When backend provides a JSON schema describing form fields, the frontend can render forms dynamically without hardcoding each field.

## Schema Format (Omics-style)

Omics uses **short type names** — `str`/`int`/`bool`/`dict`/`list`/`null`, NOT `string`/`integer`/`boolean`.

```json
{
  "fasta": { "type": "str", "path": "file", "nullable": true, "required": true, "description": "Reference genome FASTA" },
  "threads": { "type": "int", "required": false, "default": 4 },
  "skip_snp": { "type": "bool", "required": false, "default": false },
  "samples": { "type": "list", "required": true },
  "params": { "type": "dict", "required": false, "properties": { "quality": { "type": "int", "default": 25 } } },
  "ROOT_DIR": { "type": "null", "nullable": true, "required": false }
}
```

The `dict` fields like `env`, `Procedure`, `Params`, `genome` contain nested `properties`. The `Procedure` dict's children often have `type: "null"` (nullable tool paths) — these still render as text inputs because the parent dict has `properties`.

### Config Template Structure

The Omics `config/*.json` template files contain actual default values:
```json
{
    "env": { "env_dir": "/home/user/Database/env", "star": "/path/to/star.sif", ... },
    "Procedure": { "STAR": null, "samtools": null, ... },
    "Params": { "star": { "alignEndsType": "Local", "outFilterMismatchNmax": 10, ... } },
    "genome": { "default": "GRCm39", "references": { "GRCm39": { "fasta": "/path/to/genome.fa", ... } } },
    "paired_samples": [], "single_samples": [], "control_samples": []
}
```

When pre-filling the form from `configTemplate`, filter out system fields that are auto-computed at execution time: `ROOT_DIR`, `indir`, `outdir`, `logdir`, `raw_files`, `outfiles`.

## Schema → Element Plus Component Mapping

| schema.type | schema.path | Component | Notes |
|-------------|-------------|-----------|-------|
| str/string | file | `el-input` + file picker icon | path=file gets Document prepend |
| str/string | dir | `el-input` + folder icon | FolderOpened prepend |
| str/string | prefix | `el-input` | path prefix input |
| str/string | — | `el-input` | plain text |
| int/integer/number/float | — | `el-input-number` | min=0 |
| bool/boolean | — | `el-switch` | |
| list | — | dynamic `el-tag` + `el-input` | add via Enter, close via tag X |
| dict (with properties) | — | `el-collapse` → recursive `SchemaFormItem` | nested form group |
| null (nullable=true) | — | `el-input` (optional) | **Procedure tool paths**: null = "use default", user types to override. Schema: `{"type":"null","nullable":true}` |
| null (with properties) | — | render children | dict children that happen to be null but parent has properties |
| null (no properties, not nullable) | — | **skip** | system fields (ROOT_DIR, indir, outdir, logdir) |

## Component Architecture

```
SchemaForm.vue          ← top-level: iterates schema keys, filters nulls, emits update:model-value
  └── SchemaFormItem.vue ← renders one field by type, handles dict recursion
```

**Key design decisions:**
- Filter out `type=null` fields and known system fields (`raw_files`, `ROOT_DIR`, `indir`, `outdir`, `logdir`) at the top level
- `dict` fields use `el-collapse` with recursive `SchemaForm` inside
- All value changes emit through `update:model-value` — parent holds the state
- `SchemaFormItem` needs `export default { name: 'SchemaFormItem' }` for Vue recursive component resolution

## Workflow Template Import Pattern

When importing from an external config directory (e.g. `{repo}/config/`):

1. Scan for `*.json` files, skip `*.schema.json` and `schema.json`/`schema.schema.json`
2. For each `{Name}.json`, find matching `{Name}.schema.json`
3. Determine type by checking if `{repo}/subworkflow/{Name}.smk` exists (pipeline) or `{repo}/modules/{Name}/{Name}.smk` (task)
4. Read both files as strings, store in `configTemplate` and `schemaJson` columns
5. Use upsert logic: if template name exists, update config; otherwise insert

## Form Initialization from Template

```typescript
// Load template
const tpl = await getTemplate(templateId)
// Parse schema (might be string or object)
const schema = typeof tpl.schemaJson === 'string' ? JSON.parse(tpl.schemaJson) : tpl.schemaJson
// Initialize form data from template's default config, filtering system fields
const config = typeof tpl.configTemplate === 'string' ? JSON.parse(tpl.configTemplate) : tpl.configTemplate
const SYSTEM_FIELDS = ['ROOT_DIR', 'indir', 'outdir', 'logdir', 'raw_files', 'outfiles']
const filtered: Record<string, any> = {}
if (config) {
  for (const [key, val] of Object.entries(config)) {
    if (!SYSTEM_FIELDS.includes(key)) filtered[key] = val
  }
}
schemaFormData.value = filtered
```

**Why filter**: `ROOT_DIR`, `indir`, `outdir` etc. are computed from the project context at execution time, not user input. Pre-filling them would confuse users and potentially conflict with execution-time values.

**Pitfall: null vs undefined for EP props**: Element Plus component props typed as `string | number | boolean | undefined` reject `null`. Use `undefined` for optional refs:
```typescript
// WRONG: ref<number | null>(null)  → TS2322 on el-radio-group v-model
// RIGHT: ref<number | undefined>(undefined)
```

## Three-Step Create Flow

For template-driven creation (type → template → form):

```
Step 0: Type selection (task / pipeline) — radio cards
Step 1: Template selection — load templates filtered by type, radio buttons
Step 2: Dynamic form — SchemaForm renders from schema, user fills in
```

Use `el-steps` for progress indication. Store `selectedType`, `selectedTemplateId`, and `schemaFormData` as separate refs.

## JSON Editor Fallback

Schema-driven forms can't cover every parameter (incomplete schemas, dynamic keys like genome references). Always provide a JSON editor toggle:

```vue
<el-divider>
  配置参数
  <el-button size="small" :icon="Edit" @click="jsonEditMode = !jsonEditMode">
    {{ jsonEditMode ? '表单模式' : 'JSON 编辑' }}
  </el-button>
</el-divider>
<SchemaForm v-if="!jsonEditMode" ... />
<el-input v-if="jsonEditMode" v-model="jsonEditText" type="textarea" :rows="18" style="font-family: monospace" />
```

Sync logic:
- Toggle ON → serialize `schemaFormData` to `jsonEditText`
- Toggle OFF → parse `jsonEditText` back to `schemaFormData` (show error if invalid JSON, stay in edit mode)
- On submit → if in JSON edit mode, parse `jsonEditText` as final config

## DB Schema Migration

After modifying the `.sql` schema file, the live database does NOT auto-update. Always run ALTER TABLE / CREATE TABLE against the live MySQL container before testing:

```bash
docker exec bioplatform-mysql mysql -uroot -p'bioplatform123' bioplatform -e "ALTER TABLE ..."
```

**Pattern**: The `.sql` file is the source of truth for fresh installs, but live databases need explicit DDL statements.
