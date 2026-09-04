# Building Apptainer/Singularity SIF images with EnvUtil

`workflow/Omics/src/common/util/EnvUtil.py` generates Apptainer `.def` files from
conda env YAMLs and builds `.sif` images, preserving module-level hierarchy in
the output directory.

This is the **primary** container workflow for Snakemake - Snakemake's `container:`
directive uses Singularity/Apptainer internally, not Docker. It accepts:
- `docker://image:tag` (pull from registry)
- `/path/to/image.sif` (local SIF file)
- It does NOT accept `.tar` archives from `docker save`.

## Snakemake container usage in this project

Rules use `container: sif("xxx.yaml")` where `sif()` is defined in
`modules/common/common.smk`. The `sif()` function uses the YAML filename stem
(e.g. `star.yaml` -> `star`) as the lookup key -- it does NOT read the YAML
`name:` field. It resolves the SIF path via `config["env"]` (single dict with
`env_dir` key and optional per-env overrides). For cases where yaml stem !=
SIF name (e.g. `gatk.yaml` -> `gatk4.sif`), the user adds an explicit mapping
`"gatk": "/path/to/gatk4.sif"` in the config env dict. See
`references/snakemake-container-integration.md` for full details.

System has `apptainer 1.3.2` installed at `/usr/bin/apptainer` (Singularity-compatible).

## Base image source (China mirror — IMPORTANT)

Docker Hub (`registry-1.docker.io`) is **blocked in China** — apptainer build
will timeout with `i/o timeout` after 30s. Both `APPTAINER_FROM` and
`DOCKER_FROM` constants use the daocloud mirror:

```
docker.m.daocloud.io/continuumio/miniconda3:latest
```

Verify mirror reachability before building:
```bash
curl -sI --connect-timeout 10 https://docker.m.daocloud.io/v2/   # 401 = OK (reachable, unauthorized)
curl -sI --connect-timeout 10 https://registry-1.docker.io/v2/    # timeout = Docker Hub blocked
```

**After changing the FROM source**, existing `.def` files still have the old
source. Must run `apptainer gen` to regenerate all `.def` files with the new
mirror before `build` or `all`.

## Dockerfile naming convention

Dockerfiles have been renamed from the default `Dockerfile` to
`<parent_dir>.dockerfile` (e.g. `modules/star/star.dockerfile`,
`modules/DESeq2/DESeq2.dockerfile`). The `find_dockerfiles()` method in
`EnvUtil.py` recognises three patterns to support both old and new naming:

1. `Dockerfile` (classic, legacy)
2. `*.dockerfile` (new convention)
3. `*.Dockerfile` (alternative case)

Results are deduplicated by resolved path and sorted.

When generating new dockerfiles via `generate_dockerfile()`, the default output
name is `<parent_dir>.dockerfile`. If a dockerfile already exists but references
a different YAML, the generator falls back to `<env_name>.dockerfile` to avoid
clobbering (multi-env modules).

## Dockerfile naming convention

`.def` files are named `<parent_dir>.def` (e.g. `modules/star/star.def`,
`modules/DESeq2/DESeq2.def`), matching the `<parent_dir>.dockerfile` convention.
Generation is handled by `EnvUtil.py` (`generate_def_file` classmethod).

- `generate_def_file`: default output is `<yaml.parent.name>.def`
- `_render_def`: takes `def_filename` param (default `"env.def"` for backward
  compat), used in the `# Build:` comment so the filename is correct
- Multi-YAML collision avoidance: if `<parent_dir>.def` already exists but
  references a *different* YAML, the generator uses `<env_name>.def` instead

## Output layout

`.def` files are generated in the module directory (next to the YAML). SIF images
and copied def/yaml files preserve module hierarchy:

```
modules/bedtools/bedtools.def                  # generated in module dir
modules/openms/searchengine/searchengine.def   # nested module

output_dir/
  bedtools/
    bedtools.def          (copied)
    bedtools.yaml         (copied)
    bedtools.sif          (apptainer build)
  openms/
    searchengine/
      searchengine.def
      searchengine.yaml
      searchengine.sif
```

## Environment naming convention (MANDATORY)

Every conda env YAML MUST follow this naming rule:

