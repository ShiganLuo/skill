# Target Execution Control (run.py --forcerun)

When the user needs to re-run a specific rule or rule:wildcard job without
re-running the entire pipeline, run.py exposes `--forcerun` as a first-class
CLI argument.

## Usage

```bash
# Single target (rule name only, no wildcards)
python run.py -m meta.tsv -w RNAseq -o output/ --sdm \
    --forcerun function_gsea

# Single target with wildcards
python run.py -m meta.tsv -w RNAseq -o output/ --sdm \
    --forcerun trimming_Paired:sample_id=S1

# Multiple targets
python run.py -m meta.tsv -w RNAseq -o output/ --sdm \
    --forcerun trimming_Paired:sample_id=S1 trimming_Paired:sample_id=S2
```

## How it works internally

run.py translates `--forcerun TARGETS` into **two** snakemake flags:

```
snakemake ... --until <TARGETS> --forcerun <TARGETS>
```

Both flags receive the same target list. This combination is critical:

- `--until TARGETS` truncates the DAG to TARGETS + upstream dependencies only.
  Downstream rules are excluded from the DAG entirely.
- `--forcerun TARGETS` forces re-execution of the specified jobs regardless of
  whether their output files already exist.

Without `--until`, `--forcerun` alone would re-run the target AND all downstream
jobs (because the DAG still spans all outfiles). Without `--forcerun`, `--until`
alone would skip the target if its output already exists.

## Why NOT positional targets + --force

Snakemake positional targets (bare `rule:wildcard=val` at the end of the command)
are interpreted as **file paths**, not rule names. A bare rule name like
`function_gsea` triggers `MissingRuleException` / `AttributeError: 'str' object
has no attribute 'is_storage'` because snakemake tries to resolve it as a file.

`--until` and `--forcerun` accept rule names and `RULE:WILDCARD=VALUE` syntax
natively, so they work correctly with rule-name-only targets.

## Relationship to outfiles

`outfiles` (set by `run<Workflow>()` in run.py, consumed by `rule all` in each
subworkflow .smk) defines the full DAG boundary. When `--until` is used, the DAG
is further restricted to the target + its upstream dependencies. The target must
be reachable from `outfiles` (i.e., it must be an upstream dependency of some
outfile). If the target is not in the DAG at all, snakemake will report it as
missing.

## Implementation in run.py

### parse_args()

```python
parser.add_argument('--forcerun', type=str, nargs='+', default=None,
    help='force re-run specific jobs without downstream, e.g. --forcerun trimming_Paired:sample_id=S1')
```

### build_snakemake_cmd()

```python
if forcerun:
    cmd.append("--until")
    cmd.extend(forcerun)
    cmd.append("--forcerun")
    cmd.extend(forcerun)
```

Placed after `--dry-run`, before `--snakemake-args`.

### execute_workflows()

```python
cmd = build_snakemake_cmd(
    ...,
    forcerun=args.forcerun,
)
```

## Pitfalls

- **Do NOT use `--force` + positional target**: snakemake treats positional
  arguments as file paths, not rule names. Use `--until` + `--forcerun` instead.
- **`--forcerun` alone re-runs downstream**: Without `--until`, the DAG still
  includes all outfiles and their dependencies, so downstream jobs will also
  re-run. Always pair `--until` with `--forcerun` when the intent is to
  re-run only the specified job.
- **`--target-jobs` is internal-only**: Snakemake marks `--target-jobs` as
  "Internal use only". It works from CLI but is intended for programmatic API
  use. Do not expose it; use `--until` / `--forcerun` instead.
