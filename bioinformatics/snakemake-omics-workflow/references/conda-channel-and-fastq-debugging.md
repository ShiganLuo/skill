# Conda channel resolution and FASTQ debugging notes

Session findings:

- Snakemake invokes conda as `conda env create --file <yaml> --prefix <env>`.
- conda merges `environment.yml` channels with global `context.channels` from `~/.condarc` unless the yaml includes `nodefaults`.
- `channel_priority: strict` should be set in conda config, and can be verified with `conda config --show-sources` plus `conda config --show channel_priority channels solver pkgs_dirs`.
- For reproducible Snakemake envs, prefer minimal yaml channels plus `nodefaults` in the yaml when you want to suppress global defaults.

RNAseq failure mode seen in this session:

- STAR reported `quality string length is not equal to sequence length`, but the real issue was cutadapt emitting empty reads.
- In the trimmed FASTQ, some records had empty sequence and quality fields; count these before blaming STAR.
- Quick probe pattern:
  - iterate FASTQ records 4 lines at a time
  - flag records where `len(seq) == 0` or `len(seq) != len(qual)`
- Fix is usually to set a positive `minimum_length` in cutadapt or filter zero-length reads before alignment.

Bowtie2 indexing failure mode seen in this session:

- `bowtie2_index` completed the tool run and wrote the temporary index files, but the rule still failed because the `run:` block had an unconditional `raise e` outside the `except` block.
- Keep exception re-raise inside `except`; never leave a bare `raise e` at the end of a `run:` block.
- Also avoid `logger.error(f.write(...))`; `f.write()` returns an integer, not a log message.
