# Monolithic Tool Wrapper Pattern

When wrapping a self-contained pipeline tool (like mimseq, Cell Ranger, or nf-core
pipelines run as a single command), the tool processes ALL samples at once via a
sample sheet rather than per-sample Snakemake rules.

## When to use

- Tool takes a sample sheet (TSV/CSV) and processes everything internally
- Internal steps are tightly coupled and cannot be independently re-run
- Tool manages its own parallelism internally
- Breaking into per-sample rules would require reimplementing the tool's logic

## Module pattern

```python
rule mimseq_run:
    input:
        sample_data = config.get("sample_data", ""),
        trnas = config.get("genome", {}).get("trnas", ""),
    output:
        outdir = directory(outdir + "/mimseq"),
    log:
        logdir + "/mimseq/mimseq_run.log"
    conda:
        "mimseq.yaml"
    params:
        script = "mimseq",
        species = config.get("Params", {}).get("mimseq", {}).get("species", ""),
        # ... all tool flags as params
    run:
        try:
            log_path = str(log)
            open(log_path, "w").close()
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            mimseq_outdir = f"{outdir}/mimseq"
            script_path = os.path.join(outdir, f"mimseq_run_{current_time}.sh")

            cmd = [params.script, "-s", params.species, ...]
            # Sample data is positional arg (last)
            cmd += [input.sample_data]

            with open(script_path, "w") as f:
                f.write("#!/bin/bash\nset -e\n")
                f.write(" ".join(cmd) + "\n")
            shell(f"bash {script_path} >> {log_path} 2>&1")
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"mimseq_run failed: {e}\n")
            raise
```

## Key differences from per-sample rules

1. **No `{sample_id}` wildcard** — tool handles all samples internally
2. **`directory()` output** — entire output directory is the artifact
3. **Sample sheet in config** — `config.get("sample_data", "")` not `samples` list
4. **Single rule covers entire pipeline** — no need to split into align → quantify → DESeq2
5. **run.py integration** — `outfiles` points to the output directory, not per-sample files

## run.py integration

```python
def runToolName(datajson, samples_info_dict, indir, outdir):
    datajson["ROOT_DIR"] = os.path.dirname(__file__)
    datajson["indir"] = indir
    datajson["outdir"] = outdir
    datajson["logdir"] = os.path.join(outdir, "log")
    datajson["samples"] = list(samples_info_dict.keys())
    # Single outfile = output directory
    datajson["outfiles"] = [f"{outdir}/tool_output"]
    # Write raw.json
    ...
```

## Example: mimseq (mim-tRNAseq)

mimseq takes a sample data TSV (fastq_path\tcondition) and runs:
tRNA clustering → GSNAP alignment → deconvolution → coverage → modification
quantification → CCA analysis → DESeq2 — all in one command.

Wrapping as a single `mimseq_run` rule is correct because:
- Internal steps share in-memory data structures (cluster_dict, tRNA_dict)
- GSNAP indices are built and used within the same process
- DESeq2 needs all sample coverage data together
