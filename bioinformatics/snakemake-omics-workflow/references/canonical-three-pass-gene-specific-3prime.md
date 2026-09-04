# Canonical three-pass small-RNA alignment and gene-specific 3′ analysis

Use this reference when implementing a paper-derived small/ncRNA alignment branch followed by gene-specific 3′-end analysis.

## Canonical three-pass definition (three_pass_align.py)

Do not infer the meaning of "three-pass" from the name. For the workflow discussed here it is one inseparable chain:

1. **Pass 1**: Map reads to hg38 with EndToEnd, permissive multimapping and no introns.
   ```
   STAR --outFilterMultimapNmax 1000 --alignIntronMin 9999999
        --outFilterMultimapScoreRange 1 --outFilterMismatchNoverLmax 0.2
        --alignEndsType EndToEnd
   ```
2. Extract reads overlapping annotated small-RNA genes using bedtools + samtools.
3. **Pass 2**: Align extracted reads EndToEnd to a canonical small-RNA FASTA containing 50-bp upstream/downstream flanks. Uses clip5p/clip3p to remove non-template tail sequences.
   ```
   STAR --outFilterMultimapNmax 1000 --outFilterMultimapScoreRange 0
        --outFilterMismatchNoverLmax 0.2 --outFilterMismatchNoverReadLmax 0.05
        --clip5pNbases 20 0 --clip3pNbases 0 20
        --alignIntronMin 9999999 --alignMatesGapMax 500
        --alignEndsType EndToEnd --outReadsUnmapped Fastx
   ```
   Output splits into mapped reads and unmapped reads.
4. **Pass 3a**: Re-align pass2 **mapped** reads locally to hg38 with strict mismatch.
   ```
   STAR --outFilterMultimapNmax 1000 --outFilterMultimapScoreRange 0
        --outFilterMismatchNoverLmax 0.025
        --alignIntronMin 9999999 --alignMatesGapMax 500
        --alignEndsType Local
   ```
   Then extract reads that again overlap canonical small-RNA genes with bedtools. This removes canonical small RNA reads with sequencing errors that may misalign with small RNA variant genes.
5. **Pass 3b**: Re-align pass2 **unmapped** reads locally to hg38 with the same Local settings. Captures reads that couldn't map to the canonical database but may have genome-local alignments.
6. Combine pass3a + pass3b into the canonical final BAM.

### Data flow diagram

```
原始 FASTQ
    │
    ▼ pass1: genome E2E (mismatch 0.2)
    │
    ├── bedtools intersect → small RNA reads
    │
    ▼ pass2: smallRNA ref E2E + clip (mismatch 0.2, readLmax 0.05)
    │
    ├── mapped reads ──→ pass3a: genome Local (mismatch 0.025)
    │                      │
    │                      └── bedtools intersect → canonical small RNA reads
    │
    └── unmapped reads ─→ pass3b: genome Local (mismatch 0.025)
                           │
                           └── non-canonical reads
    │
    ▼
  merge pass3a + pass3b → 最终 BAM
```

## Gene-specific stage (three-pass per-gene re-alignment)

The canonical final BAM is the explicit upstream producer. The gene-specific branch must import/call that producer; a configured path alone does not complete the DAG.

The gene-specific three-pass mirrors the canonical three-pass structure, but uses the per-gene reference index for all three passes instead of switching between genome and small-RNA indexes:

1. **Pass 1** (E2E, all reads): Align all per-gene FASTQ reads to the per-gene index with `EndToEnd` and permissive mismatch (0.2).
2. **Pass 2** (E2E + clip, all reads): Re-align the **same** input reads (not pass1 unmapped) to the same per-gene index with `EndToEnd` + `clip5pNbases`/`clip3pNbases`. The clip removes non-template tail sequences from read ends. Output is split into mapped and unmapped FASTQ groups via `--outReadsUnmapped Fastx`.
3. **Pass 3a** (Local, mapped reads): Local alignment of pass2 **mapped** reads with strict mismatch (0.025).
4. **Pass 3b** (Local, unmapped reads): Local alignment of pass2 **unmapped** reads with the same strict Local parameters.
5. **Merge** pass3a + pass3b BAMs per gene, then run Tailer on the merged gene BAM.

### CRITICAL: Do NOT use unmapped-read chain

