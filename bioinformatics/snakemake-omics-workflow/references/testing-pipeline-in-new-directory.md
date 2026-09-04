# Testing pipeline changes in a separate output directory

When modifying pipeline code, test in a new directory to avoid clobbering existing results.

## Setup checklist

```bash
# 1. Create test directory and copy config
mkdir -p test_output
cp original/raw.json test_output/

# 2. Update config paths
python3 -c "
import json
with open('test_output/raw.json') as f:
    d = json.load(f)
d['outdir'] = '/abs/path/to/test_output'
d['outfiles'] = ['/abs/path/to/test_output/mimseq/mimseq.done']
d['logdir'] = '/abs/path/to/test_output/log'
with open('test_output/raw.json', 'w') as f:
    json.dump(d, f, indent=2)
"

# 3. Symlink shared data (FASTQ, references)
ln -s /abs/path/to/original/fastq test_output/fastq

# 4. Clear Snakemake cache
rm -rf test_output/.snakemake
```

## Common pitfalls

### `outfiles` config mismatch
If `outfiles` still points to the original directory, Snakemake checks the original
outputs and reports "Nothing to be done". Must update `outfiles`, `outdir`, and `logdir`.

### `.snakemake` stale metadata
Snakemake caches rule metadata in `.snakemake/`. Stale metadata from a previous directory
causes incorrect "Nothing to be done" or unnecessary re-runs. Always clear before first
run in a new directory.

### `conda:` archive per-project
Conda environments are cached globally (by `--conda-prefix`), but `.snakemake/conda-archive/`
is per-project. First run in a new directory re-registers environments (fast, no actual install).
