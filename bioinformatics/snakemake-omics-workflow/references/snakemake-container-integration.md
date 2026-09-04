# Snakemake container: directive integration

The Omics Snakemake project uses Apptainer SIF images as containers. Each rule
that has a `conda:` directive pointing to a `.yaml` file should also have a
`container:` directive that points to the corresponding SIF file. The `sif()`
function in `common.smk` resolves the SIF path automatically.

## The sif() function (in modules/common/common.smk)

```python
_ENV_MAP = config.get("env", {})

def sif(yaml_filename: str) -> str:
    """Resolve SIF path for a conda env YAML.

    Priority:
    1. config["env"][<yaml_stem>] -- explicit path from config
    2. config["env"]["env_dir"] / <module_dir> / <yaml_stem>.sif -- auto-prefixed

    Raises ValueError if yaml_stem not in config["env"] AND no "env_dir" set.
    """
    stem = os.path.splitext(os.path.basename(yaml_filename))[0]
    if stem in _ENV_MAP:
        return _ENV_MAP[stem]
    env_dir = _ENV_MAP.get("env_dir")
    if not env_dir:
        raise ValueError(...)
    module_dir = os.path.basename(workflow.basedir)
    return os.path.join(env_dir, module_dir, f"{stem}.sif")
```

Key design:
- NO hardcoded paths. `env_dir` comes from `config["env"]["env_dir"]`.
- Uses YAML filename stem (e.g. `star.yaml` -> `star`), NOT the `name:` field
  inside the YAML. This is simpler and avoids file I/O.
- If `env_dir` is None/missing and the stem is not explicitly mapped, `sif()`
  raises a `ValueError` with a helpful message.
- For cases where yaml stem != SIF filename (e.g. `gatk.yaml` but SIF is
  `gatk4.sif`), the user adds an explicit mapping in config:
  `"gatk": "/path/to/gatk4.sif"`.

## Adding container to a rule

After every `conda: "xxx.yaml"` directive, add a `container:` directive:

```python
rule star_align:
    ...
    conda:
        "star.yaml"
    container:
        sif("star.yaml")
    ...
```

The argument to `sif()` must match the argument to `conda:` -- same YAML file.

### When NOT to add container

- Rules with `conda:` pointing to a config reference (not a `.yaml` filename),
  e.g. `conda: config['conda']['RNA-SNP']` -- these use an external conda env
  path, not a SIF. Skip them.
- Rules with no `conda:` at all (e.g. `rule all`) -- pure orchestration.
- Rules where the conda yaml is actually a `.schema.yaml` file.

## Config JSON design (single env dict, no env_dir field)

Every workflow config JSON carries a single `env` dict. The `env_dir` key lives
INSIDE this dict, not as a separate top-level field:

```json
{
    "ROOT_DIR": null,
    "env": {
        "env_dir": null,
        "star": null,
        "hisat2": null,
        "cutadapt": null,
        "DESeq2": null,
        "gatk": null,
        ...
    },
    ...
}
```

**IMPORTANT**: The env keys must be the YAML filename stems (without `.yaml`)
used by THIS workflow's modules -- not a generic empty dict. Each workflow's
config should list only the environments it actually uses. For example,
RNAseq.json lists 14 env entries (star, hisat2, cutadapt, trim-galore,
trimmomatic, TEtranscripts, DESeq2, StringTie, RmrRNA, bowtie2, gatk, arriba,
function, RNAseq_report), while tRNAseq.json lists only 3 (cutadapt, fumitools,
mimseq).

User fills in either:
- `"env_dir": "/home/luosg/Database/env"` and leaves the rest as null -- auto
  resolves to `env_dir/<module_dir>/<yaml_stem>.sif`
- Or individual overrides like `"star": "/custom/path/star.sif"` -- takes priority
- For mismatched names (yaml stem != SIF name), e.g. `gatk.yaml` -> `gatk4.sif`:
  set `"gatk": "/path/to/gatk4.sif"` explicitly

