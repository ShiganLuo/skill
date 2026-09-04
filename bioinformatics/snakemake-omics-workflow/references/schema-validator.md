# SchemaValidator — Config Schema Validation, Type Casting & Test Path Generation

## Overview

`src/common/util/SchemaValidatorUtil.py` provides:
1. **Config validation** — `validate()` checks required/nullable
2. **Path field discovery** — `get_path_fields()` finds all `path: "file"/"dir"/"prefix"` fields
3. **Test path generation** — `generate_test_paths()` creates placeholder files for dry-run
4. **CLI extra_args type casting** — `cast_extra_args()` casts CLI values to schema-declared types + validates paths
5. **Field type lookup** — `get_field_type(dotted_key)` resolves schema type for any dotted key path

Each workflow has `config/<Workflow>.schema.json` mirroring its `config/<Workflow>.json`.

## Schema File Structure

```json
{
  "ROOT_DIR": {"type": "null", "nullable": true, "required": false},
  "indir":    {"type": "null", "nullable": true, "required": false},
  "paired_samples": {"type": "list", "required": true},
  "genome": {
    "fasta": {"type": "str", "path": "file", "nullable": true, "required": false},
    "gtf":   {"type": "str", "path": "file", "nullable": true, "required": false},
    "hisat2_index_prefix": {"type": "str", "path": "prefix", "nullable": true, "required": false},
    "star_index_dir":      {"type": "str", "path": "dir",    "nullable": true, "required": false}
  },
  "Params": {
    "macs3": {
      "pvalue": {"type": "str", "required": false},
      "bw": {"type": "int", "required": false}
    }
  }
}
```

### Field properties

| Key | Values | Meaning |
|-----|--------|---------|
| `type` | `str`, `list`, `int`, `float`, `bool`, `null`, `dict` | Expected Python type |
| `path` | `file`, `dir`, `prefix` (omit for non-paths) | Path classification |
| `nullable` | `true`/`false` | Whether `None` is acceptable |
| `required` | `true`/`false` | Whether field must exist and be non-empty |

### Path type semantics

- **file** — single file (fasta, gtf, BED, VCF, SIF container)
- **dir** — directory (star_index_dir, cellranger_ref_dir)
- **prefix** — multi-file index prefix (hisat2 8-file, bowtie2 6-file, bwa-mem2 5-file)

### Genome structure styles

Three styles exist across workflows:

| Style | Structure | Workflows |
|-------|-----------|-----------|
| A (properties) | `genome.properties.references.additionalProperties.properties.fasta` | RNAseq, scRNAseq |
| B (direct) | `genome.fasta` | CLIP, MERIP, Mutation, PacVar, PeakCalling, QuantMS, ncRNAseq, tRNAseq, KARRseq |
| C (genome name) | `genome.GRCm39.fasta` | CoCulture |

`get_field_type()` handles all three via `_resolve_field()` which checks:
1. `node["properties"][key]` — Style A
2. `node["additionalProperties"]["properties"][key]` — dynamic keys
3. `node[key]` — Style B/C direct access

## API — Validation & Path Discovery

```python
from src.common.util.SchemaValidatorUtil import SchemaValidator

sv = SchemaValidator()
sv._schema_dir = "/path/to/Omics/config"
sv.load("config/RNAseq.schema.json")  # or sv.load_workflow("RNAseq")

# Get all path-type fields
fields = sv.get_path_fields()
# {"genome.fasta": {"type": "str", "path": "file", ...}, ...}

# Validate config
errors = sv.validate(config_dict)

# Generate test paths (scans ALL *.schema.json)
mapping = sv.generate_test_paths("assests/test/data", "GRCm39")
```

## API — Type Casting (cast_extra_args)

```python
sv.load_workflow("RNAseq")

# Cast CLI extra_args to schema-declared types
extra_args = {
    "Params.function.enabled": "true",          # str → bool True
    "Params.star_TEtranscripts.outFilterMultimapNmax": "10",  # str → int 10
    "counters": "STARsolo",                      # str → list ["STARsolo"]
    "Procedure.STAR": "/nonexistent/star.sif",   # path=file check
}
casted, errors = sv.cast_extra_args(extra_args)
# casted: {"Params.function.enabled": True, "counters": ["STARsolo"], ...}
# errors: ["字段 'Procedure.STAR' path=file，文件不存在: '/nonexistent/star.sif'"]
```

### Type casting rules

| schema type | Casting behavior | Error condition |
|-------------|-----------------|-----------------|
| `list`/`array` | Single value → `[value]`; recurses with `items.type` | — |
| `int` | `int(value)` | Non-numeric string |
| `float` | `float(value)` | Non-numeric string |
| `bool` | `true/false/yes/no/1/0` (case-insensitive) | Anything else |
| `str` | Pass through | Never errors |
| `dict`/`object` | `json.loads(value)` | Invalid JSON |
| `null` | Pass through | Non-nullable + empty |
| (not in schema) | `smart_cast()` fallback | Never errors |

### Path validation

After type casting, if the field has `path` constraint:
- `path=file` → `os.path.isfile(value)`
- `path=dir` → `os.path.isdir(value)`
- `path=prefix` → infers tool from field name, checks `INDEX_MAP` extensions

