# Snakemake Module Implementation

## Exome Data Limitations

**Exome sequencing data is NOT suitable for telomere length estimation.** Exome capture
probes target coding regions, not repetitive telomeric/centromeric sequences. Results from
Exome data will show:

| Method | Expected Result | Issue |
|--------|-----------------|-------|
| read_density | Very low telomere fraction (~0.8%) | Probes don't capture telomeric regions |
| assembly_scan | Few contigs with telomere signal | Assembly quality poor for repetitive regions |
| tidk | No telomeric repeats found | Insufficient coverage |
| telogator2 | Only 3 alleles detected | Very few reads with telomeric signal |

**For accurate telomere measurement, use:**
- Whole-genome sequencing (WGS) with sufficient coverage
- PacBio HiFi or ONT ultra-long reads
- Dedicated telomere-length assays (TRF, Q-FISH, TeSLA)

## Module Structure

The telomere module in the Omics pipeline implements all approaches in a single module:

```
modules/telomere/
├── telomere.smk          # 4 rules: telogator2 + assembly_scan + read_density + tidk
├── telomere.yaml         # conda: telogator2, tidk, pysam, numpy
├── telomere.json         # config template
└── bin/
    ├── scan_assembly_telomere.py   # Approach A
    └── read_density_telomere.py    # Approach B
```

## Output Path Convention

Each approach outputs to a subdirectory under `{sample_id}/`:

```
repeat/telomere/{sample_id}/
├── telogator2/           # Approach 0: per-chromosome-arm
│   └── tlens_by_allele.tsv
├── assembly_scan/        # Approach A: assembly contig ends
│   └── {sid}_assembly_telomere_stats.txt
├── read_density/         # Approach B: read-level k-mer density
│   └── {sid}_read_telomere_stats.txt
└── tidk/                 # Approach C: tidk community tool
    └── {sid}_tidk_telomeres.tsv
```

## Config Parameters

```json
{
    "assembly_dir": "{outdir}/repeat/centromere",
    "Params": {
        "telogator2": {
            "species": "human",
            "assembly_scan_length": 50000,
            "n_chrom_arms": 40
        }
    }
}
```

## Dependency Chain

```
centromere assembly (hifiasm)
    ├── assembly_telomere_scan (Approach A)
    └── tidk_scan (Approach C)

HiFi BAM (gatk_prepare)
    ├── telogator2_run
    └── read_density_telomere (Approach B)
```

## run.py Integration

The `runPacVar()` function must include all output paths in `outfiles`:

```python
# Telogator2
outfiles.append(f"{outdir}/repeat/telomere/{sid}/telogator2/tlens_by_allele.tsv")
# Approach A
outfiles.append(f"{outdir}/repeat/telomere/{sid}/assembly_scan/{sid}_assembly_telomere_stats.txt")
# Approach B
outfiles.append(f"{outdir}/repeat/telomere/{sid}/read_density/{sid}_read_telomere_stats.txt")
# Approach C
outfiles.append(f"{outdir}/repeat/telomere/{sid}/tidk/{sid}_tidk_telomeres.tsv")
```
