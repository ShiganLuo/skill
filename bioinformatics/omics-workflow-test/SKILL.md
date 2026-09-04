---
name: omics-workflow-test
description: Run dry-run tests for Omics Snakemake workflows via run.py --test
---

# When to use

- User asks to test Omics workflows
- User wants to verify DAG resolution without executing rules
- User wants to add a new workflow and needs to validate it

# How to run tests

```bash
cd /rna_seq_1/luoshg/Chipseq_20260709/workflow/Omics

# Test all registered workflows (auto-discovered from WORKFLOW_DISPATCH)
python run.py --test

# Test single workflow
python run.py --test ncRNAseq
python run.py --test PeakCalling

# Specify output directory
python run.py --test -o /some/path   # output goes to /some/path/test/
```

# Architecture

```
run.py
  ├── setup_test_args()      # configure test mode args
  ├── setup_normal_args()    # validate normal mode args
  ├── execute_workflows()    # build + run snakemake commands
  └── print_test_summary()   # PASS/FAIL report

src/common/SchemaValidator.py
  ├── load(path)             # load single schema file
  ├── load_workflow(name)    # load config/<name>.schema.json
  ├── get_path_fields()      # return path-type fields from loaded schema
  ├── validate(config)       # check required/nullable/type
  └── generate_test_paths()  # create touch files, return {key: abs_path}

config/<Workflow>.schema.json  # per-workflow schema (mirrors config structure)
assests/test/                  # test resources
```

# Per-workflow schema design

Each workflow has its own `config/<wf>.schema.json` that mirrors the config structure:

```json
{
  "ROOT_DIR": {"type": "str", "path": "dir", "required": true, "nullable": false},
  "indir": {"type": "str", "path": "dir", "required": true, "nullable": false},
  "genome": {
    "fasta": {"type": "str", "path": "file", "nullable": true, "required": false},
    "gtf": {"type": "str", "path": "file", "nullable": true, "required": false}
  }
}
```

No inheritance, no merging, no override mechanism. Each workflow is self-contained.

# Path injection flow

1. `setup_test_args` loads SchemaValidator, calls `generate_test_paths()` → `args._test_base_paths`
2. `execute_workflows` per-workflow:
   a. Loads workflow config JSON
   b. Detects genome structure (flat vs nested)
   c. Injects schema-known paths
   d. **Fallback**: for config fields NOT in schema, uses `_is_path_like(val)` heuristic

```python
# Fallback for fields not in schema
for field, val in genome_cfg.items():
    base_key = f"genome.{field}"
    if base_key in base_paths:          # schema knows this field
        wf_extra[base_key] = base_paths[base_key]
    elif _is_path_like(val):            # fallback: config value looks like a path
        wf_extra[base_key] = _resolve_test_path(field, test_data, genome)
```

# Nested genome injection (CoCulture)

CoCulture has `genome.GRCm39.fasta` and `genome.GRCh38.fasta` (nested). The injection logic:

```python
nested_orgs = [k for k, v in genome_cfg.items()
               if isinstance(v, dict) and re.match(r'^[A-Za-z]+[0-9]+$', k)]

if nested_orgs:
    # Inject ONLY for fields that exist in the config
    for org in nested_orgs:
        org_cfg = genome_cfg.get(org, {})
        for field in org_cfg.keys():
            base_key = f"genome.{field}"
            if base_key in base_paths:
                wf_extra[f"genome.{org}.{field}"] = base_paths[base_key]
else:
    # Flat injection
    for k, v in base_paths.items():
        wf_extra[k] = v
```

# Test resources

Located at `assests/test/`:

```
assests/test/
  data/
    ref/           # Touch placeholder reference files
    index/         # hisat2/, star/, bowtie2/, bwa-mem2/ index files
    smallrna/      # smallRNA BED, FASTA
    fastq/         # Touch placeholder FASTQ files
  meta_<Workflow>.tsv  # per-workflow meta files
```

# Summary output format

```
============================================================
[TEST] Results (11 workflows)
============================================================
  [PASS] PeakCalling
  [PASS] ncRNAseq
  [FAIL] CLIP
         ImportError: No module named 'common'

  Passed: 3, Failed: 8, Total: 11
  Failed workflows: CLIP, CoCulture, ...
```

# Pitfalls

1. SE samples in meta: fastq_2 MUST be a non-existent placeholder path (not empty/NaN)
2. In test mode, conda-prefix is auto-set to `{output_dir}/.conda` (local). In
   normal mode, `--conda-prefix` is required when `--sdm` is absent (default None,
   not a foreign path). When `--sdm apptainer` is set, conda is omitted entirely.
3. Snakemake 9.x required for conda: + run: compatibility
4. Test summary must show ALL results, not crash on first failure
5. Output goes to `{cwd}/test/` (or `{--output-dir}/test/`), NOT root_dir
6. Schema is NOT the only source of truth — fallback to config value heuristics
7. Nested genome detection uses `re.match(r'^[A-Za-z]+[0-9]+$', k)` (matches GRCm39, GRCh38)
