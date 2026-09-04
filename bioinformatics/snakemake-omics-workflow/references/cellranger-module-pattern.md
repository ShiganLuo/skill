# Cell Ranger Module Pattern — Rule-only-validates, logic-in-script

## Principle

Rules in `.smk` files must ONLY:
1. Declare inputs/outputs/log/threads
2. Set params (python, script, arguments)
3. Construct cmd list, write to .sh, call via shell

ALL processing logic lives in Python scripts under `bin/`.

## Critical: cellranger has NO --output/--output-dir flag

Both `cellranger mkref` and `cellranger count` create output in the **current working directory**. They do NOT accept `--output` or `--output-dir`.

**Fix for mkref:** Set `cwd=args.output` in subprocess:
```python
subprocess.check_call(cmd, cwd=args.output)
```

**Fix for count:** Add `cd {outdir}` in the shell script:
```python
with open(command_script, "w") as f:
    f.write("#!/usr/bin/env bash\nset -euo pipefail\n")
    f.write(f"cd {outdir}\n")  # ← MUST cd to output dir first
    f.write(" ".join(cmd) + "\n")
```

**Stale directory cleanup:** cellranger fails if the target directory exists but isn't a valid pipestance. Always clean up before running:
```python
mkref_dir = os.path.join(args.output, f"mkref_{args.genome}")
if os.path.exists(mkref_dir):
    import shutil
    shutil.rmtree(mkref_dir)
```

## Wrong: inline bash in run block

```python
# DON'T: sed/awk/grep embedded in .smk via string lists
run:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"cat {q(fasta_in)} \\",
        "    | sed -E 's/^(\\\\S+).*/>\\\\1 \\\\1/' \\",  # escaping nightmare
        "    | sed -E 's/^>([0-9]+|[XY]) />chr\\\\1 /' \\",
        ...
    ]
    with open(script_path, "w") as f:
        f.write("\n".join(lines))
```

Problems:
- Backslash escaping across Python → bash → sed is error-prone
- The cellranger_ref sed patterns had a bug (missing `>` in regex) that
  required multiple fix attempts
- Logic not testable independently

## Right: logic in bin/ script

### bin/cellranger_ref.py
```python
import argparse, os, re, subprocess

def modify_fasta_headers(fasta_in, fasta_out):
    """Add chr prefix, handle chrM."""
    with open(fasta_in) as fin, open(fasta_out, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                parts = line[1:].split(None, 1)
                name = parts[0]
                chr_name = name
                if re.match(r"^[0-9]+$", name) or name in ("X", "Y"):
                    chr_name = f"chr{name}"
                elif name == "MT":
                    chr_name = "chrM"
                line = f">{chr_name} {name}\n"
            fout.write(line)

def modify_gtf_ids(gtf_in, gtf_out):
    """Strip Ensembl version suffixes."""
    for id_type in ("gene_id", "transcript_id", "exon_id"):
        line = re.sub(
            rf'{id_type} "(ENS(?:MUS)?[GTE]\d+)\.(\d+)";',
            rf'{id_type} "\1"; {id_type.replace("_id", "_version")} "\2";',
            line,
        )

def filter_gtf_by_biotype(gtf_in, gtf_out):
    """Filter by biotype allowlist, exclude readthrough, remove PAR_Y."""
    # collect gene IDs from passing transcripts
    # filter to allowlisted genes
    # exclude chrY PAR range (start < 2752083 or >= 56887903)
    # exclude ENSG00000290840

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--genome", default="GRCh38")
    parser.add_argument("--version", default="2024-A")
    parser.add_argument("--cellranger", default="cellranger")
    parser.add_argument("--nthreads", type=int, default=16)
    args = parser.parse_args()
    # ... download, modify, filter, mkref

if __name__ == "__main__":
    main()
```

### cellranger.smk — rule only calls
```python
ref_script = os.path.join(ROOT_DIR, "modules", "cellranger", "bin", "cellranger_ref.py")

rule cellranger_ref:
    output:
        ref_dir = directory(ref_outdir)
    log:
        logdir + "/cellranger_ref/cellranger_ref.log"
    threads: 16
    params:
        python = python,
        script = ref_script,
        cellranger = cellranger_bin,
        genome_name = ref_genome_name,
        version = ref_version,
        fasta = ref_fasta,
        gtf = ref_gtf,
        nthreads = 16,
    run:
        log_path = str(log)
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            os.makedirs(str(output.ref_dir), exist_ok=True)
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            command_script = os.path.join(str(output.ref_dir), f"cellranger_ref_{current_time}.sh")
            cmd = [
                params.python, params.script,
                "--fasta", params.fasta,
                "--gtf", params.gtf,
                "--output", str(output.ref_dir),
                "--genome", params.genome_name,
                "--version", params.version,
                "--cellranger", params.cellranger,
                "--nthreads", str(params.nthreads),
            ]
            with open(command_script, "w") as handle:
                handle.write("#!/usr/bin/env bash\nset -euo pipefail\n")
                handle.write(" ".join(shlex.quote(str(item)) for item in cmd) + "\n")
            shell(f"bash {shlex.quote(command_script)} >> {shlex.quote(log_path)} 2>&1")
        except Exception as exc:
            with open(log_path, "a") as handle:
                handle.write(f"cellranger_ref failed: {exc}\n")
            raise
```

## SIF container with external Cell Ranger binary

Cell Ranger is not available via conda. The SIF bundles it via `%files`:

```
Bootstrap: localimage
From: /path/to/existing-miniconda3.sif

%files
    cellranger.yaml /opt/conda/cellranger.yaml
    /home/luosg/Database/SoftWare/cellranger-10.1.0 /opt/cellranger-10.1.0

%post
    conda env create -f /opt/conda/cellranger.yaml && conda clean -afy
    echo 'export PATH="/opt/cellranger-10.1.0/bin:$PATH"' >> /etc/profile.d/cellranger.sh

%environment
    export PATH="/opt/conda/envs/cellranger/bin:$PATH"
    export PATH="/opt/cellranger-10.1.0/bin:$PATH"
```

Cell Ranger bundles its own STAR, samtools, etc. in `lib/bin/`. The conda
env provides python/anndata/scanpy for custom scripts.

**Pitfall:** The cellranger.yaml must include `bioconda` channel for
samtools, and pin `anndata>=0.10` to avoid pandas 3.x incompatibility.
See `apptainer-sif-build-pitfalls.md` §7.

## FASTA/GTF chromosome name handling

### Human genome (10x Genomics standard)
Input: `>1 dna:chromosome chromosome:GRCh38:1:1:248956422:1 REF`
Output: `>chr1 1` (chr prefix only on first token, original name as second)

Pattern: `>chr_name original_name` — NOT `>chr_name chr_name`

### Non-human genome (Ensembl)
**Do NOT add chr prefix.** Keep original Ensembl chromosome names (1, 2, ..., X, Y, MT).
Cellranger only requires FASTA and GTF chromosome names to MATCH — no chr prefix needed.
This avoids the common bug where FASTA gets chr prefix but GTF doesn't, causing mismatch.

```python
# For non-human: skip modify_fasta_headers entirely
# Just use original FASTA and GTF as-is (after ID stripping)
```

## GTF ID stripping pattern

Input: `gene_id "ENSG00000223972.5";`
Output: `gene_id "ENSG00000223972"; gene_version "5";`

Regex: `r'{id_type} "(ENS(?:MUS)?[GTE]\d+)\.(\d+)";'`

## PAR_Y filtering

chrY entries in PAR region (start < 2752083 or >= 56887903) are excluded.
Exception: ENSG00000290840 is always excluded regardless of position.
