# mimseq per-sample output directory pattern

## Problem
mimseq writes all per-sample files flat in `out_dir/`:
- `{sample}.single.fq.gz.uniq.bam` + `.bai`
- `{sample}.single.fq.gz.mult.bam`
- `{sample}.single.fq.gz.nomapping.bam`
- `{sample}.single.fq.gz.transloc`
- `{sample}.single.fq.gz.uniq.bam_predictedModstemp.csv`

With 58+ samples, this creates 350+ files in one directory.

## Solution: sample_dir parameter in mapReads

### 1. Add sample_dir to mapReads (tRNAmap.py)

```python
def mapReads(fq, ..., out_dir, snp_tolerance, keep_temp, mismatches, remap, sample_dir=None):
    if sample_dir is None:
        sample_dir = out_dir
    # Use sample_dir for BAM output, out_dir for shared logs/stats
    # gsnap --split-output: sample_dir + output_prefix
    # align.log, mapping_stats.txt: still in out_dir
```

### 2. Create per-sample dir in mainAlign (tRNAmap.py)

```python
sample_name = fq.split("/")[-1].split(".single.fq.gz")[0]
sample_dir = os.path.join(out_dir, "samples", sample_name) + "/"
os.makedirs(sample_dir, exist_ok=True)
unique_bam, librarySize, alignstats = mapReads(..., sample_dir=sample_dir)
```

### 3. _coverage.txt follows BAM directory (mmQuant.py)

```python
# OLD: out_dir + inputs.split("/")[-1] + "_coverage.txt"
# NEW: os.path.dirname(inputs) + "/" + inputs.split("/")[-1] + "_coverage.txt"
cov_table_melt.to_csv(os.path.dirname(inputs) + "/" + inputs.split("/")[-1] + "_coverage.txt", ...)
```

### 4. getCoverage reads from BAM directory (getCoverage.py)

```python
# OLD: out_dir + bam.split("/")[-1] + "_coverage.txt"
# NEW: os.path.dirname(bam) + "/" + bam.split("/")[-1] + "_coverage.txt"
coverage = pd.read_csv(os.path.dirname(bam) + "/" + bam.split("/")[-1] + "_coverage.txt", ...)
os.remove(os.path.dirname(bam) + "/" + bam.split("/")[-1] + "_coverage.txt")
```

### 5. _predictedModstemp.csv needs NO change
It uses `inputs + "_predictedModstemp.csv"` which is relative to BAM path — automatically in sample dir.

## Result structure
```
mimseq/
├── samples/
│   ├── 4C-1/
│   │   ├── 4C-1.single.fq.gz.uniq.bam
│   │   ├── 4C-1.single.fq.gz.uniq.bam.bai
│   │   ├── 4C-1.single.fq.gz.mult.bam
│   │   ├── 4C-1.single.fq.gz.nomapping.bam
│   │   ├── 4C-1.single.fq.gz.transloc
│   │   └── 4C-1.single.fq.gz.uniq.bam_predictedModstemp.csv
│   └── ...
├── state/           # shared pickle state
├── coverage_byaa.txt
├── coverage_bygene.txt
├── mapping_stats.txt
├── *.done
└── *.log
```

## Pitfall: shared files stay in out_dir
`align.log`, `mapping_stats.txt`, `sample_data_cov.tsv` are shared across samples — keep them in `out_dir`, not in sample dirs.
