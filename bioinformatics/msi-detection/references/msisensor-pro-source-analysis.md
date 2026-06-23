# msisensor-pro Source Code Analysis

Based on v1.3.0 source at `msisensor-pro/cpp/`.

## Architecture

4 subcommands:
- `scan` → `HomoAndMicrosateScan()` — scan reference genome
- `msi` → `HomoAndMicrosateDisMsi()` — paired tumor-normal detection
- `baseline` → `TrainMsiP()` — build baseline from normal samples
- `pro` → `HomoAndMicrosateDisMsiPro()` — tumor-only detection

## Key Data Structures

### HomoSite
Core struct for a microsatellite locus:
- chr, location, typeLen (1=homopolymer, 2-6=microsatellite)
- homoType: binary-encoded repeat unit (2bit/base)
- length: repeat count
- frontKmer, endKmer: flanking sequences
- normalDis, tumorDis: `unsigned short*[]` — length distribution [sample][0-99]
- pValue: chi-squared p-value
- hunterValueU, hunterValueV: deletion/insertion ratios
- thres: per-locus threshold from baseline

### Param
Global parameters:
- MininalHomoSize=8, MaxHomoSize=50
- MaxMicrosate=6, Repeats=5
- s_dispots=100 (distribution bins)
- covCutoff=15 (coverage threshold)
- fdrThreshold=0.05 (paired mode)
- hunterThreshold=0.1 (tumor-only mode)
- sampleNum=10 (min baseline support)

## MSI Scoring

### Paired Mode (msi)
Chi-squared test + BH-FDR:
1. Compare normal vs tumor distribution per locus
2. Chi-squared test → p-value
3. BH-FDR correction → FDR<=0.05 = unstable
4. MSI% = unstable_loci / valid_loci * 100

### Tumor-Only Mode (pro)
Hunter method:
```
pro_p = delValue / (normalValue + delValue + insertValue)
```
- With baseline: pro_p > mean + 3*sigma → unstable
- Without baseline (-i): pro_p > hunterThreshold (default 0.1) → unstable

## Baseline Construction

1. Read normal samples' `_all` files
2. Per locus: collect pro_p values across samples
3. Compute mean + 3*sigma → threshold
4. Filter: support < sampleNum (10) → LowSupportSamples

Baseline file format = scan output format, just with real threshold values.

## Why pro_p Works

Normal samples: reads length concentrated at reference length → pro_p ≈ 0
MSI samples: reads length distributed → pro_p > 0

pro_p specifically quantifies deletion signal (not insertion), because:
- Deletions more common in MSI (especially homopolymers)
- Insertions may come from sequencing errors

## Output Files

- `<prefix>`: MSI score summary
- `<prefix>_unstable`: unstable loci with pro_p, pro_q, coverage, threshold
- `<prefix>_all`: all valid loci
- `<prefix>_dis`: full distribution data
