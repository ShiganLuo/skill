# mimseq Module Splitting — Lessons Learned

## Overview

mimseq is a monolithic tRNA-seq analysis tool that handles everything from alignment to
differential expression. We split it into 6 independent Snakemake sub-modules.

## Architecture

```
modules/mimseq/
├── mimseq.smk              # Orchestrator (includes sub-modules)
├── mimseq.yaml             # Shared conda env
├── bin/
│   ├── serialize.py        # Pickle/JSON state serialization
│   ├── utils.py            # extract_condition() for metadata
│   ├── tRNAtools/run.py    # tRNA parsing + SNP index + GSNAP indices
│   ├── align/run.py        # GSNAP alignment
│   ├── clusters/run.py     # Cluster splitting + deconvolution
│   ├── mods/run.py         # Modification quantification
│   ├── coverage/run.py     # Coverage calculation + plots
│   └── deseq/run.py        # DESeq2 differential expression
├── tRNAtools/tRNAtools.smk
├── align/align.smk
├── clusters/clusters.smk
├── mods/mods.smk
├── coverage/coverage.smk
├── deseq/deseq.smk
└── mimseq/                 # Original source code (copied from conda env)
```

## Dependency Chain

```
prepare_sample_data → tRNAtools → align → clusters → mods → coverage → deseq → result
```

## Key Pitfalls

### 1. `conda:` + `run:` incompatibility

Snakemake does NOT allow `conda:` directive with `run:` blocks. Must remove `conda:`
and use full path to Python executable in the conda environment:

```python
# WRONG
rule my_rule:
    conda: "env.yaml"
    run:
        shell("python script.py")

# RIGHT — use full path
rule my_rule:
    run:
        shell("/path/to/env/bin/python script.py")
```

### 2. mimseq argparse bugs

**`--umi-length` shows `(default: None)` but is actually required:**
```bash
# This fails:
fumi_tools copy_umi -i in.fq.gz -o out.fq.gz
# → error: the following arguments are required: --umi-length

# This also fails:
fumi_tools copy_umi -i in.fq.gz -o out.fq.gz --umi-length None
# → error: invalid int value: 'None'
```

**`--control-condition` only accepts ONE value:**
```bash
mimseq --control-condition GV  # ✓ One control, compares all others against it
# Cannot specify multiple comparisons; run mimseq multiple times if needed
```

### 3. usearch version compatibility

mimseq requires usearch v10 (not v12). v12 removed `-sortbysize` command:

```bash
# Install correct version:
conda install -c bioconda usearch=10.0.259
```

### 4. gsnap version compatibility

gsnap genome indices are version-specific. Old gsnap (2017-01-14) cannot read indices
built by newer versions. Also, newer gsnap removed options:
- `--ignore-trim-in-filtering` (removed)
- `--md-lowercase-snp` (removed)

**Fix:** Update gsnap to 2024+ and remove unsupported options from tRNAmap.py:
```bash
sed -i 's/"--ignore-trim-in-filtering", "1",//' tRNAmap.py
sed -i 's/"--md-lowercase-snp",//' tRNAmap.py
```

### 5. mimseq `out_dir` requires trailing `/`

mimseq concatenates paths like `out_dir + "filename"`. Without trailing `/`, paths
become `outdirfilename` instead of `outdir/filename`:

```python
# WRONG
cmd = ["--out", outdir]

# RIGHT
cmd = ["--out", outdir + "/"]
```

### 6. Import pattern for mimseq package

When importing from mimseq package in wrapper scripts, use module-level imports:

```python
# WRONG — triggers relative import error
from mimseq.tRNAtools import modsToSNPIndex

# RIGHT — import as module
MIMSEQ_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if MIMSEQ_PARENT not in sys.path:
    sys.path.insert(0, MIMSEQ_PARENT)
import mimseq.tRNAtools as tRNAtools_module

# Then use:
tRNAtools_module.modsToSNPIndex(...)
```

### 7. Built-in species references

When using mimseq with built-in species (e.g., `Mmus`), the wrapper must set
reference paths explicitly. mimseq does this internally in `main()`, but our
wrapper calls `modsToSNPIndex()` directly:

```python
species_refs = {
    "Mmus": ("mm39-eColitK/mm39-tRNAs-all.fa", "mm39-eColitK/mm39-tRNAs-detailed.out", ...),
    "Hsap": ("hg38-eColitK/hg38-tRNAs-all.fa", "hg38-eColitK/hg38-tRNAs-detailed.out", ...),
    # ... etc
}
if species in species_refs:
    trnas_ref, trnaout_ref, mito_ref = species_refs[species]
    trnas = os.path.join(mimseq_data_dir, trnas_ref)
    trnaout = os.path.join(mimseq_data_dir, trnaout_ref)
```

### 8. PATH for subprocess calls

When Python scripts call external tools (gsnap, usearch, samtools) via subprocess,
the conda environment's bin/ must be in PATH. Add to generated shell scripts:

```bash
#!/bin/bash
export PATH=/path/to/conda/env/bin:$PATH
python wrapper.py ...
```

## mimseq.yaml Dependencies

```yaml
dependencies:
  - python>=3.7
  - mimseq
  - biopython
  - pandas
  - numpy
  - pysam
  - pybedtools
  - bedtools
  - samtools
  - gmap>=2024.11.20
  - gsnap>=2024.11.20
  - usearch=10.0.259  # NOT v12!
  - blast
  - infernal
  - r-base
  - bioconductor-deseq2
```

## State Serialization

Create `bin/serialize.py` with:
- `save_pickle(obj, path)` / `load_pickle(path)` — for Python objects
- `save_json(obj, path)` / `load_json(path)` — for metadata
- `save_tRNA_state(outdir, ...)` / `load_tRNA_state(outdir)` — domain-specific
- `save_align_state(outdir, ...)` / `load_align_state(outdir)` — domain-specific

Each module saves state to `{outdir}/state/` directory.
