# mimseq Module Notes

## Tool Overview
mimseq is a monolithic tRNA-seq analysis tool that handles:
- tRNA sequence parsing and clustering
- GSNAP alignment
- Modification quantification
- CCA analysis
- DESeq2 differential expression

## Critical Dependencies

### usearch Version
- **Required**: usearch v10.x (supports `-sortbysize` command)
- **Broken**: usearch v12.x (removed `-sortbysize`)
- **Install**: `conda install -c bioconda usearch=10.0.259`

### Other Dependencies
- gmap/gsnap (alignment)
- samtools (BAM processing)
- bedtools (coverage)
- R + DESeq2 (differential expression)

## Path Handling

### Trailing `/` Required
mimseq requires output directory paths to end with `/`. Without it, path concatenation produces incorrect paths:

```python
# BROKEN: /output/mimseqMmus_tRNAgenome (missing /)
out_dir = "/output/mimseq"
genome_dir = out_dir + species + "_tRNAgenome"

# FIXED: /output/mimseq/Mmus_tRNAgenome
out_dir = "/output/mimseq/"
genome_dir = out_dir + species + "_tRNAgenome"
```

**Fix in Snakemake**: Add trailing `/` to outdir parameter:
```python
cmd = ["python", script, "--out", outdir + "/", ...]
```

**Fix in Python wrapper**: Ensure trailing `/`:
```python
if not out.endswith("/"):
    out = out + "/"
```

## Species-Specific References

When using built-in species (Mmus, Hsap, etc.), mimseq automatically sets reference paths. The wrapper script must replicate this logic:

```python
species_refs = {
    "Mmus": ("mm39-eColitK/mm39-tRNAs-all.fa", "mm39-eColitK/mm39-tRNAs-detailed.out"),
    "Hsap": ("hg38-eColitK/hg38-tRNAs-all.fa", "hg38-eColitK/hg38-tRNAs-detailed.out"),
    # ... etc
}
if species in species_refs:
    trnas_ref, trnaout_ref = species_refs[species]
    trnas = os.path.join(mimseq_data_dir, trnas_ref)
    trnaout = os.path.join(mimseq_data_dir, trnaout_ref)
```

## Splitting into Sub-Modules

### Architecture
```
modules/mimseq/
├── mimseq.smk              # Main orchestrator
├── mimseq.yaml             # Shared conda env
├── bin/
│   ├── serialize.py        # Pickle serialization utilities
│   ├── utils.py            # Original utils
│   ├── tRNAtools/run.py    # Wrapper for tRNA parsing
│   ├── align/run.py        # Wrapper for alignment
│   ├── clusters/run.py     # Wrapper for cluster splitting
│   ├── mods/run.py         # Wrapper for modification quantification
│   ├── coverage/run.py     # Wrapper for coverage calculation
│   └── deseq/run.py        # Wrapper for DESeq2
├── tRNAtools/tRNAtools.smk
├── align/align.smk
├── clusters/clusters.smk
├── mods/mods.smk
├── coverage/coverage.smk
└── deseq/deseq.smk
```

### State Serialization
Use pickle files to pass intermediate state between modules:

```python
# serialize.py
def save_tRNA_state(outdir, tRNA_dict, cluster_dict, ...):
    state_dir = os.path.join(outdir, "state")
    os.makedirs(state_dir, exist_ok=True)
    save_pickle(tRNA_dict, os.path.join(state_dir, "tRNA_dict.pkl"))
    # ... save other state

def load_tRNA_state(outdir):
    state_dir = os.path.join(outdir, "state")
    return {
        "tRNA_dict": load_pickle(os.path.join(state_dir, "tRNA_dict.pkl")),
        # ... load other state
    }
```

### Dependency Chain
```
prepare_sample_data → tRNAtools → align → clusters → mods → coverage → deseq → result
```

Each module produces a `.done` sentinel file:
```python
rule mimseq_align:
    input:
        sample_data = outdir + "/sample_data.tsv",
        state_dir = outdir + "/state",
    output:
        align_done = touch(outdir + "/align.done"),
```

### Importing Rules in Subworkflow
When using `module` + `use rule`, ALL intermediate rules must be imported:

```python
# tRNAseq.smk
module mimseq:
    snakefile: "../modules/mimseq/mimseq.smk"
    config: mimseq_config

use rule mimseq_all from mimseq as tRNAseq_mimseq_run
use rule mimseq_result from mimseq as tRNAseq_mimseq_result
use rule mimseq_tRNAtools from mimseq as tRNAseq_mimseq_tRNAtools
use rule mimseq_align from mimseq as tRNAseq_mimseq_align
# ... import ALL intermediate rules
```

## Common Pitfalls

### conda: + run: Conflict
Snakemake doesn't allow `conda:` directive with `run:` blocks. Options:
1. Remove `conda:` and use full path to Python executable
2. Use `shell:` instead of `run:` (loses flexibility)

### Missing `usearch` Command
If `usearch -sortbysize` fails with "Unknown command-line option", check version:
```bash
usearch --version  # Should be v10.x, not v12.x
```

### Empty Genome Directory
If `snpindex` fails with "Unable to find genome", check:
1. Output directory has trailing `/`
2. `gmap_build` completed successfully
3. Genome directory contains actual index files

### Empty anticodon in mmQuant.py
`clusterAnticodon()` returns `[]` for isodecoders not found in the stk alignment file.
`min(anticodon)` then raises `ValueError: min() arg is an empty sequence`.
Fix: guard with `anticodon and pos-1 == min(anticodon)` in both the inosine check (line 90)
and the elif branch (line 93) of `unknownMods()`.

## Testing

### Dry-Run
```bash
snakemake -s subworkflow/tRNAseq.smk \
  --configfile raw.json \
  --cores 8 \
  --use-conda \
  --dry-run
```

### Single Module Test
Test individual modules by running their wrapper scripts directly:
```bash
python bin/tRNAtools/run.py --species Mmus --out /tmp/test/ --name test
```
