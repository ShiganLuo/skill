# msisensor-pro Source Analysis

Based on msisensor-pro v1.3.0 (Peng Jia, Xi'an Jiaotong University, Ye Lab).
Source: https://github.com/xjtu-omics/msisensor-pro

## Architecture

4 subcommands in `cmds.cpp`:

| Command | Function | Purpose |
|---------|----------|---------|
| `scan` | `HomoAndMicrosateScan()` | Scan reference genome for microsatellite loci |
| `msi` | `HomoAndMicrosateDisMsi()` | Paired tumor-normal MSI detection |
| `baseline` | `TrainMsiP()` | Build baseline from normal samples |
| `pro` | `HomoAndMicrosateDisMsiPro()` | Tumor-only MSI detection (core innovation) |

Two detection paths:
```
Path A (paired):  scan → msi
Path B (tumor-only): scan → baseline → pro
                    or scan → pro -i hard_threshold
```

## Core Data Structure: HomoSite

```cpp
struct HomoSite {
    string chr; int location;
    int typeLen;        // 1=homopolymer, 2-6=microsatellite
    string homoType;    // 2bit/base encoded repeat unit
    int length;         // repeat count
    string frontKmer, endKmer;  // flanking sequence (binary)
    string fbases, bases, ebases;  // flanking (text)
    unsigned short* normalDis[];  // [sample_idx][0-99] length distribution
    unsigned short* tumorDis[];
    float dif;          // area distance between distributions
    float pValue;       // chi-squared p-value
    float hunterValueU; // deletion ratio (pro_p)
    float hunterValueV; // insertion ratio (pro_q)
    float thres;        // per-locus threshold from baseline
};
```

## Key Algorithms

### 1. Reference Scanning (`scan`)

`refseq.cpp → ScanHomoAndMicrosate()`:
1. Per-chromosome sequential scan
2. Homopolymer: consecutive same base ≥ MininalHomoSize (default 8)
3. Microsatellite: for k=2..6, check k-mer repeat count ≥ Repeats (default 5)
4. Record: chrom, pos, repeat_unit, repeat_count, flanking (5bp ContextLength)
5. Output: `chromosome location repeat_unit_length repeat_times repeat_unit_bases left_flank right_flank threshold support_num filter`
   - Initial scan: threshold=-1, support_num=-1, filter=PASS

### 2. Length Distribution Computation

`polyscan.cpp` + Window (500kb chunks):
1. Group loci by genomic position into windows
2. Per window: fetch reads from BAM via `sam_fetch`
3. Per read: compute "effective length" at each microsatellite (considering indel from CIGAR)
4. Distribution: `bin[reflen-1]` = normal length, `< reflen-1` = deletion, `> reflen-1` = insertion
5. 100 bins total (`s_dispots=100`)

### 3. Paired Mode: Chi-squared + FDR

`homo.cpp → DisGenotyping()`, `chi.cpp → X2BetweenTwo()`, `sample.cpp → calculateFDR()`

Per locus:
1. Check normal and tumor coverage ≥ covCutoff (default 15)
2. Area distance: `d = (Max_area - Min_area) / Max_area`
3. Chi-squared test:
   - Optional coverage normalization (`-z 1`) when tumor >> normal depth
   - `Exp[i] = (Obs1[i]+Obs2[i]) * Sum_k / SumTotal`
   - `X² = Σ((Obs-Exp)² / Exp)`, df = effective_data_points - 1
   - p-value via incomplete Gamma function
4. BH-FDR correction: `FDR = pValue * total / rank`
5. Unstable if FDR ≤ 0.05 (default `fdrThreshold`)
6. **MSI score = unstable_loci / valid_loci × 100%**

### 4. Tumor-Only Mode: Hunter Method (Core Innovation)

`homo.cpp → HunterDisTumorSomatic()`, `Hunterp()`

**Hunterp() algorithm:**
```
Input: tumorDis[0..99], s_dispots, reflen

normalValue = Σ(tumorDis[i] * (i+1)) for i=0..reflen-2
            + Σ(tumorDis[i] * reflen) for i=reflen-1..end
            // total bases matching reference length

delValue = Σ(tumorDis[i] * (reflen - (i+1))) for i=0..reflen-2
           // total base deviation from deletions

insertValue = Σ(tumorDis[i] * (i+1-reflen)) for i=reflen-1..end
              // total base deviation from insertions

pro_p = delValue / (normalValue + delValue + insertValue)  // deletion ratio
pro_q = insertValue / (normalValue + delValue + insertValue)  // insertion ratio
```

**Intuition**: pro_p/pro_q quantify what fraction of total signal comes from length deviations. Normal loci → ~0, unstable loci → elevated.

**Instability判定**:
- With baseline: `pro_p > threshold` (per-locus, read from baseline file)
- Without baseline (`-i`): `pro_p > hunterThreshold` (default 0.1, hard cutoff)

**Why only pro_p (not pro_q)?** MSI manifests more commonly as deletions (especially in homopolymers), and deletion signals are more reliable (insertions may come from sequencing errors).

### 5. Baseline Construction

`distribution.cpp → TrainMsiP()`, `polyscan.cpp → MergeBaseline()`

1. Read config file listing normal sample `*_all` file paths
2. Per locus: collect pro_p values from all normal samples
3. Statistics: `mean(pro_p)`, `stdev(pro_p)`
4. Threshold: `mean + 3 * stdev` (99.7% confidence interval)
5. QC: samples with support < sampleNum (default 10) → `LowSupportSamples`
6. Output: same format as scan, but threshold column has actual value

**Key design**: baseline file format is identical to scan output — only the threshold column changes from -1 to actual value. This means `pro` command can directly read baseline files as microsatellite locus input.

## Comparison with Original msisensor

| Dimension | msisensor | msisensor-pro |
|-----------|-----------|---------------|
| Paired normal | Required | Optional |
| Scoring | Chi-squared | Chi-squared (paired) / Hunter (tumor-only) |
| Baseline | None | mean+3σ per-locus from normals |
| Input format | BAM only | BAM + CRAM (v1.2.0+) |
| Threshold | Fixed FDR | Hard cutoff (-i) or baseline soft cutoff |
| Locus file format | Binary-encoded | Text-encoded + threshold/support_num/filter columns |
| Parallelism | OpenMP | OpenMP (more in baseline/pro) |
| QC | Coverage only | Coverage + support_num filtering |

## Why pro_p Over Information Entropy?

Early versions used `comentropy` (information entropy). Hunter method was adopted because:
- Entropy is sensitive to ANY distribution change (including noise)
- pro_p specifically quantifies length-shift signal, better reflecting MSI biology
- Code retains entropy functions but pro mode uses Hunterp exclusively

## Key Parameters (param.cpp)

| Parameter | Default | Description |
|-----------|---------|-------------|
| MininalHomoSize | 8 | Min homopolymer length |
| MaxHomoSize | 50 | Max homopolymer length |
| MaxMicrosate | 6 | Max repeat unit length |
| Repeats | 5 | Min microsatellite repeat count |
| s_dispots | 100 | Distribution bins |
| covCutoff | 15 | Min coverage per site |
| windowSize | 500000 | BAM fetch window size |
| fdrThreshold | 0.05 | FDR cutoff (paired mode) |
| hunterThreshold | 0.1 | Default hard cutoff (tumor-only) |
| sampleNum | 10 | Min samples for baseline |

## Output Files

| File | Content |
|------|---------|
| `<prefix>` | MSI total score |
| `<prefix>_unstable` | Unstable loci list |
| `<prefix>_all` | All candidate loci with scores |
| `<prefix>_dis` | Per-locus length distribution details |
