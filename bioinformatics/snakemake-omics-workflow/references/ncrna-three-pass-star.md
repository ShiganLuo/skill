# ncRNAseq: Three-Pass STAR Alignment for Small RNA

Reference for small RNA-seq analysis using three-pass STAR alignment.

## Two aligner routes

### 1. star_3pass (canonical small RNA)

```
genome module:
    GTF -> extract_smallrna -> BED + FASTA(±50bp)
    FASTA -> star_index (sjdbOverhang=0) -> smallRNA STAR index

Trim Galore
    -> STAR pass1 (genome, relaxed, multimap 1000)
        -> bedtools intersect + samtools sort -n + fastq -> SE FASTQ
            -> STAR pass2 (smallRNA FASTA, EndToEnd, clip 20bp)
                -> samtools view -F 4 -> mapped SE FASTQ -> STAR pass3a (genome, strict)
                    -> bedtools intersect -> canonical BAM
                -> samtools view -f 4 -> unmapped SE FASTQ -> STAR pass3b (genome, strict)
                    -> samtools merge (canonical + noncanonical) -> featureCounts (SE mode)
```

### 2. star_3pass_gene (per-gene re-alignment, Ma et al 2024)

```
Trim Galore + Subsample + Hard clip
    -> STAR pass1 (genome, EndToEnd, 5' hard clip 10nt via clip5pNbases "10 0")
        -> bedtools intersect (per gene) + samtools fastq -> per-gene FASTQ
            -> STAR pass2 (smallRNA FASTA index, Local alignment, per-gene)
                -> samtools merge (all per-gene BAMs) -> sample BAM
                    -> featureCounts + Tailer (global mode)
```

Key differences from star_3pass:
1. Pass 1: EndToEnd (not relaxed Local), 5' hard clip 10 nt for post-transcriptional modification tolerance
2. No pass2/pass3a/pass3b split: reads grouped by gene, re-aligned individually to smallRNA FASTA index using Local alignment
3. Per-gene FASTQ extraction: bedtools intersect per gene interval, samtools fastq per gene
4. Merge: all per-gene BAMs merged into sample BAM (not canonical+noncanonical)

## star_3pass.smk rules

| Rule | Purpose |
|------|---------|
| `star_3p_extract_smallrna` | pass1 BAM -> bedtools intersect -> SE FASTQ |
| `star_3p_pass2_mapped_to_fq` | pass2 BAM -> mapped SE FASTQ for pass3a |
| `star_3p_pass2_unmapped_to_fq` | pass2 BAM -> unmapped SE FASTQ for pass3b |
| `star_3p_pass3a_extract` | pass3a BAM -> bedtools intersect -> canonical BAM |
| `star_3p_merge` | canonical + noncanonical -> merged BAM |

## star_3pass_gene.smk rules

| Rule | Purpose |
|------|---------|
| `star_3pg_extract_per_gene` | pass1 BAM -> bedtools intersect per gene -> per-gene FASTQ.gz |
| `star_3pg_align_per_gene` | per-gene FASTQ -> STAR Local alignment to smallRNA index -> per-gene BAM |
| `star_3pg_merge` | all per-gene BAMs -> samtools merge -> sample BAM + index |

Module file: `modules/star/star_3pass/star_3pass_gene.smk` (shares `star_3pass.yaml`)

## Config pattern

```python
# CRITICAL: define derived paths BEFORE config dicts (pitfall #61)
smallrna_bed = f"{outdir}/genome/smallrna/smallrna_genes.bed"
smallrna_fasta = f"{outdir}/genome/smallrna/smallrna_genes_flank.fa"
smallrna_star_index = f"{outdir}/genome/smallrna/index"

# Auto-build genome STAR index when star_index_dir is null
# MUST be BEFORE pass configs that capture star_index_dir
if not star_index_dir:
    star_genome_idx_config = {
        "ROOT_DIR": ROOT_DIR, "outdir": f"{outdir}/genome", "logdir": logdir,
        "Procedure": {"STAR": STAR}, "Params": {"STAR": {}},
        "genome": {"fasta": genome_fasta, "gtf": config.get("genome", {}).get("gtf")}
    }
    module star_genome_idx:
        snakefile: "../modules/star/star.smk"
        config: star_genome_idx_config
    use rule star_index from star_genome_idx as ncRNAseq_star_index_genome
    star_index_dir = f"{outdir}/genome/index"

# pass2/3a/3b all SE
star_pass2_config = {
    "paired_samples": [],
    "single_samples": paired_samples + single_samples,
    "genome": {"fasta": smallrna_fasta, "index_dir": smallrna_star_index}
}
# featureCounts SE mode
fc_paired = [] if aligner == "star_3pass" else paired_samples
fc_single = paired_samples + single_samples if aligner == "star_3pass" else single_samples
```

## star_3pass_gene config

```json
"star_3pass_gene": {
    "pass1": {
        "outFilterMultimapNmax": 1000,
        "alignIntronMin": 9999999,
        "outFilterMultimapScoreRange": 0,
        "outFilterMismatchNoverLmax": 0.2,
        "alignEndsType": "EndToEnd",
        "clip5pNbases": "10 0"
    }
}
```

## smallrna_types for paper-specified sncRNAs

Paper specifies: snRNA, misc_RNA, rRNA, rRNA_pseudogene, snoRNA, scaRNA, ribozyme, TERC
(NOT miRNA, scRNA, vaultRNA). Config: `Params.ncRNAseq.smallrna_types`.

## align_bam_dir pattern for downstream modules

featureCounts and Tailer indir must be resolved per-aligner:
```python
if aligner == "star_3pass":
    align_bam_dir = f"{outdir}/common/3_raw_bam/final_bam"
elif aligner == "star_3pass_gene":
    align_bam_dir = f"{outdir}/common/3_raw_bam/per_gene"
else:
    align_bam_dir = f"{outdir}/common/3_raw_bam"
```

## Pitfalls

1. **sjdbOverhang=0** when no GTF - STAR fatal error otherwise
2. **Python dict value capture** - define derived paths BEFORE config dicts
3. **star_index output** - `directory(outdir)` not `directory(outdir + "/index")`
4. **Input paths** - use `.bam` not `.Aligned.sortedByCoord.out.bam`
5. **include path** - `../../common/common.smk` (two levels up)
6. **BAM->FASTQ rules needed** - STAR `outReadsUnmapped` only gives unmapped
7. **featureCounts SE mode** - merged BAM is single-end
8. **samtools sort -n** before `samtools fastq`
9. **Genome index MissingInputException** - `use rule star_align` only imports `star_align`, not `star_index`. Must also import `star_index` when `star_index_dir` is null. See skill pitfall #48.
10. **All passes share one genome index** - create ONE `star_genome_idx` module, not one per pass. Pass2 uses separate smallRNA index.
11. **star_3pass_config missing comma (pre-existing bug, fixed)** - ncRNAseq.smk line 412 had `"pass2_outdir": star_pass2_config["outdir"]` without trailing comma before `"logdir"`. Causes SyntaxError at parse time. Always check for missing commas in multi-line config dicts.
12. **align_bam_dir pattern** - featureCounts and Tailer indir must be resolved per-aligner (see above), not hardcoded to `common/3_raw_bam`.
13. **star.smk clip5pNbases limitation** - The `star_align` rule in `star.smk` has a fixed parameter list and does NOT natively pass `clip5pNbases` to STAR. For `star_3pass_gene` pass1 to apply the 5' hard clip, verify the STAR log output shows `clip5pNbases` was applied, or extend `star.smk` to pass it.
