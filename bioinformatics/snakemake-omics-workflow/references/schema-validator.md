# SchemaValidator — Per-Workflow Config Schema Validation & Test Path Generation

## Overview

`src/common/SchemaValidator.py` validates workflow configs and generates test paths.
Each workflow has its own schema file: `config/<Workflow>.schema.json` that mirrors the config structure.

## Schema File Structure

Each `config/<wf>.schema.json` mirrors its `config/<wf>.json` structure:

```json
{
  "ROOT_DIR": {"type": "str", "path": "dir", "required": true, "nullable": false},
  "indir":    {"type": "str", "path": "dir", "required": true, "nullable": false},
  "outdir":   {"type": "str", "path": "dir", "required": true, "nullable": false},
  "logdir":   {"type": "str", "path": "dir", "required": true, "nullable": false},
  "samples":  {"type": "list", "required": true},
  "paired_samples": {"type": "list", "required": true},
  "single_samples": {"type": "list", "required": true},
  "outfiles": {"type": "list", "required": true},
  "genome": {
    "fasta": {"type": "str", "path": "file", "nullable": true, "required": false},
    "gtf":   {"type": "str", "path": "file", "nullable": true, "required": false},
    "hisat2_index_prefix": {"type": "str", "path": "prefix", "nullable": true, "required": false},
    "star_index_dir":      {"type": "str", "path": "dir",    "nullable": true, "required": false}
  }
}
```

For nested genome configs (CoCulture dual-species):
```json
{
  "genome": {
    "GRCm39": {
      "fasta": {"type": "str", "path": "file", "nullable": true, "required": true},
      "gtf":   {"type": "str", "path": "file", "nullable": true, "required": true}
    },
    "GRCh38": {
      "fasta": {"type": "str", "path": "file", "nullable": true, "required": true},
      "gtf":   {"type": "str", "path": "file", "nullable": true, "required": true}
    }
  }
}
```

### Field properties

| Key | Values | Meaning |
|-----|--------|---------|
| `type` | `"str"`, `"list"`, `"int"`, `"float"`, `"bool"`, `"null"` | Expected Python type |
| `path` | `"file"`, `"dir"`, `"prefix"` (omit for non-paths) | Path classification |
| `nullable` | `true`/`false` | Whether `None` is acceptable |
| `required` | `true`/`false` | Whether field must exist and be non-empty |

### Path type semantics

- **file** — single file (fasta, gtf, BED, VCF, etc.)
- **dir** — directory (star_index_dir, smallrna_star_index)
- **prefix** — multi-file index prefix (hisat2 8-file, bowtie2 6-file, bwa-mem2 5-file)

### Design principle

Schema mirrors config structure exactly. No inheritance, no merging, no overrides.
Each workflow is self-contained. If two workflows need different constraints for the same field,
each schema states its own constraints independently.

## API

```python
from src.common.SchemaValidator import SchemaValidator

sv = SchemaValidator()

# Set schema directory (for generate_test_paths which scans all *.schema.json)
sv._schema_dir = "/path/to/Omics/config"

# Or load specific workflow schema for validate/get_path_fields
sv.load("config/ncRNAseq.schema.json")

# Get all path-type fields from loaded schema
fields = sv.get_path_fields()
# {"genome.fasta": {"type": "str", "path": "file", ...}, ...}

# Validate config against loaded schema
errors = sv.validate(config_dict)
# [] if valid, ["Missing or empty required field: 'genome.fasta'"] if not

# Generate test paths (scans ALL *.schema.json in schema_dir)
mapping = sv.generate_test_paths("assests/test/data", "GRCm39")
# {"genome.fasta": "/abs/path/assests/test/data/ref/GRCm39.fa", ...}
```

## Inject ALL path fields recursively

The injection logic must handle ALL path-like values in the config, not just genome.* fields. This includes `Params.arriba.blacklist`, `Procedure.gatk`, etc.

```python
def _is_path(val):
    if val is None: return True
    if not isinstance(val, str): return False
    if "/" in val: return True
    return False

def _inject(cfg, prefix, wf_extra):
    """Recursively inject test paths for ALL path-like fields."""
    for field, val in cfg.items():
        dotted = f"{prefix}.{field}" if prefix else field
        if isinstance(val, dict):
            _inject(val, dotted, wf_extra)
        elif _is_path(val):
            wf_extra[dotted] = base_paths.get(dotted, _make_test_path(field, test_data, genome))

# In execute_workflows, per-workflow:
wf_extra = {}
_inject(workflow_config, "", wf_extra)
```

## Path injection with fallback

The injection logic in `execute_workflows` must handle fields NOT in schema:

