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

## metavar tuple length mismatch with nargs

Using a tuple `metavar` with `nargs="+"` raises `ValueError`:

```python
# WRONG — metavar tuple length (3) != nargs ("+" means variable)
parser.add_argument("--group", nargs="+", action="append",
                    metavar=("H5AD", "SAMPLE1", "SAMPLE2"), ...)
# ValueError: length of metavar tuple does not match nargs
```

**Fix**: Use a single string metavar when nargs is variable (`"+"`, `"*"`, `N`):

```python
# CORRECT
parser.add_argument("--group", nargs="+", action="append",
                    metavar="ARG",
                    help="H5AD_PATH SAMPLE1 SAMPLE2 [SAMPLE3 SAMPLE4 ...]")
```

**Rule**: `metavar` tuple length must exactly match `nargs` when `nargs` is an int. For variable nargs (`"+"`, `"*"`), use a single string.

## Repeatable multi-value group pattern (`--group`)

For analyses with multiple independent groups (e.g., 2 tissues × 2 quantification methods = 4 groups), use a repeatable `--group` argument:

```python
parser.add_argument("--group", nargs="+", action="append", required=True,
                    metavar="ARG",
                    help="KEY ARG1 ARG2 [ARG3 ARG4 ...]")
```

Each `--group` invocation collects a list. Parse the first element as the key (e.g., h5ad path), remaining elements in pairs:

```python
for group_args in args.group:
    key = group_args[0]           # e.g., h5ad path
    pairs = group_args[1:]
    for i in range(0, len(pairs), 2):
        sample1, sample2 = pairs[i], pairs[i+1]
```

Validate pair counts in post-parse:
```python
if (len(group_args) - 1) % 2 != 0:
    parser.error("sample names must be in pairs")
```

Output subdirectories from file stem: `Path(key).stem`.
