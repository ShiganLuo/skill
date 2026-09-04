# Strict STAR multipass review lessons

## User-correction gate

When a user challenges a workflow design, inspect the relevant module and subworkflow first, trace the DAG, and state whether the objection is correct before editing. Do not treat a successful `--list-rules` or dry-run as proof that producers and consumers are connected.

## Single-rule multipass contract

If the user requests all passes inside one execution rule, implement the ordered pass commands inside one module `run:` block for both the canonical and sibling branches. The subworkflow must import the single new rule alias and remove stale aliases for the old per-pass rules.

## Producer connectivity

A gene-specific branch consuming `common/3_raw_bam/final_bam/{sample}/{sample}.bam` must import the canonical one-rule STAR producer in the same subworkflow. A path in `input:` is not sufficient if no producer is connected to it.

## Verification checklist

- Check both `star_3pass.smk` and `star_3pass_gene.smk` with `snakemake --list-rules` using a minimal config containing required paths.
- Check `subworkflow/ncRNAseq.smk` contains exactly one canonical producer alias and one gene-specific alias for the selected design.
- Assert old per-pass aliases are absent when the one-rule contract is active.
- Run a focused `/tmp/hermes-verify-*` ad-hoc check and report it as structural evidence only; it does not prove STAR execution or literature equivalence.
