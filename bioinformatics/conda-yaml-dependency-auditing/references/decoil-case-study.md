# Case Study: decoil Container Build Failure

## Symptoms
- `EnvUtil.py apptainer all` reported "Build complete" then "SIF too small (229 MB)"
- `apptainer exec decoil.sif decoil` → "executable file not found in $PATH"
- `pip list` inside container showed only pip/setuptools/wheel

## Root Cause
`decoil==2.0.2` depends on:
- `datrie` — needs `gcc` to compile C extensions
- `pybedtools` — needs `bedtools` (bioconda system package)
- `deeptoolsintervals` — needs `gcc` + `htslib`

Original YAML only had:
```yaml
dependencies:
  - python=3.9
  - pip
  - pip:
      - decoil=2.0.2
```

Missing: `gcc_linux-64`, `gxx_linux-64`, `bedtools`, `htslib`

## Fix
```yaml
dependencies:
  - python=3.9
  - pip
  - gcc_linux-64
  - gxx_linux-64
  - bedtools
  - htslib
  - pip:
      - decoil==2.0.2
```

## Key lesson
When a pip package fails to install, check `pip install` output for:
- `error: command 'gcc' failed` → add `gcc_linux-64`/`gxx_linux-64`
- `Building wheel for <pkg>` + C compilation errors → missing compiler
- Package wrapping a bioinformatics tool → add the tool as conda dep