## Config schema changes

```json
{
    "env": {
        "type": "dict",
        "required": false,
        "properties": {
            "env_dir": {"type": "str", "nullable": true, "required": false},
            "star": {"type": "str", "nullable": true, "required": false},
            ...
        }
    }
}
```

## Subworkflow config propagation

Every `*_config` dict in a `subworkflow/*.smk` must pass `env` to the module:

```python
star_config_for_TEtranscripts = {
        "indir": trimmed_fastq_dir,
        "outdir":  f"{outdir}/common/3_raw_bam",
        "logdir": logdir,
        "env": config.get("env", {}),
        ...
}
module star_for_TEtranscripts:
    snakefile: "../modules/star/star.smk"
    config: star_config_for_TEtranscripts
```

**Exception**: Subworkflows that use `dict(config)` (e.g.
`Population_genomics.smk`, `spatial_transcriptomics.smk`) automatically
inherit `env` -- no need to add it explicitly.

## Batch container insertion

When batch-adding `container:` to all rules in `modules/`, the pattern is:
1. Find all `conda:` directives that point to a `.yaml` file (skip config-path
   references and `.schema.yaml`).
2. Insert `container:` + `sif("xxx.yaml")` AFTER the yaml line, not between
   `conda:` and the yaml line.
3. Handle both inline (`conda: "xxx.yaml"`) and multiline (`conda:\n    "xxx.yaml"`)
   patterns.
4. Skip files that don't `include: "../common/common.smk"` (they don't have `sif()`).
5. Skip files that already have `container:` directives.

## SIF naming conventions

SIF file names are determined by the YAML `name:` field at build time (via
EnvUtil), but `sif()` uses the YAML filename stem for lookup. When they differ,
the user must add an explicit mapping in config.

| Module dir          | YAML file          | YAML name: | SIF path                          | config key |
|---------------------|--------------------|------------|-----------------------------------|------------|
| star                | star.yaml          | star       | env/star/star.sif                 | star       |
| gatk                | gatk.yaml          | gatk4      | env/gatk/gatk4.sif                | gatk       |
| igv                 | igv.yaml           | hisat2     | env/igv/hisat2.sif               | igv        |
| msisensor-pro       | msisensro_pro.yaml | samtools   | env/msisensor-pro/samtools.sif    | msisensro_pro |
| PeakCalling_report  | report.yaml        | report     | env/PeakCalling_report/report.sif | PeakCalling_report |

## Running Snakemake with containers

Use `--sdm apptainer` (NOT `--use-conda`). Do NOT combine both. In this project,
`--sdm` and `--singularity-args` are TOP-LEVEL `run.py` arguments (not passed
via `--snakemake-args`). `--sdm` is a bare flag (store_const, const='apptainer')
-- no value needed on the command line:

```bash
python run.py \
    -m meta.tsv \
    -w ncRNAseq \
    -o output \
    --sdm
```

When `--singularity-args` is omitted, `run.py` auto-generates `--bind` from the
config JSON (see "Auto bind-path generation" below). To override, pass
`--singularity-args '--bind /custom/path'` explicitly.

This produces a snakemake command like:
```bash
snakemake -s .../subworkflow/ncRNAseq.smk --configfile ... --cores 48 \
    --rerun-triggers mtime \
    --sdm apptainer \
    --singularity-args '--bind /home/luosg/Database,...,/tmp'
```

- `--sdm apptainer` -- Snakemake reads `container:` directives and launches SIF.
  When `container:` is present, `conda:` is ignored (unless `--use-conda` is also
  passed, which causes double isolation: conda inside container -- slow and error-prone).
- `--singularity-args '--bind ...'` -- mount host paths into the container.
  Auto-generated from config JSON when not user-specified (see below).
