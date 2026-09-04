---
name: apptainer-sif-build-pitfalls
description: Pitfalls and patterns for building Apptainer SIF images via EnvUtil.py — PyPI detection, uv vs conda templates, CN network workarounds, system dependency traps.
---

# Apptainer SIF Build Pitfalls

**NOTE**: Overlaps with `apptainer-container-build` (bioinformatics). This skill focuses on EnvUtil internals; the bioinformatics skill adds annotation standardization and scTE-specific detail.

EnvUtil.py generates `.def` files from conda YAML and builds `.sif` images. Two templates exist:

## Template Selection (auto-detected via `is_pypi_only()`)

**PyPI-only YAML** → uv template (`python:3.11-slim` + `uv pip install`)
- Trigger: no conda deps beyond `python*`/`pip*`, all real packages under `pip:` sub-section
- `parse_conda_yaml()` returns `pip_dependencies` list (items under `pip:` key)
- `is_pypi_only()` checks: `python`/`pip` are meta-deps (filtered out via regex); remaining conda deps must be empty
- Fast: ~2 min vs ~2hr conda

**Mixed/conda YAML** → conda template (`miniconda3` + `conda env create`)
- Trigger: any conda-specific dep (samtools, bedtools, openms, etc.)

## Critical Pitfall: PyPI packages with system deps

`scte-quant` is PyPI-only BUT needs `samtools` and `zstd` at runtime.
If you put only `pip: scte-quant` in the YAML, uv template is chosen and those system tools are missing.

**Fix**: Add the system deps as conda deps in the YAML:
```yaml
dependencies:
  - python>=3.6
  - pip
  - samtools
  - zstd
  - pip:
      - scte-quant
```

**Rule**: Before marking a YAML as PyPI-only, verify the pip package doesn't need system-level tools (samtools, zstd, htslib, etc.) that only conda/apt provides.

## Common Fixes

- `set -eu` in every `%post` block (**NOT `set -euo pipefail`** — the default shell in Apptainer `%post` is `sh`, not `bash`, and `pipefail` is not supported in `sh`, causing `set: Illegal option -o pipefail`)
- Docker Hub blocked in CN: `FROM: docker.m.daocloud.io/...`
- openms needs BOTH `openms` AND `openms-thirdparty`

## CLI

```bash
EnvUtil.py apptainer gen  -y <yaml>           # generate .def only
EnvUtil.py apptainer build -o <out> -f <def>  # build .sif from .def
EnvUtil.py apptainer all  -y <yaml> -o <out>  # full pipeline
```

Flags: `--no-fakeroot`, `--force` (default off, enables overwrite + rebuild)

**Pitfall**: `--force` implies `--no-skip-existing`. Without `--force`, existing SIFs are skipped
even if you want to rebuild. The `force` param controls `apptainer build --force` (overwrite output file)
while `skip_existing` controls the Python-level "SIF already exists" early-exit. `--force` sets both.

## Post-install hooks (`.post.sh`)

EnvUtil reads `<env_name>.post.sh` from the YAML's directory and injects its content
at the end of `%post` in the generated `.def`. Use for module-specific patches
(e.g. scTE's M<->MT fix) without manually editing the `.def`.

```
modules/scTE/
  scTE.yaml        # conda env definition
  scTE.post.sh     # auto-injected into %post
```

The `.post.sh` content is raw shell — indent with 4 spaces to match `%post` style.

## conda solver

Default template uses `conda config --set solver classic` (reliable).
libmamba solver installation from conda-forge is unreliable in container builds —
can fail silently, timeout, or produce empty SIFs. Classic solver is slow (5-10 min
for dual-channel) but works every time.

Host `~/.condarc` may set `solver: libmamba` which leaks into the container.
Always explicitly set `conda config --set solver classic` in `%post` to override.

## Silent build failures (CRITICAL)

`apptainer build --fakeroot` can return exit code 0 even when `%post` fails.
EnvUtil's `_run_streaming` checks returncode but apptainer doesn't propagate
`%post` errors reliably. Result: empty SIF (~300MB = just base image) with no error.

**Detection**: EnvUtil `build_sif()` now does two post-build checks:
1. SIF size < 350MB → RuntimeError (base miniconda3 is ~300MB)
2. `apptainer exec <sif> conda env list` → check env name present

**Manual verification after build**:
```bash
# Quick check
ls -lh <sif>  # should be >500MB for real envs
# Full check
apptainer exec <sif> bash -c 'conda env list; which scTE; samtools --version | head -1'
```

## SIF is read-only at runtime

Cannot patch files inside a SIF with `apptainer exec` — all fixes must be baked into the `%post` section during build. If you discover a missing patch after build, you must rebuild.

## find path precision in %post

When using `find` to locate Python package files inside conda envs, use precise paths:

```bash
# BAD — matches email/mime/base.py, pip/internal/base.py, etc.  head -1 picks wrong file silently
find /opt/conda/envs/scTE -name "base.py" -path "*/scTE/*"

# GOOD — exact site-packages path
find /opt/conda/envs/scTE -path "*/site-packages/scTE/base.py"
```

Ambiguous `find` + `head -1` is a silent failure — the patch targets the wrong file and you get no error.

## M<->MT mitochondrial patch

scTE has chrM/chrMT naming mismatches in TWO places:

### 1. `base.py split_all_chrs()` — BAM processing
Direction matters:
- BED chrMT → chromosome_list has M → map MT→M
- BED chrM → chromosome_list has MT → map M→MT
Both directions must be handled.

### 2. `scTE_build` — Index building (chr_list)
`scTE_build` line 17: `chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M']`
Ensembl GTF uses `'MT'` not `'M'`. All MT genes are silently skipped.

**Fix**: Add `'MT'` to chr_list AND add M<->MT normalization in readGtf and TE processing.

### 3. Matching installed files vs source code (CRITICAL)

The installed `scTE_build` in the container may differ from the source repo:
- Different variable names (`chrom` vs `chr`)
- Different spacing (`[str(k)` vs `[ str(k)`)
- Different line numbers

**Rule**: Always check the ACTUAL installed file inside the container before writing patches:
```bash
apptainer exec <sif> bash -c 'grep -n "target_pattern" /opt/conda/envs/scTE/bin/scTE_build'
```
Don't assume the source repo matches what's installed.
