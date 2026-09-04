# Conda Environment Hash and Reuse Mechanism

Snakemake creates one conda environment per unique yaml file content. Understanding
the hashing mechanism is critical for debugging "why is my env stale?" issues.

## How it works

Source: `snakemake/src/snakemake/deployment/conda.py`

1. Rule declares `conda: "fumitools.yaml"` (relative path)
2. Snakemake reads the yaml file's raw bytes
3. Computes MD5 hash of the content (+ optional location/container info)
4. Environment path = `{--conda-prefix}/{hash}_`

```python
import hashlib

md5hash = hashlib.md5(usedforsecurity=False)
md5hash.update(yaml_content_bytes)  # raw file bytes
hash = md5hash.hexdigest()          # 32-char hex
env_dir_name = hash + "_"           # with underscore suffix
```

## Hash candidates (fallback chain)

Snakemake tries three path patterns in order:
1. `hash[:8]` — old 8-char prefix (legacy)
2. `hash` — full 32-char hash
3. `hash + "_"` — full hash with underscore (current default, avoids admin-rights issues on Windows)

The first existing path wins. For new environments, the last candidate (`hash + "_"`) is used.

## Location-aware vs content-only hash

Two hash modes exist:
- **content_hash** (containerized): only yaml content bytes
- **hash** (non-containerized, your case): yaml content + `os.path.realpath(envs_dir)` bytes

For `--conda-prefix /data/pub/zhousha/env/mutation_0.1`, the hash includes the
realpath of that directory. Moving the prefix directory invalidates all environments
(because binaries may contain hardcoded RPATHs).

## Debugging stale environments

When a yaml was modified but Snakemake still uses the old env:

1. **Check the stored yaml snapshot** — Snakemake saves the yaml used to create each env:
   ```bash
   ls /path/to/conda-prefix/*.yaml
   cat /path/to/conda-prefix/<hash>_.yaml
   ```

2. **Compute current hash**:
   ```python
   import hashlib, os
   with open("modules/fumitools/fumitools.yaml", "rb") as f:
       content = f.read()
   env_dir = os.path.realpath("/data/pub/zhousha/env/mutation_0.1")
   h = hashlib.md5(usedforsecurity=False)
   h.update(env_dir.encode())
   h.update(content)
   print(h.hexdigest() + "_")
   ```

3. **Compare**: if the computed hash doesn't match the env directory in use,
   the yaml was changed after the env was created. Snakemake should create a
   new env on next run — but if `--rerun-triggers mtime` skips env checks,
   or the subworkflow references a different yaml path, the old env persists.

## Common pitfall: yaml modified but old env still used

The env `3f6e2e62c2860b8edd8c94fbe72cfe5d_` was created from fumitools.yaml
WITHOUT python. Later python was added, producing hash `275fe5875c5da6c984ac833213d23a75_`.
But if the workflow still references the old yaml (or uses `--rerun-triggers mtime`),
the old env without python persists.

**Fix**: Either:
- Let snakemake re-run with updated yaml (it creates new env automatically)
- Manually fix the old env (symlink python → python3)
- Delete the old env directory to force recreation
