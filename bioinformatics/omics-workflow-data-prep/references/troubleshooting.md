# Troubleshooting Omics Snakemake Workflows

## Symptom: `use rule` imports silently fail (MissingInputException for expected outputs)

**Root cause**: Module `.smk` files with `conda:` directives fail during snakemake startup when conda itself is broken. The module loads partially (Python code executes, configs are logged) but the snakemake rule registration fails silently.

**Diagnosis**: Run with `--debug-dag` and grep for your expected rule names. If only some rules appear, the module containing the missing rules failed to import.

**Fix options**:
1. Fix conda (see below)
2. Comment out `conda:` directives in the `.smk` module and pass full binary path via config's `Procedure` section

## Symptom: `TypeError: expected str, bytes or os.PathLike object, not NoneType` from conda activate

**Root cause**: `CONDA_DEFAULT_ENV=base` is set in the shell but `CONDA_PREFIX` is empty. The `anaconda_anon_usage` plugin (v0.7.0) intercepts `conda activate` and crashes when trying to deactivate the old (nonexistent) prefix.

**Fix**: `export CONDA_PREFIX=/home/luosg/miniconda3` before running snakemake, or:
```bash
pip uninstall anaconda-anon-usage
```
After uninstall, conda shows a harmless warning `Error while loading conda entry point: anaconda-anon-usage-plugin` but works correctly.

## Symptom: `ImportError: Failed to import common.LogUtil.setup_logger`

**Root cause**: `ROOT_DIR` in config points to wrong directory. The `common.smk` module does `sys.path.insert(0, os.path.join(ROOT_DIR, "src"))`.

**Fix**: Set `ROOT_DIR` to the `workflow/Omics` directory (containing `src/`), NOT the project root.

## Symptom: MissingInputException for cutadapt input files

**Root cause**: MetaUtil creates flat symlinks (`raw_fastq/{sample}_1.fq.gz`) but cutadapt expects subdirectory structure (`raw_fastq/{sample}/{sample}_1.fq.gz`).

**When using `run.py`**: This is handled automatically by the framework.

**When running snakemake directly**: Edit `raw.json` to set `indir` to the original data directory (which has the correct `{sample}/{sample}_1.fq.gz` structure).

## Symptom: `TypeError: sequence item N: expected str instance, int found` in rule `run:` block

**Root cause**: Snakemake config values (e.g., `bw=200`, `seed=2346`) are Python `int`. Building a command list with these and calling `" ".join(cmd)` fails because `str.join()` requires all elements to be strings.

**Fix**: Wrap all params: `str(params.bw)`, `str(params.seed)`, etc. Apply to any param that comes from JSON config or is hardcoded as a number.

## Symptom: `if "key" in input:` always False despite `unpack()` returning the key

**Root cause**: Snakemake's `Namedlist.__contains__` checks if the string appears as a **value** in the list (i.e., a file path), not as a **named key**. So `"bam_control" in input` checks if any input file path equals the string `"bam_control"`, which is always False.

**Context**: This happens when using `unpack(get_input_fn)` where the function returns `{"bam_treatment": path, "bam_control": path}`. Snakemake correctly resolves both files for the DAG, but `in` doesn't work for key checking.

**Fix**: Use `hasattr(input, "bam_control") and input.bam_control` instead of `"bam_control" in input`.
