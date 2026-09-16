# Test Framework Reference — `run.py --test`

## Architecture

```
assests/test/
  data/
    ref/           # Auto-generated from schema.json path fields
    index/         # hisat2/, star/, bowtie2/, bwa-mem2/
    smallrna/      # smallRNA BED, FASTA
    fastq/         # PE/SE touch FASTQ per sample
  meta_<Workflow>.tsv  # 11 workflows
```

## Key Design Decisions

1. **Output to `{cwd}/test/` (or `{--output-dir}/test/`)** — NOT root_dir, NOT tempdir
2. **Only override existing fields** — don't add new keys to config (no phantom genome.access in CoCulture)
2. **Schema-driven paths** — `SchemaValidator.generate_test_paths()` from `config/schema.json`
3. **Per-workflow injection** — read each workflow's config structure, inject accordingly
4. **Schema = constraints, config = structure** — schema says which fields are paths; config JSON decides flat vs nested. Schema includes ALL sections (genome, Params, Procedure) — not just genome.
5. **Dynamic workflows** — `WORKFLOW_DISPATCH.keys()`, not manual dict
6. **SE meta fix** — fastq_2 must be non-existent path, not empty (NaN crash)
7. **Local conda-prefix** — avoid /data/ permission issues
8. **Pass/fail summary** — one failure doesn't abort the whole run
9. **ROOT_DIR in all configs** — common.smk import fails without it

## Path Generation Flow

### Step 1: Generate base paths (in `setup_test_args`)
```python
sv = SchemaValidator()
sv._schema_dir = os.path.join(root_dir, "config")  # set dir, scans all *.schema.json
args._test_base_paths = sv.generate_test_paths(test_data, GENOME)
# Returns: {"genome.fasta": "/abs/path/ref/GRCm39.fa", "genome.gtf": ...}
```

### Step 2: Inject per-workflow ALL path fields (in `execute_workflows`)

Walk the ENTIRE config recursively, injecting test paths for ALL path-like values
(null or contains "/"), not just genome.* fields. This handles Params.arriba.blacklist,
Procedure.gatk, etc.

```python
def _is_path(val):
    if val is None: return True
    if not isinstance(val, str): return False
    if "/" in val: return True
    return False

def _make_test_path(key, test_data, genome):
    from pathlib import Path
    ref = Path(test_data) / "ref"
    ref.mkdir(parents=True, exist_ok=True)
    for name in ("smallrna", "rRNA", "access", "repeat", "decoy"):
        if name in key: return str(ref / name)
    if key.endswith(("_dir", "_index")):
        d = Path(test_data) / "index" / key.replace("_dir", "").replace("_index", "")
        d.mkdir(parents=True, exist_ok=True)
        return str(d)
    if key.endswith("_prefix"):
        d = Path(test_data) / "index" / key.replace("_index_prefix", "").replace("_prefix", "")
        d.mkdir(parents=True, exist_ok=True)
        return str(d / genome)
    return str(ref / genome)

def _inject(cfg, prefix, wf_extra):
    for field, val in cfg.items():
        dotted = f"{prefix}.{field}" if prefix else field
        if isinstance(val, dict):
            _inject(val, dotted, wf_extra)
        elif _is_path(val):
            wf_extra[dotted] = base_paths.get(dotted, _make_test_path(field, test_data, genome))

# Per-workflow:
wf_extra = {}
_inject(workflow_config, "", wf_extra)
```

**Why recursive _inject():** Handles ALL nesting levels automatically —
top-level (indir, outdir), genome.* (flat), genome.GRCm39.* (nested),
Params.arriba.blacklist (deeply nested). No manual flat-vs-nested branching needed.

**Why `_is_path` fallback:** New workflows may have fields not in any schema.
The heuristic (null or contains "/") catches them without schema changes.

## Index File Templates

```python
INDEX_MAP = {
    "hisat2":   [f".{i}.ht2" for i in range(1, 9)],
    "bowtie2":  [".1.bt2", ".2.bt2", ".3.bt2", ".4.bt2", ".rev.1.bt2", ".rev.2.bt2"],
    "bwa-mem2": [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"],
    "star":     ["Genome", "SA", "SAindex"],  # directory
}
```

## __main__ Block Structure

```python
if __name__ == "__main__":
    args = parse_args()
    ROOT_DIR = os.path.dirname(__file__)
    if args.test is not None:
        setup_test_args(args, ROOT_DIR)   # workflow list, output dir, base paths, meta map
    else:
        setup_normal_args(args)            # validate -m, -o
    logger = setup_logger(...)
    execute_workflows(args, ROOT_DIR, logger)  # per-workflow injection + execution
```

## Usage

```bash
cd /rna_seq_1/luoshg/Chipseq_20260709
python workflow/Omics/run.py --test              # output → ./test/
python workflow/Omics/run.py --test ncRNAseq     # output → ./test/ncRNAseq/
python workflow/Omics/run.py --test -o /tmp/out  # output → /tmp/out/test/
```

## Common Pitfalls

- **Empty fastq_2 in meta → NaN crash**: Use placeholder path `"_R2.fq.gz"` for SE samples
- **Missing ROOT_DIR in config → ImportError**: Every `<tool>_config` dict needs `"ROOT_DIR": ROOT_DIR`
- **Only injecting genome.* → Params paths not replaced**: Use recursive `_inject()` on entire config, not just genome section. Params.arriba.blacklist, Procedure.gatk, etc. are also paths that need test injection.
- **Output goes to cwd/test/, not root_dir/test/**: Use `args.output_dir if args.output_dir else os.getcwd()` as base
- **Schema has no genome section for nested configs**: CoCulture schema has nested genome.GRCm39/GRCh38 — the injection logic reads actual config structure, not schema structure
