# Dockerfile generation for conda environments

Each module's conda `.yaml` has a corresponding dockerfile in the same
directory, named `<parent_dir>.dockerfile` (e.g. `modules/star/star.dockerfile`,
`modules/DESeq2/DESeq2.dockerfile`).  Generation is handled by `EnvUtil.py`
(`generate_dockerfile` classmethod), which mirrors the Apptainer
`generate_def_file` pattern.

## Dockerfile naming convention

Dockerfiles are named `<parent_dir>.dockerfile` (lowercase `.dockerfile`
extension), NOT the bare `Dockerfile`.  This avoids ambiguity in multi-module
directories and makes the file's owning module obvious at a glance.

The naming was changed from the classic `Dockerfile` to `<parent_dir>.dockerfile`
across all 64 modules under `workflow/Omics/modules/`.  `EnvUtil.py` was updated
in lockstep:

- `generate_dockerfile`: default output is `<yaml.parent.name>.dockerfile`
- `_render_dockerfile`: takes `dockerfile_filename` param (default `"Dockerfile"`
  for backward compat), used in the `# Build:` comment so `-f` references the
  actual filename
- `find_dockerfiles`: recognises three patterns -- `Dockerfile`,
  `*.dockerfile`, `*.Dockerfile` -- dedupes by resolved path, returns sorted
- `copy_artefacts` / `process_yaml_docker` / `process_dockerfile`: preserve the
  source dockerfile's actual filename when copying to output (no hard-coded
  `"Dockerfile"`)

## Dockerfile template

```dockerfile
# Auto-generated Dockerfile for <name> conda environment
# Source: <abs path to yaml>
# Build: docker build -t <name> -f <parent_dir>.dockerfile .
# Save:  docker save <name> -o /home/luosg/Database/env/<name>.tar

FROM continuumio/miniconda3:latest

COPY <yaml> /tmp/<yaml>

RUN conda env create -f /tmp/<yaml> && \
    conda clean -afy && \
    rm /tmp/<yaml>

ENV CONDA_DEFAULT_ENV=<name>
ENV PATH="/opt/conda/envs/<name>/bin:$PATH"

CMD ["bash"]
```

## Generation via EnvUtil.py

`EnvUtil.generate_dockerfile(yaml_path, dockerfile_path=None, image_name=None)`
generates a dockerfile from a conda env YAML.  No PyYAML needed -- env name is
resolved with the same 3-level fallback as Apptainer (YAML `name:` > filename
stem > directory name).

### Multi-YAML collision avoidance

When a module directory has 2+ conda YAMLs (e.g. `bcftools/` has
`bcftools.yaml` + `bcftools_population.yaml`), the first YAML gets
`<parent_dir>.dockerfile`.  If that file already exists but references a
*different* YAML (detected by checking if the YAML filename appears in the
existing dockerfile text), the generator uses `<env_name>.dockerfile` instead
of overwriting it.

### Skip rules (inherited from conda YAML parsing)

- `.schema.yaml` files are always excluded
- YAMLs with empty dependencies are skipped (e.g. `annovar.yaml`)

## Full Docker pipeline (EnvUtil.py)

`process_yaml_docker(yaml_path, ...)` is the full flow:
1. Generate `<parent_dir>.dockerfile` next to the YAML (in module dir)
2. `docker build -t <image> -f <parent_dir>.dockerfile .`
3. `docker save <image> -o <image>.tar`
4. Copy dockerfile + `.yaml` to output sub-directory (preserves module hierarchy
   and the source dockerfile filename)

Batch: `process_module_docker(module_dir, ...)` and
`process_all_docker(...)` iterate over all conda YAMLs.

See `references/docker-env-build.md` for full API + CLI (two-level:
`docker {gen,build,all}`).

## Legacy: standalone Dockerfiles

Some pre-existing dockerfiles (classic `Dockerfile` name) may still exist in the
repo.  `find_dockerfiles` recognises both `Dockerfile` and `*.dockerfile` /
`*.Dockerfile`, so legacy files are still consumed by `parse_dockerfile` /
`process_dockerfile` / `process_all` (legacy API).  The primary flow is now
YAML-first: `generate_dockerfile` from the conda YAML, producing
`<parent_dir>.dockerfile`.

## bedtools GLIBCXX issue (environment, not code)

The system libstdc++ may be too old for conda-installed bedtools.  Symptom:
`GLIBCXX_3.4.32 not found`.  Fix: set `LD_LIBRARY_PATH` to a conda env that has
a newer libstdc++ (e.g. `star_env/lib`).  This is an environment issue, not a
code fix.
