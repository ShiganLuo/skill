# Apptainer SIF build pitfalls (conda + fakeroot)

Building conda-based SIF containers with `apptainer build --fakeroot` on shared
HPC systems has three recurring failure modes. All three were discovered on a
system with conda 26.x and miniconda3 as the host conda installation.

## 1. Host conda PATH leaks into container `%post`

**Symptom:** `conda env create` inside `%post` uses the HOST's conda
(`/home/<user>/miniconda3/bin/conda`) instead of the container's
(`/opt/conda/bin/conda`). The build "succeeds" but the conda env inside the
SIF is empty — `/opt/conda/envs/<name>/` contains no packages.

**Diagnostic:** The conda error report shows `base environment: /home/<user>/miniconda3`
(the host path, not `/opt/conda`).

**Fix:** Prepend the container's conda to PATH in `%post`:
```
%post
    export PATH="/opt/conda/bin:$PATH"
    conda env create -f /opt/conda/<name>.yaml
```

This is already baked into `EnvUtil.generate_def()` — verify it's present if
editing .def files manually.

## 2. `anaconda_anon_usage` plugin error

**Symptom:** `An unexpected error has occurred. Conda has prepared the above
report. If you suspect this is being caused by a malfunctioning plugin...`
The error is from the `anaconda_anon_usage` package bundled with miniconda3.

**Fix:** Set `CONDA_NO_PLUGINS=true` in `%post`:
```
%post
    export PATH="/opt/conda/bin:$PATH"
    export CONDA_NO_PLUGINS=true
```

## 3. `libmamba` solver not recognized (use classic)

**Symptom:** `CondaValueError: You have chosen a non-default solver backend
(libmamba) but it was not recognized. Choose one of: classic`

The host's `~/.condarc` sets `solver: libmamba`, which leaks into the container.
The container's miniconda3 doesn't have libmamba installed.

**Current fix (EnvUtil default):** Use classic solver:
```
%post
    export PATH="/opt/conda/bin:$PATH"
    export CONDA_NO_PLUGINS=true
    conda config --set solver classic
    conda env create -f /opt/conda/<name>.yaml
```

**Why NOT libmamba in containers:** Installing `conda-libmamba-solver` from
conda-forge inside `%post` is unreliable — it can fail silently, timeout, or
produce an empty SIF (build exits 0 but no packages installed). The classic
solver is slow (5-10 min for dual-channel) but reliable.

**Host `~/.condarc` leak:** If the host has `solver: libmamba` in `~/.condarc`,
it leaks into the container. Always explicitly set `conda config --set solver classic`
in `%post` to override.

**Future:** If conda ships libmamba built-in (no separate install needed),
switch back to libmamba. Until then, classic is the safe default.

## 3b. `conda env create` fails silently — SIF built with empty env

**Symptom:** SIF exists and `apptainer build` returned 0, but the conda env
inside is empty. `import anndata` fails with `ModuleNotFoundError`.

**Cause:** Apptainer's `%post` section does NOT have `set -e` by default. If
`conda env create` fails (e.g. `ResolvePackageNotFound`), the build continues
and produces a SIF with only the base miniconda — no packages installed.

**Fix:** Add `set -euo pipefail` as the FIRST line of `%post`:
```
%post
    set -euo pipefail
    export PATH="/opt/conda/bin:$PATH"
    ...
    conda env create -f /opt/conda/{yaml_filename}
```

This is now baked into `EnvUtil._render_def()`. If regenerating .def files,
the fix is automatic.

**Verification:** Always check after build:
```bash
apptainer exec <sif> python -c "import anndata; print('OK')"
```

## Canonical `%post` template

All fixes combined (conda-based):
```
%post
    set -euo pipefail
    export PATH="/opt/conda/bin:$PATH"
    export CONDA_NO_PLUGINS=true
    conda config --set solver classic
    conda env create -f /opt/conda/{yaml_filename} && \
        conda clean -afy && \
        rm /opt/conda/{yaml_filename}
```

This template lives in `EnvUtil._render_def()`. If you regenerate .def files
via `EnvUtil`, the fixes are automatic. If editing .def manually, ensure
`set -euo pipefail` and all three exports are present.

## 4. `openms-thirdparty` ≠ `openms`

**Symptom:** `DecoyDatabase: command not found` (or any core OpenMS tool).

`openms-thirdparty=3.1.0` provides third-party wrappers (ThermoRawFileParser,
CometAdapter, etc.) but NOT core OpenMS tools. Core tools (DecoyDatabase,
FileConverter, PeptideIndexer, etc.) come from the `openms` package.

**Fix:** Always include BOTH in the YAML:
```yaml
dependencies:
  - openms=3.1.0
  - openms-thirdparty=3.1.0
```