The earlier implementation chained pass1 unmapped -> pass2 -> pass3, which is **wrong**. That design:
- Made pass1/pass2/pass3 all use Local mode with identical parameters (no differentiation)
- Pass1 Local was too permissive on short per-gene references, mapping 100% of reads
- Pass2/3 received 0 unmapped reads, making them no-ops
- All genes showed pass2=0, pass3=0 reads

The correct design re-aligns the **same** input reads in pass2 (with clip), not the unmapped subset. Pass2's clip is the key differentiator -- it strips non-template tails so reads that failed clean E2E can now map. The mapped/unmapped split after pass2 creates the two branches for pass3a/3b.

### Parameter summary

| Pass | alignEndsType | Input | Key params | Output |
|------|--------------|-------|------------|--------|
| pass1 | EndToEnd | original FASTQ | mismatch 0.2, scoreRange 1 | BAM |
| pass2 | EndToEnd | original FASTQ (same) | clip5p "20 0", clip3p "0 20", readLmax 0.05, --outReadsUnmapped Fastx | BAM + unmapped FASTQ |
| pass3a | Local | pass2 mapped FASTQ | mismatch 0.025 | BAM |
| pass3b | Local | pass2 unmapped FASTQ | mismatch 0.025 | BAM |

Pass2 must enable `--outReadsUnmapped Fastx` to produce the mapped/unmapped split. Pass3a/3b do not need `--outReadsUnmapped`.

### Extracting mapped FASTQ from pass2 BAM

Pass2 mapped reads are extracted from the BAM (name-sort + samtools fastq):
```python
# name-sort pass2 BAM, then samtools fastq to extract mapped reads
samtools sort -n -o pass2.name_sorted.bam pass2.Aligned.sortedByCoord.out.bam
samtools fastq -n -1 pass2_mapped_1.fq.gz -2 pass2_mapped_2.fq.gz -0 /dev/null -s /dev/null pass2.name_sorted.bam
```

Pass2 unmapped reads come from STAR's `Unmapped.out.mate1`/`mate2` files (gzip them for STAR input).

### Per-gene flow

Then for each gene:

1. Perform one BAM-vs-annotation overlap operation.
2. Normalize read names before grouping when BED conversion adds `/1` or `/2` but BAM query names do not.
3. Parse appended BED fields from the end (`gene_id` is the fourth field of BED6/7, commonly `fields[-4]` after `bedtools intersect -bed -wa -wb`), not from a fixed BAM-field offset. The BED file produced by `extract_smallrna.py` is BED6+1: `chrom start end gene_id score strand gene_name`. The `prepare_gene_inputs.py` `load_bed()` function reads field 4 (Ensembl ID) as the internal key and field 7 (gene_name) as the display name. When gene_name is missing (BED6 only), it falls back to the gene_id.
4. Apply an explicit ambiguous-read policy.
5. Group reads by assigned gene and restore gene-specific FASTQ.
6. **Gene directory naming uses gene symbol (display name), not Ensembl ID.** Duplicate gene symbols (e.g. Y_RNA x758, U6 x37) get `.N` suffixes (Y_RNA.1, Y_RNA.2, ...). The manifest (`genes.tsv`) carries both `gene_id` (display name) and `ensembl_id` (Ensembl ID) columns for traceability.
7. Extract only that gene's genomic sequence with the required flank and build a gene-specific reference/index.
8. Run the three-pass structure described above (pass1 E2E -> pass2 E2E+clip -> pass3a/3b Local -> merge).
9. Run Tailer on the merged gene BAM.
10. Merge all gene BAMs into sample BAM, concatenate tail CSVs.

### Empty pass BAM pitfall

STAR always emits a BAM file (even with 0 reads -- the header alone is ~500 bytes, non-zero). The old `os.path.getsize() == 0` check passes on these empty BAMs. Use `samtools view -c` to count actual reads. If a pass BAM has 0 reads, skip it in the merge. If all passes have 0 reads for a gene, skip the gene entirely.

## Coordinate and strand contract

