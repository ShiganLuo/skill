# Conda environment locations and activation

## Named conda envs

Located at `/home/luosg/miniconda3/envs/`:
- `DNA` - matplotlib, openpyxl, pptx, pandas (for report scripts)
- `smk` - snakemake 9.14.0
- `nf` - Nextflow
- `star_env` - STAR aligner

## Snakemake-managed envs (legacy --use-conda mode)

Created by `--use-conda` at `/home/luosg/Database/env/<hash>_` with:
- `<hash>_.yaml` - the conda env spec (copy of module's yaml)
- `<hash>_.env_setup_done` - marker file indicating env creation completed
- `<hash>_` (directory) - the actual conda environment

These hash-named envs (32 hex chars + `_` suffix) are created when running
Snakemake with `--use-conda --conda-prefix /home/luosg/Database/env`. The project
is transitioning to `--sdm apptainer` (SIF container) mode, which does NOT create
hash envs. When switching a project to `--sdm` mode, the old hash envs can be
safely deleted to reclaim disk space -- they are not used by the container path.

Named subdirectories (e.g. `star/`, `bedtools/`) under the same path are SIF
image directories and must NOT be deleted. Only hash-pattern entries should be
removed.

To find which hash corresponds to a module's yaml:
```bash
grep -l "name: <EnvName>" /home/luosg/Database/env/*.yaml
```

Example: DESeq2 env hash is `314f6802660401802316bab1db6ce691_` at `/home/luosg/Database/env/314f6802660401802316bab1db6ce691_`

## conda activate TypeError fix

When `CONDA_PREFIX` is empty but `CONDA_DEFAULT_ENV`/`CONDA_SHLVL` are set (shell env var pollution), `conda activate` crashes with:

```
TypeError: expected str, bytes or os.PathLike object, not NoneType
```

in `_get_deactivate_scripts`. This happens because conda tries to deactivate the "current" environment (from `CONDA_PREFIX`) but it's empty/None.

Fix: clear the stale variables before activating:
```bash
unset CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_PREFIX CONDA_PREFIX_1 2>/dev/null
eval "$(conda shell.bash hook 2>/dev/null)"
conda activate DNA
```

This is NOT a conda version bug - it's environment variable state pollution in the current shell session. The pollution typically comes from a parent process that set `CONDA_DEFAULT_ENV`/`CONDA_SHLVL` without properly setting `CONDA_PREFIX`.
