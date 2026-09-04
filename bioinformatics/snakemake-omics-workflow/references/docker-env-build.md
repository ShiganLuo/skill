# Building and saving Docker images with EnvUtil

`workflow/Omics/src/common/util/EnvUtil.py` - generates dockerfiles from conda
env YAMLs, builds Docker images, and saves them as `.tar` archives, preserving
module-level hierarchy in the output directory.

## Base image source (China mirror — IMPORTANT)

Docker Hub (`registry-1.docker.io`) is **blocked in China** — docker build /
apptainer build will timeout. The `DOCKER_FROM` constant uses the daocloud mirror:

```
docker.m.daocloud.io/continuumio/miniconda3:latest
```

**After changing the FROM source**, existing `.dockerfile` files still have the
old source. Must run `docker gen` to regenerate all `.dockerfile` files with the
new mirror before `build` or `all`.

## Dockerfile naming convention

Dockerfiles are named `<parent_dir>.dockerfile` (lowercase `.dockerfile`
extension), NOT the bare `Dockerfile`.  Examples:
- `modules/bedtools/bedtools.dockerfile`
- `modules/DESeq2/DESeq2.dockerfile`
- `modules/star/star.dockerfile`

`EnvUtil.py` was updated to support this naming:
- `generate_dockerfile`: default output is `<yaml.parent.name>.dockerfile`
- `_render_dockerfile`: takes `dockerfile_filename` param (default `"Dockerfile"`
  for backward compat), used in the `# Build:` comment so `-f` references the
  actual filename
- `find_dockerfiles`: recognises three patterns -- `Dockerfile`,
  `*.dockerfile`, `*.Dockerfile` -- dedupes by resolved path, returns sorted
- `copy_artefacts` / `process_yaml_docker` / `process_dockerfile`: preserve the
  source dockerfile's actual filename when copying to output (no hard-coded
  `"Dockerfile"`)

## Output layout

Module hierarchy below `modules/` is preserved:

```
output_dir/
  bedtools/
    bedtools.dockerfile       (copied, preserves source filename)
    bedtools.yaml             (copied)
    bedtools.tar              (docker save)
  openms/
    searchengine/
      openms.dockerfile
      openms.yaml
      openms-searchengine.tar
```

## Image name resolution (3-level fallback)

1. **YAML `name:` field** - highest priority.
2. **Filename stem** - `bedtools.yaml` -> `bedtools`.
3. **Directory name** - last resort.

## EnvUtil Docker API

### YAML-first (primary)

| Method | Purpose |
|--------|---------|
| `generate_dockerfile(yaml_path, dockerfile_path, image_name)` | Generate `<parent_dir>.dockerfile` from conda YAML |
| `process_yaml_docker(yaml_path, ...)` | Full pipeline: generate dockerfile -> build -> save -> copy |
| `process_module_docker(module_dir, ...)` | Process all YAMLs in one module dir |
| `process_all_docker(...)` | Batch process all YAMLs under `modules_dir` |

### Dockerfile-first (legacy / build-from-existing)

| Method | Purpose |
|--------|---------|
| `parse_dockerfile(path)` | Extract image_name, yaml_filename, source_path, save_path |
| `resolve_image_name(path, parsed)` | 3-level fallback (comment > YAML name > dir name) |
| `build_image(path, image_name, no_cache)` | `docker build -t <name> -f <dockerfile> .` |
| `save_image(image_name, output_tar)` | `docker save <name> -o <tar>` |
| `copy_artefacts(path, output_subdir, parsed)` | Copy dockerfile + conda YAML to output dir |
| `process_dockerfile(path, ...)` | Full pipeline: build -> save -> copy |
| `process_all(...)` | Batch process all dockerfiles under `modules_dir` |

## CLI usage (two-level: backend + action, with shorthand flags)

All flags have single-letter shorthands: `-m` `--modules-dir`, `-o` `--output-dir`,
`-y` `--yaml`, `-f` `--file`, `-e` `--env-name`, `-s` `--skip-existing`,
`-t` `--build-timeout`.

**`gen` does NOT take `-o`** -- build files are generated next to the source YAML.
**`build` and `all` REQUIRE `-o`** -- image output must be explicitly specified;
the module-level hierarchy under `--modules-dir` is preserved in the output dir.

**All three subparser levels use `required=True`** so missing `backend` or `action`
prints usage + error instead of crashing with AttributeError.

```bash
# Docker: YAML -> .dockerfile -> image -> .tar
python EnvUtil.py docker gen                                  # YAML -> .dockerfile only (next to YAML)
python EnvUtil.py docker build  -o /home/luosg/Database/env   # .dockerfile -> image -> .tar
python EnvUtil.py docker all    -o /home/luosg/Database/env   # YAML -> .dockerfile -> image -> .tar

# Single YAML (gen or all mode)
python EnvUtil.py docker gen  -y .../modules/bedtools/bedtools.yaml
python EnvUtil.py docker all  -y .../modules/bedtools/bedtools.yaml -o /home/luosg/Database/env

# Single .dockerfile (build mode)
python EnvUtil.py docker build -f .../modules/bedtools/bedtools.dockerfile -o /home/luosg/Database/env

# Rebuild even if tar exists
python EnvUtil.py docker all -o /home/luosg/Database/env --no-skip-existing

# Pass --no-cache to docker build
python EnvUtil.py docker all -o /home/luosg/Database/env --no-cache
```

**Three actions per backend:**
- `gen` -- YAML -> build file (`.dockerfile`), no image build, no `-o` needed. `-y` for single, omit for all.
- `build` -- build file -> image (`.tar`). `-f` for single, omit for all found under `-m`. `-o` required.
- `all` -- full pipeline: YAML -> build file -> image -> tar, build file synced to output. `-y` for single, omit for all. `-o` required.

## Multi-YAML collision avoidance

When a module directory has 2+ conda YAMLs, `generate_dockerfile` checks if a
`<parent_dir>.dockerfile` already exists. If it does and references a *different*
YAML, the generator writes `<env_name>.dockerfile` instead of overwriting.

## Relationship to Apptainer flow

The Apptainer SIF flow (`references/apptainer-sif-build.md`) is the **primary**
container workflow for Snakemake. Both flows share the same `EnvUtil` class, same
conda YAML parsing, same env name resolution, and same module hierarchy preservation.
Both use the same daocloud China mirror for the base image.
