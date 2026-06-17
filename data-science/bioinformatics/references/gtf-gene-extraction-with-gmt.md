# Extracting Gene BED from GTF + GMT Files

## Overview

Common workflow: extract coordinates for a gene set (e.g., housekeeping genes)
from a GENCODE/Ensembl GTF annotation file, using a GMT file as the gene list.

## Input Files

### GMT Format (MSigDB gene sets)

Tab-separated: `name\turl\tgene1\tgene2\t...`

```
HOUNKPE_HOUSEKEEPING_GENES\thttps://www.gsea-msigdb.org/...\tAAMP\tAAR2\tAARS1\t...
```

Parse:
```python
from typing import Set

def parse_gmt(gmt_path: str) -> Set[str]:
    """Parse GMT file and extract gene symbol set.

    Parameters
    ----------
    gmt_path : str
        Path to GMT file

    Returns
    -------
    Set[str]
        Set of gene symbols
    """
    genes: Set[str] = set()
    with open(gmt_path) as f:
        for line in f:
            fields: list[str] = line.strip().split('\t')
            if len(fields) >= 3:
                genes.update(fields[2:])  # skip name and URL
    return genes
```

### GTF Format (GENCODE/Ensembl)

Standard 9-column GTF. Gene records have `gene_name` and `gene_id` in attributes.

Parse gene-level coordinates:
```python
import re
from typing import Dict, Tuple

def parse_gtf_gene_coords(
    gtf_path: str,
) -> Dict[str, Tuple[str, int, int, str, str]]:
    """Parse GTF and extract gene-level coordinates.

    Parameters
    ----------
    gtf_path : str
        Path to GTF file

    Returns
    -------
    Dict[str, Tuple[str, int, int, str, str]]
        {gene_symbol: (chrom, start, end, strand, gene_id)}
    """
    gene_coords: Dict[str, Tuple[str, int, int, str, str]] = {}
    name_pat: re.Pattern = re.compile(r'gene_name "([^"]+)"')
    id_pat: re.Pattern = re.compile(r'gene_id "([^"]+)"')

    with open(gtf_path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            fields: list[str] = line.split('\t')
            if len(fields) < 9 or fields[2] != 'gene':
                continue

            chrom: str = fields[0]
            start: int = int(fields[3]) - 1  # GTF is 1-based → BED 0-based
            end: int = int(fields[4])
            strand: str = fields[6]

            m_name = name_pat.search(fields[8])
            m_id = id_pat.search(fields[8])
            if m_name and m_id:
                gene_name: str = m_name.group(1)
                gene_id: str = m_id.group(1)
                # Keep longest transcript per gene
                if gene_name not in gene_coords or \
                   (end - start) > (gene_coords[gene_name][2] - gene_coords[gene_name][1]):
                    gene_coords[gene_name] = (chrom, start, end, strand, gene_id)

    return gene_coords
```

**PITFALL: GTF is 1-based, BED is 0-based.** Subtract 1 from GTF start:
```python
start = int(fields[3]) - 1  # GTF 1-based → BED 0-based
```

## Matching and BED Output

```python
from typing import List

def extract_gene_bed(
    gmt_path: str,
    gtf_path: str,
    output_bed: str,
) -> None:
    """Extract gene BED from GMT + GTF.

    Parameters
    ----------
    gmt_path : str
        Path to GMT file
    gtf_path : str
        Path to GTF file
    output_bed : str
        Output BED file path
    """
    hk_genes: Set[str] = parse_gmt(gmt_path)
    gene_coords: Dict[str, Tuple[str, int, int, str, str]] = parse_gtf_gene_coords(gtf_path)

    matched: List[Tuple[str, int, int, str, int, str]] = []
    unmatched: List[str] = []
    for gene in sorted(hk_genes):
        if gene in gene_coords:
            chrom, start, end, strand, _ = gene_coords[gene]
            matched.append((chrom, start, end, gene, 0, strand))
        else:
            unmatched.append(gene)

    with open(output_bed, 'w') as f:
        for chrom, start, end, name, score, strand in matched:
            f.write(f"{chrom}\t{start}\t{end}\t{name}\t{score}\t{strand}\n")

    print(f"Matched: {len(matched)}/{len(hk_genes)}")
    print(f"Unmatched: {len(unmatched)}")
    if unmatched:
        print(f"  Examples: {', '.join(unmatched[:5])}")
```

## Typical Match Rates

- HOUNKPE_HOUSEKEEPING_GENES (MSigDB): ~99.8% match with GENCODE v50
- Unmatched genes are typically aliases or recently renamed symbols
- Check aliases at HGNC: https://www.genenames.org/

## Performance Notes

- GTF parsing for gene-level records is fast (~30s for GENCODE v50)
- Only process lines where `fields[2] == 'gene'` (skip transcript/exon)
- Regex on attributes field is the bottleneck; pre-compile patterns