- **YAML filename = `<module_subdir_name>.yaml`**
- **YAML `name:` field = `<module_subdir_name>`** (same as filename stem)
- **SIF filename = `<module_subdir_name>.sif`**

This 1:1:1 correspondence (yaml stem = env name = SIF name) ensures `sif()`
can resolve paths purely from the YAML filename without reading file contents.

Examples (correct):
```
modules/star/star.yaml          name: star       -> star.sif
modules/bedtools/bedtools.yaml  name: bedtools   -> bedtools.sif
modules/openms/psmfdr/psmfdr.yaml  name: psmfdr  -> psmfdr.sif
```

**Forbidden patterns:**
- Multiple submodules sharing the same YAML filename when they each need their
  OWN independent environment (e.g. all named `openms.yaml` in different dirs).
  Each independent yaml MUST have a unique stem.
- YAML `name:` field diverging from filename stem (e.g. `gatk.yaml` with
  `name: gatk4`) -- if a different name is needed, rename the YAML file too.

**Submodule YAML sharing (IMPORTANT):** Submodules do NOT each require their own
yaml. A submodule can reference its parent's shared yaml via
`conda: "../<tool>.yaml"` (e.g. gatk_RNAseq uses `../gatk.yaml`). Only when a
submodule needs a DIFFERENT environment does it need its own `<subtool>.yaml`,
and that file's stem must be unique among all yaml stems in the project.

**Exception:** If a YAML name genuinely must differ from the directory name
(e.g. upstream version pinning), add an explicit entry in the config `env`
dict: `"yaml_stem": "/path/to/actual.sif"`. This is a last resort, not a
default practice.

## Env name resolution

`sif()` in `common.smk` uses the YAML filename stem as the lookup key:

1. **`config["env"][<yaml_stem>]`** -- explicit path from config (highest priority).
2. **`config["env"]["env_dir"]` + `<module_dir>/<yaml_stem>.sif`** -- fallback
   by convention. `env_dir` must be set by user (no hardcoded default).

If neither resolves, `sif()` raises `ValueError` with a helpful message.

## EnvUtil Apptainer API

| Method | Purpose |
|--------|---------|
| `find_env_yamls(module_dir)` | Find conda env YAMLs in a dir (excludes `.schema.yaml`) |
| `find_all_env_yamls()` | Find all conda env YAMLs under `modules_dir` |
| `find_def_files()` | Find all `.def` files under `modules_dir` |
| `parse_conda_yaml(yaml_path)` | Lightweight line-based parse: name, channels, dependencies |
| `parse_def_file(def_path)` | Extract env_name and yaml_filename from `.def` comments |
| `resolve_env_name(yaml_path, fallback)` | 3-level fallback env name resolution |
| `resolve_env_name_from_def(def_path, parsed)` | Resolve env name from `.def` (Build comment > dir name) |
| `generate_def_file(yaml_path, def_path, env_name)` | Generate `.def` next to YAML as `<parent_dir>.def` |
| `build_sif(def_path, output_sif, fakeroot, force)` | `apptainer build --fakeroot --force <sif> <def>` |
| `process_yaml(yaml_path, ...)` | Full pipeline: generate def -> build SIF -> copy to output |
| `process_def_file(def_path, ...)` | Build SIF from existing `.def` + copy artefacts to output |
| `process_module(module_dir, ...)` | Process all YAMLs in one module dir |
| `process_all_apptainer(...)` | Batch process all YAMLs under `modules_dir` |
| `process_all_def(...)` | Batch build SIF from all `.def` files under `modules_dir` |

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
# Apptainer: YAML -> .def -> .sif
python EnvUtil.py apptainer gen                                  # YAML -> .def only (next to YAML)
python EnvUtil.py apptainer build  -o /home/luosg/Database/sif   # .def -> .sif
python EnvUtil.py apptainer all    -o /home/luosg/Database/sif   # YAML -> .def -> .sif

# Single YAML (gen or all mode)
python EnvUtil.py apptainer gen  -y .../modules/bedtools/bedtools.yaml
python EnvUtil.py apptainer all  -y .../modules/bedtools/bedtools.yaml -o /home/luosg/Database/sif

