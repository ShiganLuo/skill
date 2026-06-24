# OncoWESuper QC Modules: Sample Identity & Contamination

Path: `workflow/confighub/workflow/OncoWESuper/modules/`

Three independent checks before somatic calling:

## 1. HomConsistency — HomoZygous Site Consistency

Module: `HomConsistency/`
Script: `bin/hom_consistence.py`
Threshold: `-t 0.65` (configurable in shell)

**Logic:**
1. From normal VCF, extract homozygous sites (AF=1 in INFO field)
2. For each site, pileup cancer BAM at that position, count alt reads
3. `caseFreq = alt_reads / total_depth`
4. If caseFreq >= 0.65 → that locus is "consistent"
5. Output: consistency percentage = consistent_loci / total_loci

**Why 0.65 works:**
- True homozygous site in matched tumor: caseFreq should be ~1.0
- Tumor purity pulls it down (50% purity → ~0.5-0.7)
- CNV and sequencing noise add variance
- Unmatched pairs: caseFreq depends on random genotype, concentrated in 0~0.5 range

**Output:** `hom_consistence_result.tsv` with mutcount and consistenceFreqd (%)

## 2. PairCheck21 — 21-SNP Sample Pair Verification

Module: `PairCheck21/`
Script: `bin/21snpcheck.py` (Python 2)
Helper: `bin/get_gt.py` (Python 3, extracts genotypes via bcftools)

**CRITICAL: "21" = number of SNP sites, NOT chromosome 21.**

SNP sites are in `bin/snpsite.bed`: 21 biallelic SNPs across chr1/2/3/7/8/9/10/12/13/14/15/16/17/18/20. Each chromosome contributes 1-2 sites.

**Logic:**
1. For each sample (cancer + normal), run `bcftools mpileup` + `bcftools call` on the 21 SNP sites
2. Extract DP4 (ref-fwd, ref-rev, alt-fwd, alt-rev) per site from VCF
3. Compute alt_freq = (alt_fwd + alt_rev) / total_reads per site
4. Build alt_freq vectors for both samples
5. Compute Pearson correlation between the two vectors
6. Classify using pre-trained distribution model

**Pre-trained model (`getPredefinedModel`):**
- Returns (p1V, p1S, p0V, p0S) based on sequencing depth bin
- p1V/p1S = mean/std of correlation for MATCHED pairs (same person)
- p0V/p0S = mean/std of correlation for UNMATCHED pairs (different person)

Example (depth>10, non-family):
```
Matched:   r ~ N(0.875, 0.022)  → concentrated 0.83~0.92
Unmatched: r ~ N(0.311, 0.060)  → concentrated 0.19~0.43
```

**Classification (`classifyNV`):**
```
d0 = |r - p0Vec| - p0S   # distance to unmatched distribution
d1 = |r - p1Vec| - p1S   # distance to matched distribution
d0 > d1 → matched (label=1)
d0 ≤ d1 → unmatched (label=0)
```

Subtracting std provides 1-sigma tolerance buffer at distribution edges.

**Two model families:**
- Family mode: p0Vec higher (~0.64 at depth>10) because relatives share more genotypes
- Non-family mode: p0Vec lower (~0.31), wider gap between matched/unmatched

**Output:** `*.sample_pair_check.tsv` + `*_output_corr_matrix.txt`

## 3. ContEstWES — Cross-Contamination Estimation

Module: `ContEstWES/` (paired) and `ContEstSingleWES/` (tumor-only)
Uses GATK `CalculateContamination`

```bash
gatk CalculateContamination \
  -I ${cancer_pileups} --matched-normal ${normal_pileups} \
  -O ${tsv} --tumor-segmentation ${tumor_seg}
```

Requires prior `GetPileupSummaries` on common SNP sites.

## Integration in Pipeline

These QC results feed into:
- `Report` module (`add_qc.py`): displays HOM (homozygous consistency %), CTR (contamination ratio), and pair check status
- `HotFilter` module: flags samples with contamination in siteFilter
- `PycloneWES` module: uses contamination status for filtering

## Pitfalls

1. **PairCheck21 uses Python 2** — the 21snpcheck.py script requires `python2`, while get_gt.py requires `python3`
2. **HomConsistency uses AF=1 filter** — only considers sites where normal is fully homozygous for alt, not heterozygous sites
3. **Threshold 0.65 is empirical** — not derived from statistical theory, tuned for typical tumor purity ranges (30-70%)
4. **21 SNPs is minimal** — sufficient for identity verification but lower power than panels with 50+ SNPs
