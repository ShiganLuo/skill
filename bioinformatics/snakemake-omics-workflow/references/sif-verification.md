# Verifying SIF image contents

After building or updating a SIF, verify that expected tools and pip packages
are correctly installed inside the container.

## Check if a command exists inside a SIF

```bash
apptainer exec /path/to/env/star/star.sif bash -c 'which Tailer; find /opt/conda/envs/star -name "Tailer"; pip show jla-tailer'
```

Output (success):
```
/opt/conda/envs/star/bin/Tailer
/opt/conda/envs/star/bin/Tailer
Name: jla-tailer
Version: 0.1.18
```

This three-pronged check covers:
1. `which <cmd>` -- is it on PATH inside the container?
2. `find /opt/conda/envs/<name> -name "<cmd>"` -- does the binary exist?
3. `pip show <package>` -- is the pip package metadata present?

## Conda env structure inside SIF

EnvUtil-built SIFs use `continuumio/miniconda3:latest` as the base image.
Conda envs are created at `/opt/conda/envs/<env_name>/`. The `%environment`
section sets `PATH="/opt/conda/envs/<env_name>/bin:$PATH"` so tools are
directly available via `apptainer exec`.

For pip-installed packages (e.g. `jla-tailer` in star.yaml), the package
lands at `/opt/conda/envs/<env_name>/lib/python<X.Y>/site-packages/`.

## When to verify

- After adding new dependencies to a YAML and rebuilding the SIF
- After adding pip dependencies (pip install can fail silently in conda env create)
- When a tool inside the SIF is not found at runtime
- **After ANY SIF build** -- `apptainer build` can exit 0 even if `%post`
  commands failed. The SIF file is created regardless, but the conda env may
  be missing inside. Always verify the env exists, not just the SIF file.

## Verifying the conda env was actually created (CRITICAL)

`apptainer build` exits 0 even when `%post` commands fail -- the SIF file is
created from the base image regardless. A build that reports "Build complete"
can still produce an empty container with no conda env.

**Failure mode**: If `conda env create -f /opt/conda/<yaml>` fails inside
`%post` (e.g. wrong file format, network error, solver conflict), the SIF is
still created but `/opt/conda/envs/<env_name>/` does not exist. Tools like
`Rscript` are missing, causing `command not found` (exit 127) at runtime.

**Post-build verification (always run this after building):**
```bash
# Check the conda env directory exists and has the expected tool
apptainer exec /path/to/env.sif bash -c 'ls /opt/conda/envs/ && which Rscript'
# If envs/ is empty or Rscript not found, the build failed silently
```

**Checking the build log for conda errors:**
Look for `EnvironmentSpecPluginNotDetected` or `PackagesNotFoundError` in the
apptainer build output. These indicate conda env create failed but the SIF was
still produced.

**Runtime symptom**: Snakemake job fails with `exit status 127` and the per-rule
log shows `<command>: command not found`. This means the tool is missing from
the SIF, not a PATH issue.

## Testing if a YAML can create a conda env (pitfall)

`conda env create -f <yaml> --dry-run` is **not reliable** for complex envs
with many dependencies. It can hang for 5+ minutes on the conda solver,
making it impractical as a quick sanity check.

Alternatives:
1. Build the SIF directly (`apptainer build` or `EnvUtil.py apptainer all`) --
   the build itself is the real test. If conda env create fails inside the
   SIF build, you see the error in the apptainer log.
2. Create a throwaway conda env: `conda env create -f <yaml> -n test_env`
   (no --dry-run). Slower but definitive.
3. Use `conda env create -f <yaml> --dry-run --json` with a long timeout
   (600s+) only if you specifically need a dry-run.

The user's workflow: update YAML -> rebuild SIF -> verify with
`apptainer exec` -> commit and push.
