"""Template: Style 2 — run: block + shell script generation (complex commands)

Use when: tool needs dynamic args, conditional flags, pipes, multi-step sequences.
Generated .sh scripts serve as debug artifacts and reproducibility records.
Examples: pbsv, deepvariant, hiphase, star, bowtie2, hisat2, arriba
"""
from snakemake.logging import logger
import time
import os

indir = config.get("indir", "input")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
samples = config.get("samples", [])
fasta = config.get("genome", {}).get("fasta")


rule <tool>_<action>:
    input:
        bam = indir + "/{sample_id}/{sample_id}.bam",
        bai = indir + "/{sample_id}/{sample_id}.bam.bai",
        fasta = fasta
    output:
        vcf = outdir + "/{sample_id}/{sample_id}.vcf.gz"
    log:
        logdir + "/{sample_id}/<tool>_<action>.log"
    threads: 8
    conda:
        "<tool>.yaml"
    params:
        tool = config.get("Procedure", {}).get("<tool>") or "<tool>",
        # Optional parameters with defaults
        extra = config.get("Params", {}).get("<tool>", {}).get("extra") or ""
    run:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info(f"Start <tool> <action> for sample {wildcards.sample_id} at {current_time}")
        script = os.path.join(outdir, f"<tool>_<action>_{current_time}.sh")
        cmd = [
            params.tool,
            "--num-threads", str(threads),
            "--reference", input.fasta,
            input.bam,
            output.vcf
        ]
        # Optional: conditional flags
        # if params.extra:
        #     cmd += ["--extra", params.extra]
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(" ".join(cmd) + "\n")
        shell("bash {script} > {log} 2>&1")


# Multi-step variant (align + sort + index):
# rule <tool>_align:
#     run:
#         current_time = time.strftime(...)
#         script = f"..."
#         cmd1 = [params.aligner, "-x", index, "-1", r1, "-2", r2, "|",
#                 "samtools", "view", "-bS", "-", ">", output.bam]
#         cmd2 = [params.samtools, "sort", "-@", str(threads), "-o", output.bam, input.bam]
#         cmd3 = [params.samtools, "index", "-@", str(threads), output.bam]
#         with open(script, "w") as f:
#             f.write("#!/bin/bash\n")
#             for cmd in [cmd1, cmd2, cmd3]:
#                 f.write(" ".join(cmd) + "\n")
#         shell(f"bash {script} > {log} 2>&1")


rule <tool>_result:
    input:
        vcf = outdir + "/{sample_id}/{sample_id}.vcf.gz"
