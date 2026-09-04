# Conda triage and FASTQ runtime checks

## Conda channel resolution
- Snakemake calls `conda env create --file <yaml> --prefix <env>`.
- `environment.yml` channels are not isolated from global conda config.
- Conda merges YAML channels with `context.channels` unless `nodefaults` is present in the YAML.
- For reproducibility and less solver churn:
  - set `channel_priority: strict`
  - keep user `.condarc` minimal
  - prefer `conda-forge`, `bioconda`, `defaults` only
  - add `nodefaults` to env YAMLs when you want to suppress default/global channels

## Log triage workflow
1. Read the Snakemake execution log under `<workdir>/.snakemake/log/`.
2. Confirm whether failure is during env creation or during rule execution.
3. For rule failures, open the rule-local log under `logdir/...`.
4. Match log timestamps to the current process start time; old runs are noise.

## FASTQ corruption check for STAR
If STAR reports:
- `quality string length is not equal to sequence length`

Then verify the FASTQ directly, not the conda env:
- read gzip records in groups of 4
- compare sequence length vs quality length for every record
- check the offending file(s) from the rule input

A clean FASTQ will end with an even number of 4-line records and no length mismatches.
