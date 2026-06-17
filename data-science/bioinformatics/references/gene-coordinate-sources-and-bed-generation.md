# Gene Coordinate Sources and BED File Generation

## UCSC refGene Coordinates

Download URL pattern:
```
https://hgdownload.soe.ucsc.edu/goldenPath/{genome}/database/refGene.txt.gz
```

Examples:
- hg38: `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/refGene.txt.gz`
- hg19: `https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/refGene.txt.gz`
- mm10: `https://hgdownload.soe.ucsc.edu/goldenPath/mm10/database/refGene.txt.gz`

### refGene.txt.gz Column Format

| Column | Index | Description |
|--------|-------|-------------|
| bin | 0 | Indexing bin |
| name | 1 | Transcript ID (e.g., NM_001354609) |
| chrom | 2 | Chromosome (chr1, chr2, ...) |
| strand | 3 | + or - |
| txStart | 4 | Transcription start position (0-based) |
| txEnd | 5 | Transcription end position |
| cdsStart | 6 | Coding region start |
| cdsEnd | 7 | Coding region end |
| exonCount | 8 | Number of exons |
| exonStarts | 9 | Comma-separated exon start positions |
| exonEnds | 10 | Comma-separated exon end positions |
| score | 11 | Score (usually 0) |
| name2 | 12 | **Gene symbol** (e.g., GAPDH) |

**Key**: Column 12 (`name2`) is the gene symbol used for matching gene lists.

### Parsing Pattern

```python
import gzip

gene_coords = {}  # gene_symbol -> (chrom, start, end, strand)

with gzip.open("refGene.txt.gz", 'rt') as f:
    for line in f:
        fields = line.strip().split('\t')
        if len(fields) >= 13:
            chrom = fields[2]
            start = int(fields[4])
            end = int(fields[5])
            strand = fields[3]
            gene_symbol = fields[12]
            
            # Keep longest transcript per gene
            if gene_symbol not in gene_coords or \
               (end - start) > (gene_coords[gene_symbol][2] - gene_coords[gene_symbol][1]):
                gene_coords[gene_symbol] = (chrom, start, end, strand)
```

**PITFALL**: Multiple transcripts exist per gene. For gene-level BED, keep the longest transcript (largest span) or merge intervals with `bedtools merge`.

## Housekeeping Gene Lists

### Source 1: Eisenberg & Levanon 2013 (Most Cited)

Paper: "Housekeeping genes, evolution" — Nature Reviews Genetics 2013

Curated list of ~3,800 human housekeeping genes based on:
- Uniform expression across tissues
- Low tissue specificity
- Constitutive expression

Common genes in this set include:
- Ribosomal proteins: RPL*, RPS*
- Translation factors: EEF1A1, EEF2, EIF*
- Proteasome subunits: PSMA*, PSMB*, PSMC*, PSMD*
- Cytoskeleton: ACTB, ACTG1, TUBB, VIM
- Metabolism: GAPDH, PKM, LDHA, ALDOA, ENO1
- Chaperones: HSP90AA1, HSPA8, HSPD1
- Ubiquitin: UBB, UBC, UBA52

### Source 2: HGNC Gene Groups

HGNC maintains gene group annotations. Search for "housekeeping" at:
```
https://www.genenames.org/
```

REST API (may require specific query syntax):
```
https://rest.genenames.org/search/gene_group:housekeeping
```

### Source 3: UniHouse Database

Specialized database for housekeeping genes:
```
http://housekeeping.unicamp.br/
```

### Source 4: Tissue-Specific Gene Database (TSGD)

Contains both housekeeping and tissue-specific classifications.

## BED File Generation Workflow

### Step 1: Download gene coordinates
```bash
curl -s "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/refGene.txt.gz" \
  -o refGene_hg38.txt.gz
```

### Step 2: Parse and build coordinate lookup
```python
gene_coords = {}  # symbol -> (chrom, start, end, strand)
# Parse as shown above
```

### Step 3: Match gene list and write BED
```python
with open("output.bed", 'w') as f:
    f.write("#chrom\tchromStart\tchromEnd\tname\tscore\tstrand\n")
    for gene in sorted(gene_list):
        if gene in gene_coords:
            chrom, start, end, strand = gene_coords[gene]
            f.write(f"{chrom}\t{start}\t{end}\t{gene}\t0\t{strand}\n")
```

### Step 4: Report matching statistics
```python
matched = sum(1 for g in gene_list if g in gene_coords)
unmatched = [g for g in gene_list if g not in gene_coords]
print(f"Matched: {matched}/{len(gene_list)}")
if unmatched:
    print(f"Unmatched: {', '.join(unmatched[:20])}")
```

## Common Pitfalls

1. **Gene symbol aliases**: Some genes have aliases (e.g., BAX = BCL2L4). If a gene doesn't match, check aliases at HGNC.

2. **Withdrawn symbols**: Gene symbols may be withdrawn or merged. Use HGNC's symbol checker.

3. **Multiple transcripts**: refGene has one row per transcript. For gene-level BED, aggregate by gene symbol (column 12).

4. **Coordinate version**: Ensure refGene version matches your target genome (hg19 vs hg38).

5. **Strand information**: BED strand column uses `+`/`-`, matching refGene format directly.

## Quick Command Reference

```bash
# Download refGene for specific genome
curl -s "https://hgdownload.soe.ucsc.edu/goldenPath/${GENOME}/database/refGene.txt.gz" -o refGene_${GENOME}.txt.gz

# Count genes in BED file
wc -l genes.bed

# Extract gene names from BED
cut -f4 genes.bed | sort -u

# Intersect with other BED
bedtools intersect -a data.bed -b genes.bed -wa -wb

# Coverage statistics
bedtools coverage -a data.bed -b genes.bed -mean
```