All 8 OpenMS-based QuantMS containers (raw2mzml, decoydatabase, searchengine,
psmrescoring, psmfdr, proteininference, quantification, msstats) need both.

## 5. Network timeout → localimage bootstrap fallback

**Symptom:** `apptainer build` fails with `TLS handshake timeout` or
`dial tcp: i/o timeout` when fetching the Docker base image from any
registry (daocloud, Docker Hub, Anaconda).

**Fix:** Use an existing SIF as the base via `localimage` bootstrap:
```
Bootstrap: localimage
From: /home/luosg/Database/env/star/star.sif
```

The base SIF must already have miniconda3 installed (most Omics SIFs do).
The `%post` section then runs `conda env create` on top of the existing
conda installation. External binaries (e.g. cellranger-10.1.0) are
copied via `%files` and added to PATH in `%environment`.

## 6. Bundling external (non-conda) binaries in SIF

When a tool is distributed as a pre-compiled binary (not available via
conda), copy the entire directory into the container via `%files` and
add to PATH:

```
%files
    tool.yaml /opt/conda/tool.yaml
    /absolute/path/to/tool-1.0.0 /opt/tool-1.0.0

%post
    conda env create -f /opt/conda/tool.yaml && conda clean -afy
    echo 'export PATH="/opt/tool-1.0.0/bin:$PATH"' >> /etc/profile.d/tool.sh

%environment
    export PATH="/opt/conda/envs/tool/bin:$PATH"
    export PATH="/opt/tool-1.0.0/bin:$PATH"
```

The `%files` section preserves directory structure, so relative paths
(e.g. `bin/cellranger` → `lib/bin/STAR`) remain intact inside the
container.

## 7. anndata + pandas version incompatibility

**Symptom:** `ModuleNotFoundError: No module named 'pandas.core.index'`
when importing anndata inside the SIF.

**Cause:** `pandas.core.index.RangeIndex` was removed in pandas 2.0+.
Old anndata versions (<0.10) still import it.

**Fix:** Pin `anndata>=0.10` in the YAML. Do NOT pin `pandas<2.0` —
conda may ignore the constraint when other packages (scanpy, anndata)
pull in pandas 2.x+.

```yaml
dependencies:
  - python=3.11
  - anndata>=0.10
  - scanpy>=1.9
  - h5py
```

**Verification after build:**
```bash
apptainer exec <sif> python -c "import anndata, scanpy; print(anndata.__version__)"
```

## 8. `ResolvePackageNotFound` — package only on PyPI

**Symptom:** `conda env create` fails with `ResolvePackageNotFound: <package>`.
The package is not in conda-forge or bioconda.

**Diagnostic:** `pip index versions <package>` confirms it exists on PyPI.

**Fix:** Move the package to `pip:` sub-dependencies:
```yaml
dependencies:
  - python=3.11
  - scanpy
  - pip:
    - infercnvpy
```

Known packages requiring this: `infercnvpy`.

**Important:** When using `pip:` section, add `pip` itself as a conda dependency to avoid the warning:
```yaml
dependencies:
  - python=3.11
  - pip
  - scanpy
  - pip:
    - infercnvpy
```

Without `pip` in conda deps, conda warns: "you have pip-installed dependencies in your environment file, but you do not list pip itself as one of your conda dependencies."

## 9. uv-based build: 10x faster alternative to conda

When all packages are on PyPI, use `uv pip install` instead of `conda env create`.
Conda's classic solver can take hours for complex environments (scanpy + scvelo + liana);
uv resolves and installs in minutes.

**EnvUtil auto-detection (baked in):** `EnvUtil.generate_def_file()` now
automatically detects PyPI-only YAMLs and uses the uv template. Detection
logic in `EnvUtil.is_pypi_only()`:
- `parse_conda_yaml()` extracts `pip_dependencies` from the `pip:` sub-section
- `python*` and `pip*` conda deps are treated as meta-packages (base image provides them)
- If remaining conda deps are empty AND pip deps exist → PyPI-only → uv template
- Otherwise → conda template

To test detection on a YAML:
```python
from EnvUtil import EnvUtil
EnvUtil.is_pypi_only('path/to/env.yaml')  # True/False
```

**Def template (uv-based):**
```
Bootstrap: docker
From: docker.m.daocloud.io/python:3.11-slim

%post
    set -euo pipefail
    apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
    pip install uv
    uv pip install --system --no-cache \
        scanpy anndata leidenalg python-igraph scrublet \
        scvelo liana celltypist openai requests infercnvpy

%environment
    export PYTHONUNBUFFERED=1
```

