# SV Frequency Correction — Key Literature

Curated references for SV detection, frequency calibration, technical bias correction, and population SV databases.

## Population SV Frequency Databases (必读)

| PMID | Title | Journal | Year | Notes |
|------|-------|---------|------|-------|
| 32461652 | A structural variation reference for medical and population genetics | Nature | 2020 | **gnomAD SV** 奠基文章，人群 SV 频率标准 |
| 40702182 | Structural variation in 1,019 diverse humans based on long-read sequencing | Nature | 2025 | 长读长测序人群 SV 目录 |
| 36055201 | High-coverage whole-genome sequencing of the expanded 1000 Genomes Project cohort | Cell | 2022 | 1000 Genomes 高深度数据 |
| 36243989 | PGG.SV: a whole-genome-sequencing-based structural variant resource | Nucleic Acids Res | 2023 | 中国人群 SV 频率数据库 |

## Technical Bias Correction in SV/CNV Detection (核心方法学)

These papers address the specific statistical and technical biases that affect SV/CNV detection accuracy — the foundation for any frequency correction approach.

| PMID | Title | Journal | Year | Key Contribution |
|------|-------|---------|------|------------------|
| 26740523 | SV-Bay: structural variant detection in cancer genomes using a Bayesian approach with correction for GC-content and read mappability | Bioinformatics | 2016 | **Bayesian SV detection with explicit GC-content and read mappability bias correction** |
| 23275535 | Improving detection of copy-number variation by simultaneous bias correction and read-depth segmentation | Nucleic Acids Res | 2013 | **Simultaneous bias correction + read-depth segmentation** (single unified model) |
| 25802807 | GROM-RD: resolving genomic biases to improve read depth detection of copy number variants | PeerJ | 2015 | Systematic resolution of genomic biases (GC, mappability, repeat regions) for RD-based CNV |
| 22942022 | Statistical challenges associated with detecting copy number variations with NGS | Bioinformatics | 2012 | **Review of statistical challenges**: overdispersion, GC bias, mappability, batch effects |
| 23040492 | Discovery and statistical genotyping of copy-number variation from whole-exome sequencing depth | Am J Hum Genet | 2012 | Exome CNV calling with depth normalization and statistical genotyping |
| 23089826 | Modeling read counts for CNV detection in exome sequencing data | Stat Appl Genet Mol Biol | 2011 | Read count modeling approaches for exome CNV (Poisson/negative binomial) |
| 24465483 | PSCC: sensitive and reliable population-scale CNV detection based on low coverage sequencing | PLoS One | 2014 | Low-depth CNV detection with population-scale normalization |
| 22302147 | cn.MOPS: mixture of Poissons for discovering CNVs with a low false discovery rate | Nucleic Acids Res | 2012 | Poisson mixture model with built-in bias handling |
| 39030667 | A novel method addressing NGS-based mappability bias for sensitive detection of DNA alterations | J Bioinform Comput Biol | 2024 | Latest mappability bias correction approach |
| 35697522 | Polishing copy number variant calls on exome sequencing data via deep learning | Genome Res | 2022 | Deep learning post-processing to reduce CNV false positives |
| 32024845 | Inferring structural variant cancer cell fraction | Nat Commun | 2020 | SV VAF/cancer cell fraction inference methodology |

## SV Detection Methods (方法原理)

| PMID | Title | Journal | Year | Notes |
|------|-------|---------|------|-------|
| 22962449 | DELLY: structural variant discovery by paired-end and split-read | Bioinformatics | 2012 | 经典 SV caller |
| 26647377 | Manta: rapid detection of structural variants and indels | Bioinformatics | 2016 | Illumina 官方 SV caller |
| 29535149 | SvABA: genome-wide detection of SVs by local assembly | Genome Res | 2018 | 局部组装检测 SV |
| 21324876 | CNVnator: discover, genotype, and characterize CNVs | Genome Res | 2011 | 基于 read depth 的 CNV 检测 |
| 37604963 | GATK-gCNV enables discovery of rare CNVs from exome data | Nat Genet | 2023 | GATK 官方，含 GC/深度校正 |

## SV Filtering and Quality Control

| PMID | Title | Journal | Year | Key Contribution |
|------|-------|---------|------|------------------|
| 34034781 | Samplot: a platform for structural variant visual validation and automated filtering | Genome Biol | 2021 | Visual validation + automated SV filtering |
| 39240375 | CSV-Filter: deep learning-based comprehensive SV filtering for short and long reads | Bioinformatics | 2024 | DL-based SV filtering (quality scores) |
| 39297879 | VISTA: an integrated framework for structural variant discovery | Brief Bioinform | 2024 | Integrated SV discovery with filtering |
| 36035246 | Omics-informed CNV calls reduce false-positive rates and improve power | HGG Adv | 2022 | Multi-omics integration for CNV FP reduction |

## SV Detection Benchmarking

| PMID | Title | Journal | Year | Notes |
|------|-------|---------|------|-------|
| 38549092 | Comparison of structural variant callers for massive WGS data | BMC Genomics | 2024 | SV caller 比较 |
| 31136576 | Comprehensively benchmarking applications for detecting CNV | PLoS Comput Biol | 2019 | CNV 工具 benchmark |
| 34257369 | Benchmarking germline CNV calling tools from exome data | Sci Rep | 2021 | 外显子 CNV 工具评估 |
| 39668338 | Detection of germline CNVs from gene panel data | Brief Bioinform | 2024 | Panel CNV 检测评估 |

## Recommended Reading Order

1. **入门**: gnomAD SV (32461652) — 了解人群 SV 频率如何构建
2. **统计挑战**: PMID 22942022 — CNV 检测中的统计问题综述
3. **偏差校正方法**: PMID 26740523 (SV-Bay, GC+mappability) → PMID 23275535 (simultaneous correction)
4. **深度校正**: PMID 23040492 (exome depth normalization) → PMID 25802807 (GROM-RD)
5. **后处理过滤**: PMID 35697522 (DL polishing) → PMID 34034781 (Samplot filtering)
6. **评估**: SV caller 比较 (38549092) — 了解不同工具的假阳性率
7. **数据库**: PGG.SV (36243989) — 中国人群 SV 频率特点
