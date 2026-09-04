"""Template: Style 3 — run: block + direct Python logic

Use when: rule needs Python data processing (pandas, JSON, file aggregation),
or needs to prepare input files before calling an external script.
Examples: msisensor-pro merge, spectrum, track (igv), arriba_report, StringTie TEChimericPlot

PITFALL: Always use FULL conda python path in generated .sh scripts.
Bare "python" resolves to /usr/bin/python which lacks conda-installed packages
(pysam, pandas, etc.). Also add `export PATH` for CLI tools (samtools, bedtools).
See references/generate-shell-scripts-from-run-blocks.md for details.
"""
from snakemake.logging import logger
import time
import os

indir = config.get("indir", "input")
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
samples = config.get("samples", [])
ROOT_DIR = config.get("ROOT_DIR", ".")


# Pure Python processing variant
rule <tool>_merge:
    input:
        files = expand(outdir + "/{sid}/{sid}.tsv", sid=samples)
    output:
        merged = outdir + "/<tool>_merged.tsv"
    log:
        logdir + "/all/<tool>_merge.log"
    run:
        import pandas as pd
        dfs = []
        for f in input.files:
            sid = os.path.basename(os.path.dirname(f))
            df = pd.read_table(f)
            df["sample_id"] = sid
            dfs.append(df)
        merged = pd.concat(dfs, ignore_index=True)
        merged.to_csv(output.merged, sep="\t", index=False)


# Mixed Python + shell variant (prepare files then call script)
rule <tool>_report:
    input:
        files = expand(outdir + "/{sid}/{sid}_passed.tsv", sid=samples),
    output:
        report = outdir + "/<tool>_report/summary.html"
    log:
        logdir + "/all/<tool>_report.log"
    conda:
        "<tool>.yaml"
    params:
        report_script = os.path.join(ROOT_DIR, "modules/<tool>/bin/report.py")
    run:
        current_time = time.strftime("%Y%m%d.%H:%M:%S", time.localtime())

        # Step 1: Python — prepare mapping/index file
        map_file = os.path.join(outdir, f"<tool>_file_map.{current_time}.tsv")
        with open(map_file, "w") as f:
            f.write("sample_id\tpath\n")
            for sample_file in input.files:
                sid = os.path.basename(os.path.dirname(sample_file))
                f.write(f"{sid}\t{sample_file}\n")

        # Step 2: Shell — call the report script
        # IMPORTANT: Use full conda python path, NOT bare "python"
        CONDA_BIN = "/data/pub/zhousha/env/mutation_0.1/eda061b3f191779ad16ff11ee6fe53b4_/bin"
        script = os.path.join(outdir, f"<tool>_report.{current_time}.sh")
        cmd = [
            f"{CONDA_BIN}/python", params.report_script,
            "--input", map_file,
            "--output", output.report,
        ]
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"export PATH={CONDA_BIN}:$PATH\n")
            f.write(" ".join(cmd) + "\n")
        shell("bash {script} > {log} 2>&1")
