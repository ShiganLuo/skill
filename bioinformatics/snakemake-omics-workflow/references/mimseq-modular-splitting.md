# Splitting mimseq into modular Snakemake workflow

## Background

mimseq (mim-tRNAseq) is a monolithic tRNA-seq analysis tool that does everything in one
command: tRNA parsing, alignment, clustering, modification quantification, CCA analysis,
DESeq2, and plotting. This makes it hard to debug, rerun individual steps, or integrate
into Snakemake workflows.

## Solution: Split into sub-modules

### Directory structure

```
modules/mimseq/
├── mimseq.smk           # Main orchestrator with include: directives
├── mimseq.yaml          # Shared conda env
├── mimseq/              # Original source code (copied from conda env)
├── bin/
│   ├── serialize.py     # State serialization (pickle/JSON)
│   ├── utils.py         # Shared utilities (extract_condition)
│   ├── tRNAtools/run.py # Wrapper for tRNA parsing + SNP index
│   ├── align/run.py     # Wrapper for GSNAP alignment
│   ├── clusters/run.py  # Wrapper for cluster splitting
│   ├── mods/run.py      # Wrapper for modification quantification
│   ├── coverage/run.py  # Wrapper for coverage + plotting
│   └── deseq/run.py     # Wrapper for DESeq2
├── tRNAtools/tRNAtools.smk
├── align/align.smk
├── clusters/clusters.smk
├── mods/mods.smk
├── coverage/coverage.smk
└── deseq/deseq.smk
```

### State passing via pickle

Each module saves intermediate state to `outdir/state/` as pickle files:

```python
# bin/serialize.py
def save_pickle(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

def save_tRNA_state(outdir, tRNA_dict, cluster_dict, ...):
    state_dir = os.path.join(outdir, "state")
    save_pickle(tRNA_dict, os.path.join(state_dir, "tRNA_dict.pkl"))
    # ... save all intermediate objects

def load_tRNA_state(outdir):
    state_dir = os.path.join(outdir, "state")
    return {
        "tRNA_dict": load_pickle(os.path.join(state_dir, "tRNA_dict.pkl")),
        # ... load all intermediate objects
    }
```

### Dependency chain with .done sentinel files

```
prepare_sample_data → sample_data.tsv
tRNAtools → state_dir/
align → align.done (depends on sample_data.tsv + state_dir)
clusters → clusters.done (depends on align.done)
mods → mods.done (depends on clusters.done)
coverage → coverage.done (depends on mods.done)
deseq → deseq.done (depends on coverage.done)
result → mimseq.done (depends on deseq.done)
```

### Main orchestrator (mimseq.smk)

```python
rule mimseq_prepare_sample_data:
    input: meta = meta
    output: sample_data = outdir + "/sample_data.tsv"
    run:
        # ... create sample_data.tsv from meta

include: "tRNAtools/tRNAtools.smk"
include: "align/align.smk"
include: "clusters/clusters.smk"
include: "mods/mods.smk"
include: "coverage/coverage.smk"
include: "deseq/deseq.smk"

rule mimseq_all:
    input: deseq_done = outdir + "/deseq.done"

rule mimseq_result:
    input: deseq_done = outdir + "/deseq.done"
    output: touch(outdir + "/mimseq.done")
```

### Subworkflow integration

```python
# subworkflow/tRNAseq.smk
module mimseq:
    snakefile: "../modules/mimseq/mimseq.smk"
    config: mimseq_config

# MUST import ALL intermediate rules, not just result
use rule mimseq_all from mimseq as tRNAseq_mimseq_run
use rule mimseq_result from mimseq as tRNAseq_mimseq_result
use rule mimseq_prepare_sample_data from mimseq as tRNAseq_mimseq_prepare_sample_data
use rule mimseq_tRNAtools from mimseq as tRNAseq_mimseq_tRNAtools
use rule mimseq_align from mimseq as tRNAseq_mimseq_align
use rule mimseq_clusters from mimseq as tRNAseq_mimseq_clusters
use rule mimseq_mods from mimseq as tRNAseq_mimseq_mods
use rule mimseq_coverage from mimseq as tRNAseq_mimseq_coverage
use rule mimseq_deseq from mimseq as tRNAseq_mimseq_deseq
```

## Critical: bare `python` in generated scripts

All `.smk` files for mimseq sub-modules must use the FULL conda python path in their
generated bash scripts, NOT bare `"python"`. Also must include `export PATH` for
samtools, bedtools, gsnap, usearch. See `references/generate-shell-scripts-from-run-blocks.md`.

## mimseq-specific quirks

### Argparse bug: `-o` always required

mimseq's argparse has bug where `-o/--trnaout` is always required even with `-s`:
```python
# Bug in mimseq source
required = (not '--species' or '-s' in sys.argv) or ('-t' in sys.argv)
# not '--species' is always False (string truthy), so required always True
```

**Fix**: Provide built-in tRNA.out path when using `-s`:
```python
species_trnaout_map = {
    "Hsap": "hg38-eColitK/hg38-tRNAs-detailed.out",
    "Mmus": "mm39-eColitK/mm39-tRNAs-detailed.out",
    # ...
}
cmd += ["-o", os.path.join(mimseq_data_dir, species_trnaout_map[species])]
```

### Species reference paths

When species is specified, mimseq internally sets reference paths. Wrapper must replicate:
```python
species_refs = {
    "Mmus": ("mm39-eColitK/mm39-tRNAs-all.fa", "mm39-eColitK/mm39-tRNAs-detailed.out"),
    "Hsap": ("hg38-eColitK/hg38-tRNAs-all.fa", "hg38-eColitK/hg38-tRNAs-detailed.out"),
}
mimseq_data_dir = os.path.join(env_path, "lib/python3.7/site-packages/mimseq/data")
trnas = os.path.join(mimseq_data_dir, species_refs[species][0])
```

### usearch version requirement

mimseq requires usearch v10 (not v12) for `-sortbysize` command:
```bash
conda install --prefix /path/to/env -c bioconda usearch=10.0.259
```

### --out-dir cannot be existing directory

mimseq help says `--out-dir` cannot be existing directory, but testing shows this is
not enforced. Safe to use existing directory.