- When `--sdm` is set, `run.py` automatically OMITS `--use-conda`, `--conda-prefix`,
  and `--conda-frontend` from the snakemake command. When `--sdm` is absent,
  `--conda-prefix` is required (enforced by `setup_normal_args`).

### Auto bind-path generation

When `--sdm` is set and `--singularity-args` is NOT user-specified, `run.py`
calls `_collect_bind_paths(config_json_path)` to automatically determine which
host directories to bind-mount. This function:

1. Recursively walks all string values in the runtime config JSON (raw.json)
2. Strings containing `/` are treated as paths -- files yield their parent
   directory, directories are kept as-is
3. Subdirectories are collapsed into their parents (e.g.
   `/home/luosg/Database/env/star` collapses into `/home/luosg/Database/env`)
4. `/tmp` is always appended (STAR/bowtie2/Snakemake temp files)
5. Result is joined into `--singularity-args '--bind /path1,/path2,/tmp'`

This means the user no longer needs to manually specify `--singularity-args`.
The bind list is derived from the actual paths in the config, so it always
covers: SIF images, reference genomes, ROOT_DIR, indir/outdir/logdir, and /tmp.

User-specified `--singularity-args` always takes precedence and disables
auto-generation. Legacy `--snakemake-args --singularity-args ...` is also
detected and not duplicated.

### Bind mount checklist

When `--singularity-args` is auto-generated (the default with `--sdm`), the
following paths are automatically detected from config JSON and bound:

| Path | Why | Auto-detected? |
|------|-----|----------------|
| Database dir (e.g. `/home/luosg/Database`) | Reference genomes, adapter files, blacklist, SIF images | Yes (from `env.*.sif`, `genome.fasta`, `genome.gtf`) |
| ROOT_DIR (e.g. `/home/luosg/Data/genomeStability`) | `src/common/` Python modules loaded via sys.path | Yes (from `ROOT_DIR`) |
| `/tmp` | STAR/bowtie2/Snakemake temporary files | Yes (always appended) |
| indir/outdir/logdir (if outside above) | Input FASTQ, output, logs | Yes (from `indir`, `outdir`, `logdir`) |

Rule of thumb: auto-generation covers all path prefixes in the config JSON.
Only override `--singularity-args` manually when you need a non-config path
(e.g. a bind for a tool that reads from an unlisted directory).

## Pitfalls

- **NO hardcoded paths**: `sif()` must never contain hardcoded filesystem paths.
  The `env_dir` must come from config, and if unset, raise ValueError.
  (Do NOT add `env_dir` as a separate top-level config field -- it lives inside the `env` dict.)
- **Batch container insertion order**: When batch-adding `container:` after
  `conda:`, the container directive must go AFTER the yaml line, not between
  `conda:` and the yaml. A script that inserts right after the `conda:` line
  will push the yaml line out of position and break the rule.
- **Config-path conda directives**: `conda: config['conda']['RNA-SNP']` is NOT
  a yaml file reference -- do not add `container:` to these rules.
- **`workflow.basedir` dependency**: `sif()` uses `workflow.basedir` to get
  `module_dir`. This works because Snakemake sets `workflow.basedir` to the
  directory of the Snakefile being parsed at module-include time.
- **dict(config) subworkflows**: Subworkflows using `dict(config)` or
  `dict(base_config)` automatically pass `env` through -- don't add it again.
- **YAML stem vs env_name**: `sif()` uses the YAML filename stem (e.g. `gatk`),
  NOT the `name:` field inside the YAML (e.g. `gatk4`). When they differ, the
  user must add an explicit mapping in the config `env` dict.
- **No `_read_env_name()`**: The old `_read_env_name()` function was removed.
  Do not re-add it -- reading the YAML file at parse time is unnecessary I/O
  when the filename stem is sufficient.
