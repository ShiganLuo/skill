# Why Population Genomics Needs Far Less Depth Than Clinical

## The fundamental difference

| Dimension | Clinical | Population genomics |
|-----------|----------|-------------------|
| Question | "Does THIS sample have THIS variant?" | "What is the allele frequency in this population?" |
| Information source | Single sample's reads | Hundreds/thousands of samples + LD + reference panel |
| Required confidence | Per-variant, per-sample genotype call | Population-level frequency estimate |
| Depth per sample | 30-100x+ | 1-4x |

## Three factors enabling low-depth population studies

### 1. LD-based imputation

Reference panels (1000 Genomes, gnomAD) provide haplotype structure. Even with 0
reads at a site, the imputed genotype can be correct if flanking markers are
informative. More samples → better haplotype estimation → better imputation.

### 2. Sample size compensates for per-sample depth

1000 samples × 2x = 2000x total depth at each site (on average).
The allele frequency estimate has variance ~ p(1-p)/(2N·depth), which is tiny
with large N even at low depth.

### 3. Different statistical targets

- Clinical: binary genotype call (is this het or hom-ref?)
  → needs high posterior probability for ONE genotype
  
- Population: allele frequency or dosage regression
  → soft calls (dosage 0-2) are sufficient
  → GWAS uses dosage in regression, not hard genotype calls
  → Fst, Tajima's D, etc. only need frequency estimates

## Depth recommendations from literature

- **1000 Genomes Phase 3**: ~4x per sample, 2504 samples
- **UK Biobank**: ~30x but for rare variant calling; imputation from ~1x equivalent
- **GLIMPSE**: Demonstrates accurate imputation from 0.1-1x with reference panels
- **GATK Best Practices for germline**: 30x for clinical-grade individual calls

## When you CAN'T use low depth

- Somatic variant detection (need per-sample confidence)
- Rare variant discovery without reference panels
- De novo assembly
- Structural variant detection
- Clinical diagnostic reporting