INDEX_MAP (class-level constant):
```python
INDEX_MAP = {
    "hisat2": [".1.ht2", ".2.ht2", ..., ".8.ht2"],
    "bwaMem2": [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"],
    "bowtie2": [".1.bt2", ".2.bt2", ".3.bt2", ".4.bt2", ".rev.1.bt2", ".rev.2.bt2"],
    "bowtie2_for_rRNA": [same as bowtie2],
}
```

Tool name inference: longer names preferred (`bowtie2_for_rRNA` over `bowtie2`).

### get_field_type() — Three-level field lookup

```python
sv.get_field_type("Params.star.outFilterMultimapNmax")  # → {"type": "int", ...}
sv.get_field_type("counters")                             # → {"type": "list", ...}
sv.get_field_type("unknown_key")                          # → None (falls back to smart_cast)
```

Traversal logic in `get_field_type()`:
1. Split dotted key into parts
2. For each intermediate part, call `_resolve_field(node, part)`:
   - Check `node["properties"][part]` (Style A)
   - Check `node["additionalProperties"]["properties"][part]` (dynamic keys)
   - Check `node[part]` (Style B/C)
3. If resolved has child keys (non-meta), step into it (handles `type: "dict"` containers)
4. If resolved is a pure leaf (no child keys), stop
5. Resolve final segment → return field definition dict or None

**Pitfall — `type: "dict"` with children:** A node like `{"type": "dict", "qc": {...}, "cluster": {...}}` is a container, not a leaf. The traversal checks for non-meta child keys to distinguish.

## API — Integration with run.py

In `execute_workflows()`, before injecting extra_args into workflow_config:

```python
if args.schema_validate and args.extra_args:
    sv = SchemaValidator()
    sv._schema_dir = os.path.join(root_dir, "config")
    try:
        sv.load_workflow(wf_name)
        casted, errors = sv.cast_extra_args(args.extra_args)
        if errors:
            for err in errors:
                logger.error(f"[{wf_name}] 参数校验失败: {err}")
            raise ValueError(f"extra_args 校验失败，共 {len(errors)} 个错误")
        args.extra_args = casted
    except FileNotFoundError:
        pass  # No schema → fallback to smart_cast
```

CLI flag: `--no-schema-validate` disables this (default: enabled).

**`smart_cast()` moved to SchemaValidatorUtil.py** — imported in run.py as:
```python
from src.common.util.SchemaValidatorUtil import SchemaValidator, smart_cast
```

## Schema sync workflow

When schema is out of sync with actual config JSON:

1. Run comparison script to find mismatches
2. Use `deep_sync()` to auto-fix (adds missing fields, removes stale required fields)
3. Skip `env`/`container` keys (runtime-injected, environment-specific)
4. Re-run comparison to verify

Key principle: **schema mirrors config structure exactly.** No inheritance, no merging.

## Constraint validation (5 types)

`cast_extra_args()` applies constraints in this order:

| # | Constraint | Function | Trigger |
|---|-----------|----------|---------|
| 1 | **type** | `_cast_scalar` | Schema declares `type` |
| 2 | **nullable** | inline | Schema declares `nullable: false` |
| 3 | **path** | `_validate_path` | Schema declares `path: file/dir/prefix` |
| 4 | **enum** | `_validate_enum` | Schema declares `enum: [...]` |
| 5 | **range** | `_validate_range` + `_infer_range` | Schema declares `minimum`/`maximum` OR field name matches `_RANGE_PATTERNS` |

**Schema-unknown fields** (get_field_type returns None): only smart_cast, no constraints.

### Enum — schema declares `enum: [...]`
### Range — two sources: explicit `minimum`/`maximum` in schema, or inferred from `_RANGE_PATTERNS` (field name substrings → bounds). Patterns: resolution/fdr/pvalue/p_adj/doublet_rate→[0,1], min_genes/threads/top/threshold→[1,∞]. To extend: append to `_RANGE_PATTERNS`.

## Pitfalls

1. **Schema must mirror config structure** — CoCulture has `genome.GRCm39.fasta` (nested), RNAseq has `genome.properties.references` (Style A). Each schema is self-contained.
2. **`smart_cast` is now in SchemaValidatorUtil** — not in run.py. Import from `src.common.util.SchemaValidatorUtil`.
3. **Three genome structure styles** — `_resolve_field` handles all three via properties/additionalProperties/direct lookup.
4. **`type: "dict"` containers** — nodes with both `type` and child keys are containers, not leaves. `get_field_type` traverses into them.
5. **Path validation checks existence** — `path=file` calls `os.path.isfile()`, `path=prefix` checks index files. Schema may lack `path` for some str fields — those skip validation.
6. **`env`/`container` fields are runtime-injected** — don't add to schema comparison.
7. **Schema-unknown fields get no constraint validation** — only smart_cast. Don't apply range/enum inference to fields not in schema (would produce false positives).
8. **Tool name inference for prefix** — prefers longer match (`bowtie2_for_rRNA` over `bowtie2`). Uses `sorted(INDEX_MAP, key=len, reverse=True)`.
