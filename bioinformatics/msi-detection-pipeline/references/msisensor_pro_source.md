# msisensor-pro Source Code Analysis (v1.3.0)

Author: Peng Jia (Xi'an Jiaotong University, Ye Kai lab)
GitHub: https://github.com/xjtu-omics/msisensor-pro

## Architecture

4 subcommands in cmds.cpp:
- `scan` → HomoAndMicrosateScan() — scan reference genome for microsatellite loci
- `msi` → HomoAndMicrosateDisMsi() — paired tumor-normal MSI detection
- `baseline` → TrainMsiP() — build baseline from normal samples
- `pro` → HomoAndMicrosateDisMsiPro() — tumor-only MSI detection

## Key Data Structures

### HomoSite
Core struct for a microsatellite locus:
- chr, location, typeLen (1=homopolymer, 2-6=microsatellite)
- homoType: 2-bit-per-base encoding of repeat unit
- length: repeat count
- normalDis, tumorDis: `unsigned short*[100]` — length distribution histograms
- hunterValueU (pro_p), hunterValueV (pro_q): Hunter method ratios
- thres: per-locus threshold from baseline

### Param defaults
- MininalHomoSize=8, MaxHomoSize=50
- MaxMicrosate=6, Repeats=5
- s_dispots=100 (distribution bins)
- covCutoff=15 (depth threshold)
- fdrThreshold=0.05 (paired mode)
- hunterThreshold=0.1 (tumor-only hard threshold)
- sampleNum=10 (min samples for baseline)

## Algorithm: Paired Mode (msi command)

1. Per locus: compare normal vs tumor distribution
2. Chi-squared test: X² = Σ(Obs-Exp)²/Exp
3. p-value via incomplete gamma function
4. BH-FDR correction: FDR = pValue × totalSites / rank
5. Unstable if FDR ≤ 0.05
6. MSI score = unstable / total × 100%

## Algorithm: Tumor-Only Mode (pro command) — Hunter Method

Hunterp() function computes:
- normalValue = Σ(distribution[i] × matched_length)
- delValue = Σ(distribution[i] × deletion_deviation)
- insertValue = Σ(distribution[i] × insertion_deviation)
- pro_p = delValue / (normalValue + delValue + insertValue)
- pro_q = insertValue / (normalValue + delValue + insertValue)

Only pro_p is used for instability判定:
- With baseline: pro_p > threshold (per-locus mean+3σ)
- Without baseline (-i): pro_p > hunterThreshold (default 0.1)

## Baseline Construction

1. Read multiple normal samples' _all files
2. Per locus: collect pro_p values across samples
3. Compute mean + 3×stdev → threshold
4. QC: mark loci with support < sampleNum(10) as LowSupportSamples
5. Output format identical to scan output (just threshold column differs)

## Output Files

- `<prefix>`: MSI total score
- `<prefix>_unstable`: unstable loci list
- `<prefix>_all`: all candidate loci with FDR/pro_p
- `<prefix>_dis`: per-locus distribution details
