# dbSNP VCF Management & Chromosome Naming Conventions

## dbSNP Release Structure (NCBI FTP)

```
https://ftp.ncbi.nih.gov/snp/latest_release/VCF/
├── GCF_000001405.25.gz      # GRCh37.p13 (hg19), ~26GB
├── GCF_000001405.25.gz.tbi
├── GCF_000001405.40.gz      # GRCh38.p14 (hg38), ~28GB
├── GCF_000001405.40.gz.tbi
└── CHECKSUMS
```

### GCF Accession → Assembly Mapping

| Accession | Assembly | Common Name |
|-----------|----------|-------------|
| GCF_000001405.25 | GRCh37.p13 | hg19 |
| GCF_000001405.40 | GRCh38.p14 | hg38 |

**Build history**: build 151 (2018) used `1,2,3...` chrom format; build 157 (2024) uses `NC_000001.11...` RefSeq accessions.

### Key INFO Fields

| Field | Meaning | Filter usage |
|-------|---------|--------------|
| `COMMON=1` | ≥1% MAF in any 1000Genomes pop | `-i 'COMMON=1'` for common SNPs |
| `FREQ=...` | Per-study allele frequencies | Extract population-specific MAF |
| `RS=NNNN` | dbSNP rs number | Cross-reference |
| `VC=SNV/INDEL/DIV` | Variant class | Filter by type |

## Chromosome Naming Formats (3 systems)

| Format | Example | Used by |
|--------|---------|---------|
| RefSeq accession | `NC_000001.11` | dbSNP build 157+, NCBI |
| Bare number | `1, 2, ..., X, Y, MT` | dbSNP ≤build 151, some tools |
| UCSC-style | `chr1, chr2, ..., chrX, chrY, chrM` | UCSC, GENCODE, most BAMs |

**PITFALL**: Mixing formats causes silent failures. `bam-gps`, `bcftools`, `samtools` all do interval lookups — if the VCF says `1` and the BAM header says `chr1`, the iterator returns nothing or asserts.

### Full GRCh38 RefSeq → Number Mapping

```
NC_000001.11  → 1       NC_000012.12  → 12      NC_000023.11  → X
NC_000002.12  → 2       NC_000013.12  → 13      NC_000024.10  → Y
NC_000003.12  → 3       NC_000014.9   → 14      NC_012920.1   → MT
NC_000004.12  → 4       NC_000015.10  → 15
NC_000005.10  → 5       NC_000016.10  → 16
NC_000006.12  → 6       NC_000017.11  → 17
NC_000007.14  → 7       NC_000018.10  → 18
NC_000008.11  → 8       NC_000019.10  → 19
NC_000009.12  → 9       NC_000020.11  → 20
NC_000010.11  → 10      NC_000021.9   → 21
NC_000011.10  → 11      NC_000022.11  → 22
```

### Full GRCh37 RefSeq → Number Mapping

```
NC_000001.10  → 1       NC_000012.11  → 12      NC_000023.10  → X
NC_000002.11  → 2       NC_000013.11  → 13      NC_000024.9   → Y
NC_000003.11  → 3       NC_000014.8   → 14      NC_012920.1   → MT
NC_000004.11  → 4       NC_000015.9   → 15
NC_000005.9   → 5       NC_000016.9   → 16
NC_000006.11  → 6       NC_000017.10  → 17
NC_000007.13  → 7       NC_000018.9   → 18
NC_000008.10  → 8       NC_000019.9   → 19
NC_000009.11  → 9       NC_000020.10  → 20
NC_000010.10  → 10      NC_000021.8   → 21
NC_000011.9   → 11      NC_000022.10  → 22
```

## Common Pipeline: Region-Filtered dbSNP VCF

Pattern: take full dbSNP VCF → intersect with BED → produce lightweight subset.

```bash
# 1. Download
wget -c https://ftp.ncbi.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz
wget https://ftp.ncbi.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz.tbi

# 2. Rename chromosomes (RefSeq → number)
bcftools annotate --rename-chrs refseq_to_num.map \
    GCF_000001405.40.gz -Oz -o dbsnp157_GRCh38_num.vcf.gz
bcftools index dbsnp157_GRCh38_num.vcf.gz

# 3. Filter to regions + common flag
bcftools view \
    -R housekeeping_genes.bed \
    -i 'COMMON=1' \
    dbsnp157_GRCh38_num.vcf.gz \
    -Oz -o common_GRCh38_hkg.vcf.gz
bcftools index common_GRCh38_hkg.vcf.gz
```

### Generating `refseq_to_num.map`

```bash
# Extract from BAM header and map
samtools view -H sample.bam | grep '^@SQ' | sed 's/SN:\([0-9XYM]*\).*/\1/' | \
    paste <(samtools view -H sample.bam | grep '^@SQ' | \
            sed 's/.*SN:\(NC_[0-9.]*\).*/\1/') - | \
    head -25
```

Or hardcode from the table above (24 lines + MT).

## Diagnosing Reference Version Mismatch

**Symptoms**:
- `Assertion 'aux->itr' failed` in htslib-based tools (bam-gps, bcftools)
- Empty output from `bcftools view -R` with no error
- `samtools mpileup` returning 0 variants at known SNP sites

**Root cause**: chromosome names in VCF/BED don't match BAM header.

**Diagnosis steps**:
```bash
# 1. Check BAM header chrom format
samtools view -H sample.bam | grep '^@SQ' | head -5

# 2. Check VCF chrom format
bcftools view -H variants.vcf.gz | head -5 | cut -f1

# 3. Check BED chrom format
head -5 regions.bed | cut -f1

# 4. All three must use the same naming convention
```
