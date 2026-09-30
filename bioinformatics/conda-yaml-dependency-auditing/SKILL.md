---
name: conda-yaml-dependency-auditing
description: Diagnose silent pip failures from missing conda YAML deps.
tags: [apptainer, conda, container, bioinformatics, pip]
triggers:
  - pip install failed in container
  - SIF too small
  - executable not found in container
  - conda yaml missing dependencies
  - silent build failure
---

# Conda YAML Dependency Auditing

When building Apptainer/conda containers, pip packages with C extensions or system library dependencies fail silently if the conda YAML doesn't include their build-time and runtime requirements. `apptainer build` returns 0, but the pip package is never installed.

## Diagnostic Flow

1. **SIF unusually small** → pip packages probably didn't install
2. **Executable not found inside container** → check `pip list` inside SIF
3. **`pip list` shows only pip/setuptools/wheel** → pip install section was skipped or failed
4. **Try `pip install <pkg>` manually inside container** → reveals actual compilation errors

```bash
# Quick check: is the package installed?
apptainer exec <sif> bash -c 'export PATH="/opt/conda/envs/<env>:$PATH" && pip list | grep -i <pkg>'

# Diagnose: what failed?
apptainer exec <sif> bash -c 'export PATH="/opt/conda/envs/<env>:$PATH" && pip install <pkg>==<version> 2>&1 | tail -30'
```

## Common Missing Dependencies

### C extension packages (need compilers)
Packages like `datrie`, `pysam`, `numpy` (from source) need `gcc`/`gxx`:
```yaml
dependencies:
  - gcc_linux-64    # conda-forge compiler
  - gxx_linux-64    # conda-forge C++ compiler
```

### Bioinformatics tools needing system libraries
- `pybedtools` → needs `bedtools` (bioconda)
- `pysam` / `deeptoolsintervals` → needs `htslib` (conda-forge/bioconda)
- `datrie` → needs `gcc_linux-64`

### Pattern: check wheel availability
If `pip install` shows `Building wheel for <pkg>` + compilation error, the package needs a system dependency. If it shows `Using cached ... .whl`, it has a prebuilt wheel and doesn't need compilers.

```bash
# Check if wheel exists (no compilation needed)
pip install --dry-run <pkg>==<version> 2>&1 | grep -E "(Using cached|Building wheel)"
```

## YAML Template for bioconda packages with pip deps

```yaml
name: <env>
channels:
  - conda-forge
  - bioconda
dependencies:
  - python=3.9
  - pip
  - gcc_linux-64    # if pip deps have C extensions
  - gxx_linux-64    # if pip deps have C extensions
  - htslib           # if pip deps use htslib (pysam, etc.)
  - bedtools         # if pip deps wrap bedtools (pybedtools)
  - pip:
      - <package>==<version>
```

## SIF Size Thresholds by Backend

| Backend    | Base image size | Expected SIF (minimal env) | Threshold in EnvUtil |
|------------|----------------|---------------------------|---------------------|
| micromamba | ~30 MB         | 50-150 MB                 | 350 MB (conda) / 100 MB (uv) |
| conda      | ~300 MB        | 350-500 MB                | 350 MB |
| uv         | ~150 MB        | 150-250 MB                | 100 MB |

**Pitfall**: A micromamba SIF of 229 MB may look "too small" by the 350 MB threshold but be legitimate if the env only has python + pip packages. The real check is whether pip packages are importable (EnvUtil's `_verify_pip_packages`).

## Debugging Checklist

1. `apptainer exec <sif> micromamba env list` — does the env exist?
2. `apptainer exec <sif> bash -c 'PATH=... pip list'` — are pip packages installed?
3. `pip install <pkg> 2>&1 | grep ERROR` — what's the actual failure?
4. Check if failed packages need: compilers (gcc), system libs (htslib, bedtools), or special build flags
5. Add missing deps as conda dependencies in YAML, regenerate .def, rebuild