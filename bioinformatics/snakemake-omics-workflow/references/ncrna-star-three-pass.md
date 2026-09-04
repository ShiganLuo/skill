# ncRNA STAR three-pass gene-mode review

Use this reference when implementing or reviewing `ncRNAseq.smk` with `star_3pass` or `star_3pass_gene`.

## Protocol-to-DAG mapping

1. `jla-demultiplexer`: remove 3' adapter/randomer and PCR duplicates.
2. Cutadapt/Trim Galore: remove residual Illumina adapter.
3. Genome end-to-end alignment: execute the documented three passes, including the 5' hard clip (`clip5pNbases=10 0` when specified). Later passes must consume the junction evidence produced by earlier passes; one STAR call is not a three-pass implementation.
4. Extract reads overlapping the selected small-RNA annotation with bedtools/samtools.
5. Perform local re-alignment efficiently. Do not build a whole-genome/single-gene STAR index and launch STAR once per gene in a serial loop. Prefer one batched local alignment followed by annotation-region filtering, or explicitly parallelized gene jobs only when strict per-gene reference isolation and coordinate restoration are implemented.
6. Preserve coordinate semantics for downstream tools. Tailer global mode (`Tailer -a <gtf>`) requires genome-coordinate BAMs. A BAM aligned to a synthetic small-RNA/gene FASTA cannot be passed to global Tailer without a verified coordinate/liftover step.
7. Tailer threshold and post-processing are distinct. A threshold controlling distance from the mature end does not automatically implement the protocol's truncation filter or templated/untemplated nucleotide classification. Add a separately verified post-processing module only after inspecting the actual Tailer output columns.

## Review checklist

- Is the three-pass claim backed by three actual STAR command stages?
- Is `clip5pNbases` passed to the end-to-end stages and exposed through the config chain?
- Are junction files carried from pass to pass?
- Is there any `for gene in ...` loop that starts STAR or rebuilds an index?
- Does the final BAM use genome contigs/coordinates before Tailer global mode?
- Are PE and SE input paths both implemented upstream and in the alignment module?
- Does `run.py` preserve the new parameter namespace when it creates `raw.json`?
- Verify with a PE dry-run and a separate SE dry-run; if SE is blocked by an upstream module, report that blocker instead of claiming SE support.

## Evidence boundary

A dry-run validates rule parsing and dependency paths. It does not validate STAR's biological behavior, BAM coordinate correctness, Tailer's output schema, or post-processing thresholds. Those require a small real fixture or tool-level execution.