- **`--sdm apptainer` only, NOT `--use-conda`**: When both are passed, Snakemake
  runs conda INSIDE the container (double isolation). Just use `--sdm` (bare flag,
  no value) with `--singularity-args '--bind ...'`. See "Running Snakemake with containers"
  above. Apptainer IS singularity (open-source fork) -- no separate `singularity`
  choice is needed or offered.
- **`run.py` `build_snakemake_cmd` container detection**: `run.py` has top-level
  `--sdm` (store_const flag, const='apptainer', no value needed) and
  `--singularity-args` argparse params.
  When `--sdm` is set, `build_snakemake_cmd` OMITS `--use-conda`, `--conda-prefix`,
  and `--conda-frontend` entirely and emits `--sdm apptainer` + `--singularity-args`
  in the snakemake command. When `--sdm` is absent, `--conda-prefix` is required
  (enforced by `setup_normal_args` via the `_detect_singularity()` helper).
  Backward compat: legacy `--snakemake-args --sdm apptainer` is still detected by
  `_detect_singularity()`. The `--conda-prefix` argparse default is `None` (was
  `/data/pub/zhousha/env/mutation_0.1` -- a foreign path that caused
  `EnvironmentFileNotFound` when snakemake tried to create a conda env inside the
  SIF container using that nonexistent prefix).
  Note: `--sdm` is a bare flag (`--sdm` with no value), NOT `--sdm apptainer`.
  Apptainer IS singularity (open-source fork), so no `singularity` choice is
  offered -- `apptainer` covers it.
- **Single `env` dict, no separate `env_dir` field**: User corrected: one dict
  is sufficient. `env_dir` lives INSIDE the `env` dict, not as a top-level
  config field. Do NOT add a separate `env_dir` field to config JSON.
- **YAML stem as lookup key, not `name:` field**: User corrected: reading the
  YAML file to get `name:` is "多此一举" (unnecessary). Use the filename stem
  directly. For mismatches (gatk.yaml -> gatk4.sif), explicit config mapping.
- **Procedure paths must be bare command names under `--sdm`**: When running
  with `--sdm apptainer`, rules execute INSIDE SIF containers. The `Procedure`
  section of config JSON (e.g. `config/ncRNAseq.json`) must use bare command
  names (`"STAR": "STAR"`, `"samtools": "samtools"`, `"bedtools": "bedtools"`,
  `"trim_galore": "trim_galore"`, `"featureCounts": "featureCounts"`,
  `"seqtk": "seqtk"`) -- NOT host absolute paths like
  `/home/luosg/miniconda3/envs/star_env/bin/STAR`. Host paths do not exist
  inside the container, causing `FileNotFoundError` at runtime (e.g.
  `three_pass.log` error: `No such file or directory: '/home/luosg/miniconda3/envs/star_env/bin/STAR'`).
  The SIF images already contain these tools on PATH. Exception: tools installed
  at a specific path inside the SIF (e.g.
  `"tailer": "/home/luosg/Database/env/.../bin/Tailer"`) keep their
  container-internal path. When `--sdm` is NOT used (conda mode), the `.smk`
  files fall back to bare names via `or "STAR"` anyway, so bare names work in
  both modes. ALWAYS check `Procedure` paths in config JSON when switching a
  workflow from conda mode to `--sdm` mode.
- **Auto bind-path generation**: `_collect_bind_paths()` in `run.py` scans the
  runtime config JSON (raw.json) for all string values containing `/`, resolves
  files to their parent directory, collapses subdirectories into parents, and
  appends `/tmp`. The result is passed as `--singularity-args '--bind ...'`
  automatically when `--sdm` is set and `--singularity-args` is not user-specified.
  This means `run.sh` only needs `--sdm` -- no manual `--singularity-args`.
  User-specified `--singularity-args` always takes precedence. Non-existent paths
  that contain `/` (e.g. a null-derived path like `"outdir/output"`) are kept
  as-is since `_collect_bind_paths` uses `os.path.abspath` without requiring
  existence -- only `os.path.isfile` is checked to decide dirname vs keep.
