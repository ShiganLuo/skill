# Somatic Mutation QC: Contamination & Index Matching

Quality control modules in the OncoWESuper somatic mutation pipeline for detecting
index mismatches (sample swaps) and cross-contamination.

## Three QC Modules

### 1. HomConsistency — Homozygous Site Consistency (Index Mismatch Detection)

**Module**: `modules/HomConsistency/`
**Script**: `hom_consistence.py`
**Purpose**: Detect if tumor and normal samples come from the same patient.

**Algorithm**:
1. From normal sample's germline VCF, extract homozygous sites (AF=1)
2. For each homozygous site, check the alt frequency in the tumor BAM
3. If tumor and normal are from the same patient, alt frequency should be consistent
4. Threshold: caseFreq ≥ 0.65 → "consistent"
5. Output: consistency percentage = consistent_sites / total_homozygous_sites

**CLI**:
```bash
python hom_consistence.py \
  -t 0.65 \           # consistency threshold
  -c cancer.bam \     # tumor BAM
  -n normal.snp.vcf \ # normal germline VCF (AF=1 sites)
  -o output_dir/
```

**Output**: `hom_consistence_result.tsv`
- `mutcount`: total homozygous sites checked
- `consistenceFreqd`: consistency percentage (e.g. "92%")

**Interpretation**: Low consistency → index swap or sample mix-up.

### 2. PairCheck21 — 21-chromosome SNP Pair Verification

**Module**: `modules/PairCheck21/`
**Purpose**: Verify tumor-normal pairing using 21-chromosome SNP genotypes.

**Algorithm**:
1. Extract genotypes at known SNP sites (snpsite.bed) from both BAMs
2. Use bcftools to call genotypes at these positions
3. Compare genotypes between cancer and normal
4. Concordance rate indicates correct pairing

**Inputs**:
- cancer_bam, normal_bam
- snpsite.bed (21-chromosome SNP positions)
- Reference genome (hg19)

**Output**: `{sample}.sample_pair_check.tsv`

### 3. ContEstWES — Cross-Contamination Estimation

**Module**: `modules/ContEstWES/` / `modules/ContEstSingleWES/`
**Purpose**: Estimate DNA cross-contamination fraction using GATK CalculateContamination.

**Algorithm**:
```bash
gatk CalculateContamination \
  -I ${cancer_pileups} \
  --matched-normal ${normal_pileups} \
  -O ${output}.conest.tsv \
  --tumor-segmentation ${output}.segments.table
```

Uses GetPileupSummaries output to estimate contamination fraction from
homozygous sites showing unexpected alleles.

**Output**: contamination table (fraction) + segmentation table

## How They Work Together

```
Normal BAM ──┬── HomConsistency ──→ consistency % (index check)
             │
Tumor BAM ───┼── PairCheck21 ───→ genotype concordance (pairing check)
             │
             └── ContEstWES ────→ contamination fraction (cross-contam)
```

All three are independent checks. A passing sample should have:
- High homozygous consistency (>60-80%)
- High genotype concordance at SNP sites
- Low contamination fraction (<5%)

## Report Integration

The Report module (`modules/Report/bin/add_qc.py`) collects these results:
- `CTR`: Contamination Ratio (from ContEstWES)
- `HOM`: Homozygous consistency (from HomConsistency)
- `Sex`: Sex check (separate module)

## Pitfalls

### HomConsistency threshold is lenient
- Default 0.65 means 65% consistency is enough to pass
- This is intentionally lenient because tumor samples have somatic alterations
- True index swaps typically show <30% consistency

### PairCheck21 uses only chr21 SNPs
- Limited marker count → may miss subtle issues
- Complementary to HomConsistency, not a replacement

### ContEstSingleWES vs ContEstWES
- ContEstWES: paired mode (uses matched normal)
- ContEstSingleWES: tumor-only mode (no matched normal)
- Paired mode is more accurate
