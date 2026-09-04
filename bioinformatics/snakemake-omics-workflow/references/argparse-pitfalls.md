# Argparse Pitfalls in Snakemake CLI Scripts

## Duplicate argument definition

When refactoring CLI scripts (e.g., merging modes), arguments can be accidentally defined twice:

```python
# WRONG - batch-key defined in two places
parser.add_argument("--batch-key", default="", help="...")  # line 900 (QC section)
parser.add_argument("--batch-key", default="", help="...")  # line 914 (Batch section)
```

**Error**: `argparse.ArgumentError: argument --batch-key: conflicting option string: --batch-key`

**Fix**: When consolidating modes, remove arguments from the old section before adding to the new one.

**Prevention**: After any mode merge/refactor, run:
```bash
python script.py --help
```

## When merging modes

When merging two modes (e.g., batch → cluster):
1. Move parameters from old mode to new mode
2. Remove old mode's argument definitions
3. Remove old mode's dispatch in main()
4. Update CLI choices list
5. Update scanpy.smk rule to remove old rule, update new rule's params
6. Update ALL config files (module.json, workflow.json, schema.json)