# Single .def file (build mode)
python EnvUtil.py apptainer build -f .../modules/bedtools/bedtools.def -o /home/luosg/Database/sif

# Disable --fakeroot
python EnvUtil.py apptainer all -o /home/luosg/Database/sif --no-fakeroot

# Force rebuild even if SIF exists
python EnvUtil.py apptainer all -o /home/luosg/Database/sif --no-skip-existing
```

**Three actions per backend:**
- `gen` -- YAML -> build file (`.def`), no image build, no `-o` needed. `-y` for single, omit for all.
- `build` -- build file -> image (`.sif`). `-f` for single, omit for all found under `-m`. `-o` required.
- `all` -- full pipeline: YAML -> build file -> image, build file synced to output. `-y` for single, omit for all. `-o` required.

## Apptainer fakeroot: %files path pitfall (IMPORTANT)

In fakeroot mode, the `/tmp/` directory inside the container is NOT the same
namespace as the host `/tmp/`. If `%files` copies the YAML to `/tmp/<yaml>` and
`%post` runs `conda env create -f /tmp/<yaml>`, conda will report
`EnvironmentFileNotFound` even though the apptainer log says "Copying X to /tmp/X".

**Fix**: target `/opt/conda/` (which IS persistent across %files -> %post):

```
%files
    <yaml> /opt/conda/<yaml>

%post
    conda env create -f /opt/conda/<yaml> && \
        conda clean -afy && \
        rm /opt/conda/<yaml>
```

This is already baked into the `_render_def` template -- do not change back to `/tmp/`.

## CLI argument validation (IMPORTANT - added Aug 2026)

EnvUtil.py validates `-y` and `-f` arguments after `parse_args()`:

- **`-y/--yaml`**: suffix must be `.yaml`/`.yml`; file must exist; content must
  contain `channels:` or `dependencies:` (lightweight conda-env format check).
  Rejects `.def`, `.dockerfile`, or non-conda YAMLs with `parser.error()`.
- **`-f/--file`**: suffix must match backend (`.def` for apptainer, `.dockerfile`
  for docker); file must exist.

**Critical failure mode this prevents**: passing a `.def` file to `-y` causes
EnvUtil to generate a `.def` that copies itself into the container and runs
`conda env create -f /opt/conda/DESeq2.def`. Conda cannot parse `.def` format,
reports `EnvironmentSpecPluginNotDetected`, and the SIF is built **empty** --
no conda env, no Rscript, no tools. The build appears to succeed (exit 0, SIF
file created) but the container is useless.

**Always pass the conda YAML to `-y`, not the `.def` file:**
```bash
# CORRECT
python EnvUtil.py apptainer all -y .../modules/DESeq2/DESeq2.yaml -o ~/Database/env/

# WRONG - will produce an empty SIF (now rejected by validation)
python EnvUtil.py apptainer all -y .../modules/DESeq2/DESeq2.def -o ~/Database/env/
```

## Key design decisions

- **Def file generated in module dir, not output dir**: version-controllable + diffable.
- **Lightweight YAML parser** (`parse_conda_yaml`): line-based regex, no PyYAML.
- **`--fakeroot` default**: Apptainer definition files require root for `%post`.
- **%files targets /opt/conda/ not /tmp/**: fakeroot namespace mismatch (see above).
- **Modules without Dockerfiles**: Apptainer flow works from YAMLs directly.
- **Multiple YAMLs per module**: collision avoidance falls back to `<env_name>.def`.
- **CLI arg validation**: `-y` rejects non-YAML files; `-f` rejects wrong backend suffixes.

## Dockerfile generation (parallel to .def)

`EnvUtil.py` also supports Dockerfile generation from conda YAMLs. Both `.def` and
`.dockerfile` use the same `<parent_dir>` naming convention and collision avoidance.
See `references/docker-env-build.md` for full Docker API + CLI details.

## Docker vs Apptainer decision

Chose **direct Apptainer build** because:
- Fewer dependencies (no Docker daemon needed)
- Works from existing conda YAMLs without pre-generated Dockerfiles
- `.def` files are human-readable and version-controllable
- Snakemake consumes `.sif` directly, no format conversion needed
