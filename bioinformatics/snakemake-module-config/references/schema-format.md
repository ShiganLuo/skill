# Omics Config Schema Format (Custom, NOT JSON Schema)

Each workflow has a `config/<Workflow>.schema.json` file validated by
`src/common/util/SchemaValidatorUtil.py`. This is a **custom format** —
do NOT use JSON Schema (draft-07) syntax.

## Field definition structure

Each field is a dict with these keys:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `type` | str | yes | One of: `str`, `int`, `float`, `bool`, `null`, `list`, `array`, `object`, `dict` |
| `required` | bool | yes | Whether the field must be present |
| `nullable` | bool | no | Whether null is accepted (default: True per validator) |
| `path` | str | no | `"file"`, `"dir"`, or `"prefix"` — marks as a filesystem path |
| `description` | str | no | Human-readable description (not used by validator) |

## Example

```json
{
  "ROOT_DIR": {
    "type": "null",
    "nullable": true,
    "required": false
  },
  "genome": {
    "type": "object",
    "required": true,
    "properties": {
      "default": {
        "type": "str",
        "nullable": false,
        "required": true
      },
      "references": {
        "type": "object",
        "required": true,
        "additionalProperties": {
          "type": "object",
          "properties": {
            "fasta": {
              "type": "str",
              "nullable": true,
              "required": false,
              "path": "file"
            }
          }
        }
      }
    }
  }
}
```

## Validator behavior

`SchemaValidator.validate(config)` checks:
1. Top-level fields (except `genome`) — required/nullable
2. `genome` section direct children — required/nullable

It does NOT recursively validate nested structures. The schema serves as:
- Documentation of expected structure
- Path field discovery for test data generation (`generate_test_paths()`)

## Common mistakes

### ❌ Using JSON Schema syntax
```json
// WRONG — this is JSON Schema draft-07
{ "$schema": "...", "type": "object", "properties": {...} }
```

### ❌ Using `["string", "null"]` type arrays
```json
// WRONG — JSON Schema style
{ "type": ["string", "null"] }
```

### ✅ Correct custom format
```json
// RIGHT — Omics custom format
{ "type": "str", "nullable": true, "required": false }
```

## Creating a new schema

1. Start from an existing schema (e.g., `RNAseq.schema.json`, `PeakCalling.schema.json`)
2. Mirror the config JSON structure
3. Mark file/dir paths with `"path": "file"` or `"path": "dir"`
4. Use `"type": "null", "nullable": true, "required": false` for optional fields
5. Validate: `SchemaValidator().load(schema_path).validate(config)` returns `[]`

## Reference files
- `config/schema.schema.json` — meta-schema showing the format's own structure
- `src/common/util/SchemaValidatorUtil.py` — validator implementation
