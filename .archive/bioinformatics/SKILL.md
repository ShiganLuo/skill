---
name: bioinformatics
description: Bioinformatics tools and genomics pipelines — RNA-seq quantification, alignment, variant calling, and post-processing scripts.
tags: [genomics, rna-seq, stringtie, quantification, bioinformatics]
triggers:
  - StringTie, featureCounts, HTSeq, or other RNA-seq quantification
  - Gene abundance merging, TPM/FPKM/Coverage calculations
  - GTF/GFF annotation parsing and manipulation
  - Duplicate gene_id handling in quantification output
  - RNA-seq pipeline design or debugging
---

# Bioinformatics Tools & Genomics Pipelines

Recurring patterns for RNA-seq analysis, quantification, and post-processing.

## StringTie Gene Abundance Quantification

### Output Format

StringTie `-e -B -A` produces gene_abundance.tsv with columns:

| Column    | Type  | Description |
|-----------|-------|-------------|
| Gene ID   | str   | Ensembl gene ID (e.g. ENSG00000158623) |
| Gene Name | str   | HGNC symbol |
| Reference | str   | Chromosome |
| Strand    | str   | + or - |
| Start     | int   | 1-based start coordinate |
| End       | int   | End coordinate |
| Coverage  | float | Mean coverage depth |
| FPKM      | float | Fragments Per Kilobase per Million |
| TPM       | float | Transcripts Per Million |

### Duplicate Gene_id Problem

**Root cause**: StringTie clusters transcripts by genomic overlap, NOT by reference gene_id. If a gene has transcripts in non-overlapping loci (e.g. COPG2 with a ~147kb gap), StringTie outputs multiple rows with the same gene_id.

**Why only some samples**: Read coverage across the inter-locus gap varies by sample depth and fragment length. Higher coverage may bridge the gap; low coverage leaves it split.

**Why `-g` parameter won't fix it**: The `-g` (minimum locus gap) parameter controls clustering of read clusters with reads present. If there are zero reads in the gap, increasing `-g` has no effect — there's nothing to bridge.

### Merging Duplicate Gene Rows

TPM, FPKM, and Coverage are normalized metrics and cannot be simply summed. Correct merging rules:

1. **TPM**: Direct sum is mathematically valid. TPM is per-million normalized; same-sample sums preserve correct relative proportions.
2. **FPKM**: Direct sum is valid for the same reason (per-gene normalization).
3. **Coverage**: Must be length-weighted average:
   ```
   Coverage_merged = sum(Cov_i * L_i) / sum(L_i)
   where L_i = End_i - Start_i
   ```
4. **Start/End**: min(Start) / max(End). Must remain **int type** — do not convert to float.
5. **Output order**: Preserve original row order (first occurrence position), do NOT sort by gene_id.

### Pitfalls

- Do NOT sort merged output by gene_id — preserve original file order.
- Start and End must stay int, not float. Use `int()` conversion explicitly.
- Coverage weighted average needs length as weight, not raw coverage sum.
- Adjusting StringTie `-g` parameter is NOT a fix for disconnected loci — downstream merging is the correct approach.
- prepDE.py3 `-g` flag handles transcript-to-gene aggregation but still won't merge disconnected regions in the same way.

See `references/stringtie-gene-merging.md` for the working aggregation script.
