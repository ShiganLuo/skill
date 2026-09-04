# User-corrected alignment workflow discipline

When the user challenges an implementation, first determine whether the challenge is correct by tracing existing code, producer/consumer relationships, and scientific semantics. State the verdict and evidence before editing; do not reflexively rewrite code.

For literature-derived alignment workflows:

1. Identify the canonical implementation before changing a sibling branch. If `star_3pass` already implements the published three-pass method, reuse it; do not recreate its passes from memory in `star_3pass_gene`.
2. Keep the producer graph explicit. A branch consuming `final_bam` must import/use the rule that produces it; an expected path is not an implicit producer.
3. If project convention requires an inseparable multi-pass chain to be one execution rule, put all ordered pass commands inside one module `run:` and expose one `use rule` alias from the subworkflow. Do not split passes into separate Snakemake rules merely for visibility.
4. Distinguish granularity: gene-level temporary BAMs may be created inside a sample rule, while the final `star_3pass_gene` output is one merged gene-specific BAM per sample. If that BAM is the biological input to Tailer, declare the Tailer CSV as an output of the same rule and run Tailer after the merge.
5. Reconcile coordinates before downstream wiring. Gene-local BAMs require a matching gene-local/combined annotation; never pass a whole-genome GTF to a gene-local BAM by assumption.
6. Verify the complete subworkflow DAG, not only module `--list-rules`: check canonical upstream producers, downstream consumers, final outputs, and embedded analysis outputs.

This reference records a user-corrected workflow pattern: challenge first, verdict second, edit third; one-rule multi-pass execution; explicit upstream producer; final sample BAM plus embedded Tailer output.