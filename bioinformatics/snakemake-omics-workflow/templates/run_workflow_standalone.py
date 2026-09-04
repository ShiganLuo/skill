#!/usr/bin/env python3
"""
Standalone run script template for new workflows.

Use when run.py cannot be modified (read-only constraint).
This script generates the config JSON and runs the subworkflow independently.

Usage:
    python run_<Workflow>.py --indir /path/to/fastq --outdir /path/to/output --samples sample1,sample2
"""
import argparse
import json
import os
import subprocess
import sys
from typing import Dict, Any, List


def load_model_json(model_json_file: str) -> Dict[str, Any]:
    """Load model JSON template from disk."""
    with open(model_json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_outfiles(outdir: str, samples: List[str]) -> List[str]:
    """Build list of expected output files."""
    outfiles = []
    for sample_id in samples:
        # TODO: Add expected output paths per sample
        outfiles.append(f"{outdir}/<module>/{sample_id}/{sample_id}.<ext>")
    return outfiles


def run_workflow(
    datajson: Dict[str, Any],
    samples: List[str],
    indir: str,
    outdir: str,
) -> str:
    """Prepare input JSON for workflow."""
    datajson["indir"] = indir
    datajson["outdir"] = outdir
    logdir = os.path.join(outdir, "log")
    os.makedirs(logdir, exist_ok=True)
    datajson["logdir"] = logdir
    datajson["ROOT_DIR"] = os.path.dirname(os.path.abspath(__file__))

    datajson["samples"] = samples
    datajson["outfiles"] = build_outfiles(outdir, samples)

    instance_json = os.path.join(outdir, "raw.json")
    os.makedirs(outdir, exist_ok=True)
    with open(instance_json, 'w', encoding='utf-8') as wf:
        json.dump(datajson, wf, indent=2, ensure_ascii=False)
    return instance_json


def build_snakemake_cmd(
    root_dir: str,
    workflow_name: str,
    input_json: str,
    threads: int,
    conda_prefix: str,
    dry_run: bool,
    snakemake_args: List[str],
) -> List[str]:
    """Build snakemake command."""
    cmd = [
        "snakemake",
        "-s",
        f"{root_dir}/subworkflow/{workflow_name}.smk",
        "--configfile",
        input_json,
        "--cores",
        str(threads),
        "--conda-prefix",
        conda_prefix,
        "--use-conda",
        "--conda-frontend",
        "mamba",
    ]
    if dry_run:
        cmd.append("--dry-run")
    if snakemake_args:
        cmd.extend(snakemake_args)
    return cmd


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run <Workflow> workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--indir', type=str, required=True,
                        help='Input directory containing FASTQ files')
    parser.add_argument('--outdir', type=str, required=True,
                        help='Output directory for results')
    parser.add_argument('--samples', type=str, default='',
                        help='Comma-separated list of sample IDs')
    parser.add_argument('--threads', type=int, default=30,
                        help='Number of threads')
    parser.add_argument('--conda-prefix', type=str,
                        default='/data/pub/zhousha/env/<workflow>',
                        help='Conda prefix for snakemake')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run mode')
    parser.add_argument('--snakemake-args', nargs=argparse.REMAINDER,
                        default=[],
                        help='Additional arguments forwarded to snakemake')
    # TODO: Add workflow-specific arguments
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse sample list
    samples = [s.strip() for s in args.samples.split(',') if s.strip()]
    if not samples:
        print("Error: At least one sample must be specified via --samples")
        sys.exit(1)

    # Load model JSON
    root_dir = os.path.dirname(os.path.abspath(__file__))
    model_json_file = os.path.join(root_dir, "config/<Workflow>.json")
    if not os.path.exists(model_json_file):
        print(f"Error: Model JSON not found: {model_json_file}")
        sys.exit(1)

    workflow_config = load_model_json(model_json_file)

    # TODO: Update config with command line arguments
    # workflow_config["Procedure"]["<tool>"] = args.<tool_path>

    # Run workflow preparation
    abs_outdir = os.path.abspath(args.outdir)
    input_json = run_workflow(
        workflow_config,
        samples,
        args.indir,
        abs_outdir,
    )

    print(f"Generated config: {input_json}")

    # Build and run snakemake command
    cmds = build_snakemake_cmd(
        root_dir,
        "<Workflow>",
        input_json,
        args.threads,
        args.conda_prefix,
        args.dry_run,
        args.snakemake_args,
    )

    print(f"Running: {' '.join(cmds)}")
    subprocess.run(cmds, check=True)


if __name__ == "__main__":
    main()
