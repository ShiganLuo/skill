# User correction and multi-pass rule-shape protocol

When modifying a literature-derived Snakemake alignment workflow:

1. If the user challenges the implementation, inspect the existing canonical branch first and state whether the challenge is valid before editing.
2. Reuse an already implemented canonical multi-pass branch instead of recreating its semantics from memory.
3. If the user requests that all passes be compressed into one rule, implement one standard `run:` rule containing the complete ordered pass sequence and expose one subworkflow alias. Do not split passes into separate Snakemake rules merely for visibility.
4. Keep strict gene-specific post-processing distinct from the canonical upstream branch. Start from the canonical final BAM when requested.
5. Verify both rule registration and the requested rule shape: `--list-rules`, source assertions for one execution rule, pass ordering, pass-specific parameters, and dry-run where inputs can be represented safely.
6. Report ad-hoc structural verification as such; it does not prove STAR execution or literature equivalence.

This preference supersedes an earlier exploratory design that exposed each gene-local pass as a separate Snakemake rule. That design was rejected by the user because the requested abstraction is one rule per complete three-pass execution for both `star_3pass` and `star_3pass_gene`.
