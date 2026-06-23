# msisensor-pro v1.3.0 Source Code Analysis

Source: https://github.com/xjtu-omics/msisensor-pro
Author: Peng Jia (Xi'an Jiaotong University, Kai Ye lab)

## Architecture

4 subcommands:
- `scan` → HomoAndMicrosateScan() — enumerate microsatellite loci in reference
- `msi` → HomoAndMicrosateDisMsi() — paired tumor-normal detection
- `baseline` → TrainMsiP() — build per-locus thresholds from normal samples
- `pro` → HomoAndMicrosateDisMsiPro() — tumor-only detection (core innovation)

## Key Data Structures

### HomoSite
- chr, location, typeLen (1=homopolymer, 2-6=microsatellite)
- homoType: 2-bit-per-base encoding of repeat unit
- length: repeat count
- normalDis, tumorDis: unsigned short*[100] — length distribution histograms
- hunterValueU (pro_p), hunterValueV (pro_q): Hunter method ratios
- thres: per-locus threshold from baseline

### Param defaults
- MininalHomoSize=8, MaxHomoSize=50
- MaxMicrosate=6, Repeats=5
- s_dispots=100 (distribution bins)
- covCutoff=15 (minimum depth)
- fdrThreshold=0.05 (paired mode)
- hunterThreshold=0.1 (tumor-only hard cutoff)
- sampleNum=10 (minimum support for baseline)

## Paired Mode (msi command)

1. Per locus: compare normal vs tumor distribution
2. Chi-squared test: X² = Σ(Obs-Exp)²/Exp
3. BH-FDR correction across all loci
4. MSI score = unstable loci / valid loci × 100%
5. Typically ≥10% → MSI-H

## Tumor-Only Mode (pro command) — Hunter Method

### Hunterp() function
```
normalValue = Σ(distribution[i] × (i+1)) for i < reflen
            + Σ(distribution[i] × reflen) for i >= reflen
delValue = Σ(distribution[i] × (reflen - (i+1))) for i < reflen
insertValue = Σ(distribution[i] × (i+1-reflen)) for i >= reflen

pro_p = delValue / (normalValue + delValue + insertValue)  # deletion fraction
pro_q = insertValue / (normalValue + delValue + insertValue)  # insertion fraction
```

### Why pro_p only (not pro_q)?
- MSI more commonly manifests as deletions (especially in homopolymers)
- Deletion signal more reliable (insertions can come from sequencing artifacts)
- Code uses hunterValueU (pro_p) for threshold comparison

### Threshold sources
- Hard cutoff: `pro_p > hunterThreshold` (default 0.1, set via -i)
- Baseline: `pro_p > mean + 3*stdev` (per-locus, from normal samples)

## Baseline Construction

1. Read config file with paths to normal sample *_all files
2. For each normal sample, extract pro_p per locus
3. Compute mean + 3*stdev across samples
4. Filter: support < sampleNum (default 10) → mark as LowSupportSamples
5. Output: same format as scan output, but threshold column has actual values

## Distribution Computation

1. Divide loci into windows (default 500kb)
2. Per window: fetch reads from BAM (sam_fetch)
3. Per read: compute effective length at each locus (considering indels)
4. Distribution point = effective_length - reference_length (offset)
5. Histogram: bin[reflen-1] = normal length, <reflen-1 = deletion, >reflen-1 = insertion

## Output Files

### msi/pro command
- `<prefix>`: MSI score summary
- `<prefix>_unstable`: unstable loci list
- `<prefix>_all`: all candidate loci with FDR/pro_p
- `<prefix>_dis`: per-locus length distributions

### baseline command
- Same format as scan output, threshold column = mean + 3*sigma

## vs Original msisensor

| Feature | msisensor | msisensor-pro |
|---------|-----------|---------------|
| Paired sample | Required | Optional |
| Scoring | Chi-squared | Chi-squared (paired) / Hunter (tumor-only) |
| Baseline | No | Yes (mean+3σ per locus) |
| Input | BAM only | BAM + CRAM |
| Threshold | Fixed FDR | Hard or baseline soft |
