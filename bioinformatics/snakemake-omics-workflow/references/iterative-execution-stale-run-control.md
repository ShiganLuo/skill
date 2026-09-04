# Iterative execution and stale-run control

Use this when a Snakemake workflow is being revised while an old run is active or has left partial outputs.

## Procedure

1. Inspect the live process tree before editing or relaunching. Record the snakefile, configfile, rule/target, deployment mode, and source timestamps used by active workers.
2. Treat outputs from an active or interrupted old run as **untrusted by generation**, even if they are non-empty. A job may have been constructed from an older module and can produce a valid-looking but scientifically wrong BAM.
3. Stop stale workers before launching the corrected DAG, or isolate the corrected run in a new output namespace. Do not allow old and new producers to write the same final paths.
4. Reuse an upstream artifact only after structural validation. For BAM, run `samtools quickcheck`, require the BAM index, confirm the expected sample path, and inspect the producing log/command.
5. Run the corrected branch on real input, not only `--dry-run`. Confirm that command logs implement the published pass structure and that final outputs are non-empty and internally consistent.

## Literature-derived gene-specific alignment checks

- A shell loop over thousands of gene files is not equivalent to an inspectable per-gene Snakemake DAG.
- A per-gene local alignment must use the corresponding single-gene FASTA and a matching local annotation/coordinate contract; do not pass a whole-genome GTF to a gene-local BAM.
- Do not confuse a shared small-RNA STAR index with strict per-gene references.
- Check SE and PE command construction separately; do not invent mate 2 for SE input.
- Explicitly record the ambiguous-read policy. Validate that reads assigned to multiple genes are excluded or duplicated according to configuration, rather than silently inheriting whatever `bedtools`/`samtools` emits.
- A final claim requires real execution plus output checks. Rule compilation, `--list-rules`, and dry-run establish structure only.

## Failure pattern captured

A previous run spent hours executing a pre-existing `star_3pg_align_per_gene` rule that mapped per-gene FASTQs to a shared small-RNA index with one Local pass. It produced files but did not implement the requested strict gene-specific three-pass method. The correct response was to stop that generation, preserve only independently validated canonical upstream BAMs, and rebuild/verify the downstream branch before rerunning.