#!/usr/bin/env python3
"""Generate a shell script to run PeakCalling workflow manually (bypassing snakemake module issues).

Usage:
    python scripts/generate_peakcalling_script.py \
        --data-dir /path/to/raw_fastq \
        --output-dir /path/to/output \
        --genome-fa /path/to/genome.fa \
        --macs3-bin /path/to/macs3 \
        --threads 10 \
        --samples 'Rpp21IP:Rpp21Input,Rpp14IP:Rpp14Input,Pop5IP:Pop5Input'

Outputs a bash script to stdout. Redirect to a file and run it.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Generate PeakCalling shell script")
    parser.add_argument("--data-dir", required=True, help="Raw FASTQ directory (with sample subdirs)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--genome-fa", required=True, help="Reference genome FASTA")
    parser.add_argument("--macs3-bin", default="macs3", help="MACS3 binary path")
    parser.add_argument("--threads", type=int, default=10, help="Thread count")
    parser.add_argument("--samples", required=True, help="IP:Input comma-separated pairs, e.g. Rpp21IP:Rpp21Input,Pop5IP:Pop5Input")
    parser.add_argument("--quality", type=int, default=30, help="cutadapt quality threshold")
    parser.add_argument("--pvalue", default="1e-5", help="MACS3 p-value cutoff")
    parser.add_argument("--genome-size", default="mm", help="MACS3 genome size (mm/hs)")
    args = parser.parse_args()

    pairs = {}
    all_samples = []
    for pair in args.samples.split(","):
        ip, inp = pair.strip().split(":")
        pairs[ip] = inp
        all_samples.extend([ip, inp])

    out = args.output_dir
    data = args.data_dir
    fa = args.genome_fa
    idx = f"{out}/bowtie2/mm/index/genome"
    log = f"{out}/log"

    lines = ["#!/bin/bash", "set -e", ""]

    # Create dirs
    for s in all_samples:
        lines.append(f"mkdir -p {out}/cutadapt/{s} {out}/bowtie2/mm/{s} {log}/{s}")
    for ip in pairs:
        lines.append(f"mkdir -p {out}/macs3/mm/{ip}")
    lines.append(f"mkdir -p {out}/bowtie2/mm/index {log}")
    lines.append("")

    # Step 1: cutadapt
    lines.append("# Step 1: Trimming")
    for s in all_samples:
        lines.append(f"cutadapt -q {args.quality} -o {out}/cutadapt/{s}/{s}_1.fq.gz -p {out}/cutadapt/{s}/{s}_2.fq.gz {data}/{s}/{s}_1.fq.gz {data}/{s}/{s}_2.fq.gz > {out}/cutadapt/{s}/{s}.cutadapt_report.txt 2> {log}/{s}/cutadapt.log")
        lines.append(f"echo '  Trimmed {s}'")
    lines.append("")

    # Step 2: bowtie2 index
    lines.append("# Step 2: Bowtie2 index")
    lines.append(f"bowtie2-build --threads {args.threads} {fa} {idx} 2> {log}/bowtie2_build.log")
    lines.append("")

    # Step 3: bowtie2 align
    lines.append("# Step 3: Bowtie2 alignment")
    for s in all_samples:
        lines.append(f"bowtie2 -x {idx} -1 {out}/cutadapt/{s}/{s}_1.fq.gz -2 {out}/cutadapt/{s}/{s}_2.fq.gz --threads {args.threads} --no-mixed --no-discordant 2> {log}/{s}/bowtie2.log | samtools sort -@ 4 -o {out}/bowtie2/mm/{s}/{s}.bam")
        lines.append(f"samtools index {out}/bowtie2/mm/{s}/{s}.bam")
        lines.append(f"echo '  Aligned {s}'")
    lines.append("")

    # Step 4: MACS3
    lines.append("# Step 4: MACS3 peak calling")
    for ip, inp in pairs.items():
        lines.append(f"{args.macs3_bin} callpeak -t {out}/bowtie2/mm/{ip}/{ip}.bam -c {out}/bowtie2/mm/{inp}/{inp}.bam --bw 200 -p {args.pvalue} -g {args.genome_size} --outdir {out}/macs3/mm/{ip} --name {ip} --seed 2346 2> {log}/{ip}/macs3.log")
        lines.append(f"echo '  Peak calling done: {ip}'")

    lines.append("")
    lines.append("echo '=== All done ==='")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
