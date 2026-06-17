#!/usr/bin/env python3
"""
Generate BED file from gene list using UCSC refGene coordinates.

Usage:
    python generate_bed_from_gene_list.py --genome hg38 --genes GENE1 GENE2 GENE3 --output genes.bed
    python generate_bed_from_gene_list.py --genome hg38 --gene-file gene_list.txt --output genes.bed

Gene list file format: one gene symbol per line.
"""

import argparse
import gzip
import os
import sys
import urllib.request


def download_refgene(genome: str, output_dir: str = "/tmp") -> str:
    """Download refGene file for specified genome.
    
    Parameters
    ----------
    genome : str
        Genome version (e.g., hg38, hg19, mm10)
    output_dir : str
        Directory to save downloaded file
        
    Returns
    -------
    str
        Path to downloaded file
    """
    url = f"https://hgdownload.soe.ucsc.edu/goldenPath/{genome}/database/refGene.txt.gz"
    output_path = os.path.join(output_dir, f"refGene_{genome}.txt.gz")
    
    if not os.path.exists(output_path):
        print(f"Downloading refGene for {genome}...")
        urllib.request.urlretrieve(url, output_path)
        print(f"Downloaded to {output_path}")
    else:
        print(f"Using cached file {output_path}")
    
    return output_path


def parse_refgene(refgene_path: str) -> dict:
    """Parse refGene file and extract gene coordinates.
    
    Parameters
    ----------
    refgene_path : str
        Path to refGene.txt.gz file
        
    Returns
    -------
    dict
        Gene symbol -> (chrom, start, end, strand)
    """
    gene_coords = {}
    
    with gzip.open(refgene_path, 'rt') as f:
        for line in f:
            fields = line.strip().split('\t')
            if len(fields) < 13:
                continue
            
            chrom = fields[2]
            start = int(fields[4])
            end = int(fields[5])
            strand = fields[3]
            gene_symbol = fields[12]
            
            # Keep longest transcript per gene
            current_span = end - start
            if gene_symbol not in gene_coords or \
               current_span > (gene_coords[gene_symbol][2] - gene_coords[gene_symbol][1]):
                gene_coords[gene_symbol] = (chrom, start, end, strand)
    
    return gene_coords


def load_gene_list(genes: list = None, gene_file: str = None) -> list:
    """Load gene list from arguments or file.
    
    Parameters
    ----------
    genes : list, optional
        List of gene symbols from command line
    gene_file : str, optional
        Path to file with gene symbols (one per line)
        
    Returns
    -------
    list
        List of gene symbols
    """
    gene_list = []
    
    if genes:
        gene_list.extend(genes)
    
    if gene_file:
        with open(gene_file) as f:
            for line in f:
                gene = line.strip()
                if gene and not gene.startswith('#'):
                    gene_list.append(gene)
    
    return list(set(gene_list))  # Deduplicate


def generate_bed(gene_list: list, gene_coords: dict, output_path: str) -> tuple:
    """Generate BED file from gene list.
    
    Parameters
    ----------
    gene_list : list
        List of gene symbols
    gene_coords : dict
        Gene symbol -> (chrom, start, end, strand)
    output_path : str
        Output BED file path
        
    Returns
    -------
    tuple
        (matched_count, unmatched_genes)
    """
    matched = 0
    unmatched = []
    
    with open(output_path, 'w') as f:
        f.write("#chrom\tchromStart\tchromEnd\tname\tscore\tstrand\n")
        
        for gene in sorted(gene_list):
            if gene in gene_coords:
                chrom, start, end, strand = gene_coords[gene]
                f.write(f"{chrom}\t{start}\t{end}\t{gene}\t0\t{strand}\n")
                matched += 1
            else:
                unmatched.append(gene)
    
    return matched, unmatched


def main():
    parser = argparse.ArgumentParser(
        description="Generate BED file from gene list using UCSC refGene coordinates"
    )
    parser.add_argument(
        "--genome", "-g",
        required=True,
        help="Genome version (e.g., hg38, hg19, mm10)"
    )
    parser.add_argument(
        "--genes", "-G",
        nargs="+",
        help="Gene symbols to include"
    )
    parser.add_argument(
        "--gene-file", "-f",
        help="File with gene symbols (one per line)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output BED file path"
    )
    parser.add_argument(
        "--cache-dir",
        default="/tmp",
        help="Directory to cache refGene download (default: /tmp)"
    )
    
    args = parser.parse_args()
    
    # Load gene list
    gene_list = load_gene_list(genes=args.genes, gene_file=args.gene_file)
    if not gene_list:
        print("Error: No genes specified. Use --genes or --gene-file", file=sys.stderr)
        sys.exit(1)
    
    print(f"Gene list contains {len(gene_list)} unique genes")
    
    # Download and parse refGene
    refgene_path = download_refgene(args.genome, args.cache_dir)
    print("Parsing gene coordinates...")
    gene_coords = parse_refgene(refgene_path)
    print(f"Found coordinates for {len(gene_coords)} genes")
    
    # Generate BED
    print("Generating BED file...")
    matched, unmatched = generate_bed(gene_list, gene_coords, args.output)
    
    # Report statistics
    print(f"\nResults:")
    print(f"  Matched: {matched}/{len(gene_list)} genes")
    print(f"  Unmatched: {len(unmatched)} genes")
    print(f"  Output: {args.output}")
    
    if unmatched:
        print(f"\nUnmatched genes: {', '.join(unmatched[:20])}")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")


if __name__ == "__main__":
    main()
