# DIPseq/ChIP-seq (PeakCalling) Porting Case

## Overview
DIP-seq / ChIP-seq workflow: trimming → bowtie2 align → MACS3 peak calling.
Renamed from DIPseq to PeakCalling for generality (covers both ChIP-seq and DIP-seq).

## Key Files Created

### Module: `modules/macs3/`
```
macs3.smk   # macs3_callpeak + macs3_result rules
macs3.json  # config template with IP/Input support
macs3.yaml  # conda env (macs3>=3.0.0)
```

### Subworkflow: `subworkflow/DIPseq.smk`
```
Steps: cutadapt → bowtie2_index → bowtie2_align → macs3_callpeak
Key config: sample_ip_input_map (IP→Input control mapping)
```

### Config: `config/DIPseq.json`
```
Special fields: ip_samples, input_samples, sample_ip_input_map, genomes
```

### run.py: `runDIPseq()` function
```
Parses samples_info_dict for design=="ip" or design=="input"
Builds sample_ip_input_map automatically
Generates outfiles for trimming, alignment, and peak calling
```

## Design Decisions

1. **IP→Input Mapping**: Uses first available Input sample as control for all IPs. Can be extended with per-sample matching via metadata.

2. **Genome Support**: Hardcoded "mm" for mouse in outfiles. Extend with `genomes` config field for multi-genome support.

3. **Peak Calling**: MACS3 narrowPeak output. For broad peaks (H3K27me3), add `--broad` flag to params.

## Pitfalls

1. **No Input samples**: MACS3 runs without `-c` control. Warn user in runDIPseq().

2. **Single-end data**: Current outfiles assume PE (`_1.fq.gz`, `_2.fq.gz`). For SE, adjust cutadapt outputs in runDIPseq().

3. **Multi-genome**: If using multiple genomes (mm + hg38), need to duplicate outfiles for each genome in runDIPseq().
