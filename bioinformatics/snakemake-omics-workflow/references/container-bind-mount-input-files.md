# Container bind-mount: universal `raw_files` pattern

When Snakemake rules run inside Apptainer/Singularity containers, only explicitly
bind-mounted paths are accessible inside the container. `_collect_bind_paths()` in
`run.py` scans the config JSON for path-like strings and adds them to
`--singularity-args '--bind ...'`.

**Problem:** Input files that are symlinks pointing outside the bind-mounted
directory tree break silently inside the container. The error is often misleading
(e.g. `Unable to access the RAW file using the native Thermo library`).

**Solution:** `MetaUtil._collect_raw_files()` resolves symlinks at metadata time.
The resolved paths flow through `run.py` → `WORKFLOW_DISPATCH` → node functions
into `raw.json`. `_collect_bind_paths()` then picks up the real paths and adds
them to the singularity bind mounts automatically.

## Architecture: MetaUtil → run.py → node.py

```
MetaUtil.run()
  → _collect_raw_files() scans raw_fq_dir, resolves symlinks
  → returns 5-tuple: (samples_dict, pairs, group_pairs, indir, raw_files)

run.py
  → unpacks raw_files as 5th value
  → passes to WORKFLOW_DISPATCH lambda as 8th param (rf)
  → passes to node function

node.py (all 11 run*() functions)
  → accept raw_files: List[str] parameter
  → datajson["raw_files"] = raw_files
  → written to raw.json
  → _collect_bind_paths() picks them up for singularity --bind
```

## `MetaUtil._collect_raw_files()`

```python
def _collect_raw_files(self) -> List[str]:
    """Scan raw_fq_dir/{sample_id}/ for files, resolve symlinks."""
    result: List[str] = []
    if not self.raw_fq_dir.is_dir():
        return result
    for sample_dir in sorted(self.raw_fq_dir.iterdir()):
        if not sample_dir.is_dir():
            continue
        for f in sorted(sample_dir.iterdir()):
            if f.is_file():
                result.append(str(f.resolve()))
    return result
```

## WORKFLOW_DISPATCH pattern (run.py)

All lambdas accept `rf` as 8th param and pass to node functions:
```python
WORKFLOW_DISPATCH = {
    "CoCulture": lambda cfg, sid, sp, gp, indir, outdir, meta, rf: ("CoCulture.smk", runCoCulture(cfg, sid, indir, outdir, rf)),
    ...
}
```

## Node function signatures

All 11 functions accept `raw_files: List[str]` and set:
```python
datajson["raw_files"] = raw_files
```

## Config template field

Every workflow config JSON must have:
```json
"raw_files": [],
```
This is a placeholder — `MetaUtil` populates it at runtime via `run.py`.

Applies to ALL 11 workflows: CoCulture, MERIP, RNAseq, ncRNAseq, CLIP, Mutation,
PacVar, KARRseq, PeakCalling, QuantMS, tRNAseq.

## Pitfalls

- **Don't put file collection in node.py.** The file paths come from metadata,
  not from scanning directories at config-generation time. MetaUtil already knows
  the files — collect them there.
- **`run.py` unpacks 5 values from `MetaUtil.run()`, not 4.** Old code had 4-tuple.
  Missing `raw_files` causes `ValueError: too many values to unpack`.
- **WORKFLOW_DISPATCH lambdas need 8 params, not 7.** The 8th is `rf` (raw_files).
  Missing it causes `TypeError: <lambda>() missing 1 required positional argument`.
- **ThermoRawFileParser symlink errors are misleading.** The error `Unable to
  access the RAW file using the native Thermo library` usually means the file is
  a broken symlink inside the container, not a library issue.

## Verification

After running `run.py`, check that `raw.json` has populated `raw_files`:
```bash
python -c "import json; d=json.load(open('output/<wf>/raw.json')); print(len(d.get('raw_files',[])), 'files')"
```

The paths should be real paths (no symlinks): `file <path>` should NOT say
"symbolic link to ...".
