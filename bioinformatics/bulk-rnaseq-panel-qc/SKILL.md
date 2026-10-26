---
name: bulk-rnaseq-panel-qc
description: Use when an RNA-seq panel mixes library types or libraries.
tags: [rna-seq, qc, featurecounts, sample-manifest, gsva, plotting]
triggers:
  - sample names carry _x / _y suffixes in a merged count matrix
  - heatmap re-plot requested with samples excluded or labels renamed
  - total-RNA and polyA libraries mixed in one analysis panel
  - same sample appears in both paired-end and single-end count tables
---

# Bulk RNA-seq Sample-Panel Hygiene (Library Type, Duplicate Counting, Re-plotting)

## 1. `_x`/`_y` suffixes = the same sample counted twice, not two replicates
When a merged featureCounts table shows `sample_x` / `sample_y`, the sample exists
in BOTH the paired-end and single-end count tables; `pd.merge` auto-suffixed the
duplicate column names (`_x` = PE table, `_y` = SE table). Fix at the source:

1. Confirm against the sample manifest which samples are truly paired-end.
2. Back up each table as `.bak`.
3. In the SINGLE table, drop the PE samples' columns; preserve the original
   `# Program ...` header line (read it from the backup, write it back first —
   `pd.read_csv(comment='#')` drops it silently otherwise).
4. In the MERGED table, rename `<s>_x` -> `<s>` and drop `<s>_y`.
5. Re-run normalization and downstream (GSVA/DE) from the corrected tables.

Never just relabel the heatmap: cross-sample z-scores are computed on the
duplicated panel and stay wrong until the pipeline re-runs.

## 2. Keep library types in separate panels
Total-RNA and polyA libraries differ systematically (gene-body coverage,
long-gene recovery, rRNA content). Mixing them shifts cross-sample
standardization for every sample. Filter with the FULL original sample name
(`hFibroblasts1` also matches the prefix of `hFibroblasts4` — filter on exact
names, not substrings).

## 3. Re-plotting rule: read-only scripts, separate output dir
To re-plot with renamed labels or excluded samples, write a standalone script
that READS the existing scores TSV and writes to its own output directory.
Original scores/expression matrices are never modified. Keep the colorbar label
and score semantics identical unless the user asks otherwise.

## Pitfalls
- `pd.read_csv(..., comment='#')` on a featureCounts table silently drops the
  `# Program` header; when rewriting such a table, re-emit that line first.
- Sample-name filtering by substring/prefix collides with numbered siblings
  (`Fibroblasts1` vs `Fibroblasts4`) — filter on exact column names.
- The single/merged count tables live under `counts/featureCounts/<genome>/`;
  the PE/SE split mirrors the manifest's `genome_paired_samples` vs
  `genome_single_samples`.
