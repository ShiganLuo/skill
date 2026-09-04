"""Template: Alignment module with paired/single input dispatch

Use when: module needs to handle both paired-end and single-end FASTQ.
Uses dynamic input function + index fallback pattern.
Examples: star, bowtie2, hisat2, fastqc
"""
from snakemake.logging import logger
import time
import os

indir = config.get("indir", "input")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
paired_samples = config.get("paired_samples", [])
single_samples = config.get("single_samples", [])


rule <tool>_index:
    input:
        fasta = config.get("genome", {}).get("fasta")
    output:
        # For directory-based indexes (STAR):
        # index = directory(outdir + "/index")
        # For file-based indexes (bowtie2, hisat2):
        index = expand(outdir + "/index/genome.{ext}", ext=["1.bt2", "2.bt2", "3.bt2", "4.bt2", "rev.1.bt2", "rev.2.bt2"])
    log:
        logdir + "/index/<tool>_index.log"
    threads: 12
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>",
        index_prefix = outdir + "/index/genome"
    shell:
        """
        mkdir -p $(dirname {params.index_prefix})
        {params.tool} <index_args> {input.fasta} {params.index_prefix} > {log} 2>&1
        """


def get_<tool>_index(wildcards):
    """Prefer config-provided index, fall back to module-generated."""
    cfg_prefix = config.get("genome", {}).get("index_prefix")
    if cfg_prefix:
        first_file = f"{cfg_prefix}.1.bt2"
        if os.path.exists(first_file):
            return [f"{cfg_prefix}.{ext}" for ext in SUFFIXES]
    return [f"{outdir}/index/genome.{ext}" for ext in SUFFIXES]


def get_alignment_input(wildcards):
    """Dynamically determine paired-end or single-end input."""
    paired_r1 = f"{indir}/{wildcards.sample_id}/{wildcards.sample_id}_1.fq.gz"
    paired_r2 = f"{indir}/{wildcards.sample_id}/{wildcards.sample_id}_2.fq.gz"
    single = f"{indir}/{wildcards.sample_id}/{wildcards.sample_id}.single.fq.gz"

    if wildcards.sample_id in paired_samples:
        return [paired_r1, paired_r2]
    elif wildcards.sample_id in single_samples:
        return [single]
    else:
        raise ValueError(f"Sample {wildcards.sample_id} not in paired_samples or single_samples")


rule <tool>_align:
    input:
        fastq = get_alignment_input,
        index = get_<tool>_index
    output:
        bam = outdir + "/{sample_id}/{sample_id}.bam",
        bai = outdir + "/{sample_id}/{sample_id}.bam.bai"
    log:
        logdir + "/{sample_id}/<tool>_align.log"
    threads: 12
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>",
        samtools = config.get("Procedure", {}).get("samtools") or "samtools",
        index_prefix = lambda wildcards, input: input.index[0].rsplit(".", 2)[0],
        input_params = lambda wildcards, input: \
            f"-1 {input.fastq[0]} -2 {input.fastq[1]}" if len(input.fastq) == 2 else f"-U {input.fastq[0]}"
    run:
        current_time = time.strftime("%Y%m%d.%H:%M:%S", time.localtime())
        script = f"{outdir}/{wildcards.sample_id}/<tool>_align.{current_time}.sh"
        cmd_align = [
            params.tool,
            "-x", params.index_prefix,
            params.input_params,
            "--threads", str(threads),
            "|", params.samtools, "sort", "-@", str(threads), "-o", output.bam
        ]
        cmd_index = [params.samtools, "index", "-@", str(threads), output.bam]
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(" ".join(cmd_align) + "\n")
            f.write(" ".join(cmd_index) + "\n")
        shell(f"bash {script} > {log} 2>&1")


rule <tool>_result:
    input:
        bam = outdir + "/{sample_id}/{sample_id}.bam",
        bai = outdir + "/{sample_id}/{sample_id}.bam.bai"