```python
def _is_path_like(val):
    """Heuristic: does this value look like a file path?"""
    if val is None: return True       # null = needs to be filled
    if not isinstance(val, str): return False
    if "/" in val or "\\" in val: return True
    return False

def _resolve_test_path(field_name, test_data, genome):
    """Generate a test path for a field not in schema."""
    from pathlib import Path
    ref = Path(test_data) / "ref"
    ref.mkdir(parents=True, exist_ok=True)
    for name in ("smallrna", "rRNA", "access", "repeat", "decoy"):
        if name in field_name:
            return str(ref / name)
    return str(ref / genome)

# In execute_workflows, per-workflow:
for field, val in genome_cfg.items():
    if isinstance(val, dict): continue
    base_key = f"genome.{field}"
    if base_key in base_paths:          # schema knows this field
        wf_extra[base_key] = base_paths[base_key]
    elif _is_path_like(val):            # fallback: config value looks like a path
        wf_extra[base_key] = _resolve_test_path(field, test_data, genome)
```

## Schema generation from config JSONs

Schemas are auto-generated from config JSONs using recursive `build_schema()`:

```python
def build_schema(cfg):
    """Recursively build schema mirroring config structure."""
    schema = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            schema[k] = build_schema(v)  # recurse for Params, Procedure, genome, etc.
        else:
            schema[k] = make_leaf(k, v)  # leaf: type + path + nullable + required
    return schema
```

This handles arbitrary nesting depth: `Params.star_3pass.pass1.outFilterMultimapNmax`.

**Schema includes ALL sections:** top-level (ROOT_DIR, indir, etc.), genome, Params, Procedure.
The schema is a complete mirror of the config JSON — nothing omitted.

Path detection heuristics in `make_leaf()`:
- Key ends with `_prefix` → prefix type
- Key ends with `_dir` → dir type
- Key ends with `_index` AND contains "star" → dir type
- Key ends with `_index` → file type
- Value is null → `type: "null"`, `required: false`
- Value contains "/" → file type
- Known field names (fasta, gtf, fai, dict, bed, etc.) → file type
- Empty string `""` → `required: false`, no path
- `.jar` extension → file type (for Java tools like trimmomatic)

**Verification:** After generation, compare schema vs config with recursive diff to catch missing/extra keys.

## generate_test_paths output layout

```
assests/test/data/
  ref/
    GRCm39.fa                    # fasta
    GRCm39.gtf                   # gtf
    GRCm39.fai                   # fai
    GRCm39.dict                  # dict
    GRCm39.vcf.gz                # known_sites
    GRCm39.list                  # interval
    GRCm39.geneIDAnno            # geneIDAnno
    GRCm39.TE_gtf                # TE_gtf
    access.bed, repeat.bed, rRNA.fasta, ...
    smallrna.smallrna.fa         # smallRNA fasta
    smallrna.smallrna.bed        # smallRNA bed
    rRNA.rRNA.fasta              # rRNA fasta
  index/
    hisat2/GRCm39/               # 8 .ht2 files
    bowtie2/GRCm39/              # 6 .bt2 files
    bowtie2_for_rRNA/GRCm39/     # rRNA index
    bwaMem2/GRCm39/              # 5 files
    star/GRCm39/                 # directory (Genome, SA, SAindex)
    star/smallrna/               # smallRNA star index
```

## Adding a new genome field

1. Add entry to each relevant `config/<wf>.schema.json` under `genome`:
   ```json
   "new_field": {"type": "str", "path": "file", "nullable": true, "required": false}
   ```
2. Add the field to the corresponding `config/<wf>.json`
3. No Python code changes — `generate_test_paths()` picks it up automatically

## Pitfalls

1. **Schema must mirror config structure** — if config has `genome.GRCm39.fasta` (nested), the schema should have nested genome keys matching. The test framework reads the actual config structure for injection.

2. **Per-workflow means no shared overrides** — if ncRNAseq and RNAseq both require `genome.gtf`, each schema states it independently. No shared "common" section.

3. **`generate_test_paths` scans ALL schemas** — it collects path-type fields from every `*.schema.json` in the config directory. Duplicate field names across schemas are deduplicated.

4. **Schema is NOT the only source of truth for injection** — the injection logic checks schema paths first, then falls back to config value heuristics (`_is_path_like`). This handles new workflows whose fields aren't in any schema yet.

5. **Nested genome structures (CoCulture)** — schemas for dual-species workflows should have nested genome keys. The injection logic detects nested structure via `re.match(r'^[A-Za-z]+[0-9]+$', k)` on genome keys.

6. **`type: "null"` means the field is currently null in config** — the auto-generator sets this when the config value is null. It should be manually corrected to `"str"` (the expected type when filled).
