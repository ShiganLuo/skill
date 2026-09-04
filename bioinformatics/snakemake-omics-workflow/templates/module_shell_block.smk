"""Template: Style 1 — Pure shell: block (simple single-command tools)

Use when: tool takes straightforward args, no conditional flags, no pipes.
Examples: samtools flagstat, fastqc, gatk MarkDuplicates, gatk BaseRecalibrator
"""
from snakemake.logging import logger

indir = config.get("indir", "input")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
samples = config.get("samples", [])


rule <tool>_<action>:
    input:
        infile = indir + "/{sample_id}/{sample_id}.<ext>"
    output:
        outfile = outdir + "/{sample_id}/{sample_id}.<out_ext>"
    log:
        logdir + "/{sample_id}/<tool>_<action>.log"
    threads: 4
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>"
    shell:
        """
        mkdir -p $(dirname {output.outfile})
        {params.tool} <args> {input.infile} {output.outfile} > {log} 2>&1
        """


rule <tool>_result:
    input:
        outfile = outdir + "/{sample_id}/{sample_id}.<out_ext>"
