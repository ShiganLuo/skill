# Apptainer Container Building Pitfalls

EnvUtil generates .def files and builds SIF containers from conda YAMLs.

## Post-Install Hooks

For container-specific patches (e.g., fixing bugs in installed packages):

1. Create `<env_name>.post.sh` next to the conda YAML
2. EnvUtil auto-detects and injects into `%post` section
3. Use precise `find` paths to avoid matching wrong files

Example (scTE.post.sh):
```bash
# Fix scTE bug: M<->MT naming
SCTE_BASE=$(find /opt/conda/envs/scTE -path "*/site-packages/scTE/base.py" | head -1) && \
    python3 -c "
p='$SCTE_BASE'
with open(p) as f: src=f.read()
old='''old text'''
new='''new text'''
if old in src:
    src=src.replace(old,new)
    with open(p,'w') as f: f.write(src)
    print('patched',p)
else:
    print('already patched or different version')
"
```

**PITFALL**: `find ... -path "*/scTE/*"` matches ANY path containing `scTE`, including `email/mime/base.py`. Use precise paths like `*/site-packages/scTE/base.py`.

## Build Verification

EnvUtil now verifies builds with two checks:

1. **SIF size**: < 350MB indicates failed build (base image ~300MB)
2. **conda env check**: Runs `apptainer exec ... conda env list` to verify env exists

If either check fails, `RuntimeError` is raised.

**PITFALL**: `apptainer build --fakeroot` may return 0 even when `%post` fails. The verification catches this.

## Solver Issues

**libmamba solver**: May fail to install in container build context.

Current approach: Use `conda config --set solver classic` (slow but reliable).

If libmamba needed:
```
conda install -n base -c conda-forge -y conda-libmamba-solver && conda config --set solver libmamba
```

**PITFALL**: Without `-c conda-forge`, the solver package is not found.

## PyPI-Only Detection

EnvUtil detects when all deps are PyPI packages and uses uv-based template:
- Base: `python:3.11-slim`
- Install: `uv pip install --system`

Detection logic:
- Filter out `python*` and `pip*` meta-packages
- If remaining conda deps exist → use conda template
- If only pip deps → use uv template

## CLI Flags

- `--force`: Overwrite existing SIF (implies `--no-skip-existing`)
- `--no-fakeroot`: Disable fakeroot in build
- `--no-skip-existing`: Rebuild even if SIF exists