- FASTA contig name, BAM `@SQ/SN`, and gene-local GTF `seqid` must be identical.
- If the reference is strand-normalized with `bedtools getfasta -s`, the mature gene interval is inside the flanked contig, not the whole contig. For a 50-bp flank, annotate the gene starting at local coordinate 51.
- Tailer global mode applies an Illumina strand convention internally; validate GTF strand and `-read` using a real BAM. A successful command that writes only a CSV header is not valid evidence.
- After BAM->FASTQ->STAR, mate semantics may differ from the original library. Inspect flags and validate whether Tailer must use `-read 1` or `-read 2` on the regenerated alignment.

## Mandatory verification

Do not stop at `--list-rules` or dry-run. Run at least one real sample and require all of:

- helper syntax passes;
- `samtools quickcheck` succeeds;
- final gene-specific BAM has >0 alignments;
- Tailer CSV has more than its header;
- **pass2 has >0 reads** (if pass2=0, the three-pass structure is broken -- see CRITICAL note above);
- **pass3b has >0 reads for at least some genes** (confirms unmapped branch is working);
- inspect several rows for gene IDs, end positions, tail lengths, and tail sequences;
- inspect logs for per-gene STAR and Tailer outputs.

## Config structure for per-pass parameters

The `star_3pass_gene` config section uses a `passes` dict:

```json
"star_3pass_gene": {
    "passes": {
        "pass1": {
            "genomeSAindexNbases": 3,
            "alignEndsType": "EndToEnd",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 1,
            "outFilterMismatchNoverLmax": 0.2,
            "alignIntronMin": 9999999
        },
        "pass2": {
            "alignEndsType": "EndToEnd",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 0,
            "outFilterMismatchNoverLmax": 0.2,
            "outFilterMismatchNoverReadLmax": 0.05,
            "clip5pNbases": "20 0",
            "clip3pNbases": "0 20",
            "alignIntronMin": 9999999,
            "alignMatesGapMax": 500
        },
        "pass3": {
            "alignEndsType": "Local",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 0,
            "outFilterMismatchNoverLmax": 0.025,
            "alignIntronMin": 9999999,
            "alignMatesGapMax": 500
        }
    }
}
```

Only `pass1` contains `genomeSAindexNbases` (used for `STAR --runMode genomeGenerate`). Pass2 must include `clip5pNbases`, `clip3pNbases`, and `outFilterMismatchNoverReadLmax`. The `.smk` must forward these pass2-specific keys.

### .smk pass2 parameter forwarding

The `.smk` must forward pass2 clip and readLmax params in addition to the common params:

```python
if "outFilterMismatchNoverReadLmax" in p2:
    cmd += ["--pass2-out-filter-mismatch-nover-read-lmax", str(p2["outFilterMismatchNoverReadLmax"])]
if "clip5pNbases" in p2:
    cmd += ["--pass2-clip5p-nbases", str(p2["clip5pNbases"])]
if "clip3pNbases" in p2:
    cmd += ["--pass2-clip3p-nbases", str(p2["clip3pNbases"])]
```

## Interaction rule

When the user challenges the workflow semantics, first inspect the current code and determine whether the objection is correct. State that judgment and its evidence before editing. Do not treat a parse-only PASS as proof that the scientific DAG is connected or correct.

### input_dir layout (post-refactor)

The `star_3pass_gene.smk` rule sets `input_dir = os.path.join(outdir, wildcards.sample_id)` - the same directory as `output.bam` / `output.tail`. This means `prepare_gene_inputs.py` writes `genes.tsv`, `read_gene_overlaps.tsv`, and per-gene subdirectories directly into the sample directory. There is no separate `gene_inputs/` subdirectory layer.

### STAR Log.out stray file

STAR writes `Log.out` to the current working directory by default, then tries to move it into `--genomeDir`. If the move fails, STAR prints a WARNING and leaves `Log.out` in the CWD. In normal Snakemake execution this is captured by the rule's log redirect, but manual STAR invocations from the workflow root directory will leave a stray `Log.out` there. Safe to delete.

## History note

An earlier version implemented the gene-specific three-pass as an unmapped-read chain (pass1 unmapped -> pass2 -> pass3), with all passes using Local mode and identical parameters. This was **wrong** -- pass1 Local mapped 100% of reads on short per-gene references, making pass2/3 no-ops. The correct design mirrors the canonical three-pass: pass1 E2E all reads, pass2 E2E+clip all reads (split mapped/unmapped), pass3a/3b Local on mapped/unmapped respectively.