**Key differences from conda-based def:**
- Base image: `python:3.11-slim` (not miniconda3)
- Mirror: `docker.m.daocloud.io/` prefix (Docker Hub blocked in CN)
- `build-essential`: needed for packages with C extensions (annoy, igraph, leidenalg)
- `--system`: install into system Python (not a venv)
- `--no-cache`: avoid filling tmp during build

**When to use uv vs conda:**
- uv: all deps on PyPI, no R/ bioinformatics-specific binaries
- conda: some deps only in conda-forge/bioconda (e.g. STAR, samtools, R packages)

**CRITICAL: `build-essential` for C extensions:**
Packages like `annoy` (dep of scrublet), `igraph`, `leidenalg` need C++ compilation.
The `python:3.11-slim` image has NO compiler. Without `build-essential`, uv/pip fails:
```
error: [Errno 2] No such file or directory: 'g++'
```
Always include `apt-get install -y --no-install-recommends build-essential` before
`uv pip install` in the def file.

**Verification:** same as conda-based — `apptainer exec <sif> python -c "import <pkg>"`.

## 10. Verify if a package is on PyPI

Before choosing uv vs conda, confirm the package exists on PyPI:

```bash
# Single package — JSON API (scriptable)
curl -sf https://pypi.org/pypi/<package>/json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['name'], d['info']['version'])"

# pip index (slower, more info)
pip index versions <package>

# Batch check
for pkg in pkg1 pkg2 pkg3; do
    curl -sf "https://pypi.org/pypi/$pkg/json" > /dev/null && echo "$pkg -> PyPI" || echo "$pkg -> NOT PyPI"
done
```

If any package is NOT on PyPI, use conda-based def with `pip:` sub-section for the PyPI-only ones.

## 11. Post-install hooks: `.post.sh` for container-specific patches

Some containers need custom commands after `conda env create` — e.g. patching
a library bug, copying config files, or building native extensions. EnvUtil
supports a `.post.sh` hook mechanism:

**How it works:**
1. Create `<env_name>.post.sh` next to the YAML in the module directory
2. EnvUtil reads it and injects content into `%post` after `conda env create`
3. If no `.post.sh` exists, the template is unchanged

**Example — scTE mitochondrial patch:**
`workflow/Omics/modules/scTE/scTE.post.sh` contains Python scripts that
patch `scTE/base.py` and `bin/scTE_build` to handle chrM ↔ chrMT naming.
See `references/scte-container-patches.md` for full details.

**Key rules:**
- Filename must match `<env_name>.post.sh` (env_name from YAML's `name:` field)
- Content is shell commands — indent with 4 spaces to match `%post` style
- The hook runs inside the container during build, not on the host
- EnvUtil logs "Found post-install hook: <path>" when a hook is detected

**When to use:**
- Patching installed package source code (bugs, compatibility fixes)
- Post-install configuration (copying configs, setting permissions)
- Building native extensions that pip/conda didn't handle

### Critical pitfall: match INSTALLED content, not source

Post.sh patches using `str.replace()` do **exact string matching**. The installed
binary/package may have DIFFERENT formatting than the source code in the repo.
If the old text doesn't match character-for-character, the patch **silently fails**.

**Real example:** scTE_build source had `[ str(k)` (extra spaces) but the installed
binary had `[str(k)` (no spaces). The patch didn't apply.

**Rule:** Before writing a post.sh patch, inspect the ACTUAL installed file:
```bash
apptainer exec <sif> cat -n /path/to/installed/file | grep -A2 "target"
```

Use `cat -A` to see exact whitespace (tabs vs spaces, trailing spaces).

**Safer pattern:** Use `python3 -c` with a guard that prints whether the patch
was applied:
```bash
python3 -c "
with open(p) as f: src = f.read()
old = '''exact old text'''
if old in src:
    src = src.replace(old, new)
    with open(p, 'w') as f: f.write(src)
    print('patched')
else:
    print('WARNING: old text not found — patch NOT applied')
"
```

## Rebuild checklist

When rebuilding SIFs after .def changes:
1. Verify .def has all 3 PATH/plugin/solver fixes (conda) OR uv template
2. `apptainer build --force --fakeroot <name>.sif <name>.def`
3. Verify env is populated: `apptainer exec <sif> python -c "import <key_package>"`
4. If empty, check build output for conda errors (the build may exit 0 even if conda failed)
5. For uv builds: verify `build-essential` is installed (C extensions need g++)

**EnvUtil CLI `--force` flag:** `--force` sets `force=True` (apptainer build --force)
AND implies `skip_existing=False` (rebuild even if SIF exists). Without `--force`,
existing SIFs are skipped. Default is `force=False`.

```bash
# Rebuild even if SIF exists
python EnvUtil.py apptainer all -y <yaml> -o <output_dir> --force

# Skip existing (default behavior)
python EnvUtil.py apptainer all -y <yaml> -o <output_dir>
```
