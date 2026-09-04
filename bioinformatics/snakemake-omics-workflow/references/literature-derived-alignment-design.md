# Literature-derived alignment design

Use this checklist when extending an existing Omics alignment workflow from a paper.

1. Identify the canonical branch/rules already implementing the named method. Trace the full DAG and outputs before editing a sibling branch.
2. Treat published pass structure as immutable method semantics. Add only the requested adaptation; do not recreate the same passes from memory.
3. Separate four contracts: published method identity, read assignment/grouping, reference and coordinate system, and performance optimization.
4. Start gene-specific post-processing from the existing canonical final BAM if the user specifies that stage. Perform one global overlap/assignment operation, then group reads; do not rescan the whole BAM once per gene.
5. For strict per-gene re-alignment, create one reference and one alignment unit per assigned gene, and define ambiguous-read handling explicitly. Do not claim equivalence for a merged-reference batch implementation unless it is validated against strict alignment.
6. Check downstream coordinate semantics. A gene-local contig BAM cannot be passed to a whole-genome GTF without a matching gene-reference GTF or a verified coordinate lift-back.
7. Keep unrequested optimizations disabled and explicit in configuration. A Snakemake dry-run demonstrates DAG construction only, not scientific or literature equivalence.

For explicit strict gene-specific multi-pass design and verification, also use `references/explicit-multipass-gene-alignment.md`.

Session-derived pitfall: when `star_3pass` already owns the three-pass implementation, `star_3pass_gene` must not rebuild those canonical passes. It should consume the canonical `final_bam` and implement only the paper's gene-specific downstream stage — which itself contains three per-gene local alignment passes (pass1 -> pass2 from unmapped -> pass3 from unmapped), each with independent STAR parameters under `passes.pass1/pass2/pass3`.
