---
name: count-matrix-sample-removal
description: Remove sample columns from featureCounts TSVs safely.
---

featureCounts output TSV layout: line 1 = `# Program:featureCounts ...` command comment, line 2 = header (Geneid, Chr, Start, End, Strand, Length, then one full BAM path per sample), line 3+ = data. Sample columns start at column 7; columns 1-6 are always gene metadata.

## Procedure

1. `sed -n '2p' FILE | tr '\t' '\n' | nl` to list header columns and confirm sample order/positions. Never assume from a previous file.
2. Decide the kept column count from THIS file's sample list (6 + number of samples kept).
3. `cp FILE FILE.bak` before overwriting.
4. Rewrite via awk applying the SAME selection to header and data:
   ```
   awk -F'\t' 'BEGIN{OFS="\t"} NR==1 {print; next} {print $1,...,$K}' FILE.bak > FILE.tmp && mv FILE.tmp FILE
   ```
   (NR==1 skips only the `#` comment; the header at NR==2 must flow through the column-print branch.)
5. Verify in the SAME call: re-print header columns with `nl` (sample list matches intent, no leftovers), `wc -l` unchanged, `tail -1 | cut -f1,7..K` shows a data row with the right column count.

## Pitfalls

- Trimming header and data with different rules silently corrupts the matrix: the classic failure is a `NR<=2 {print; next}` guard that skips BOTH the comment and the header, leaving stale sample columns in the header while data rows are trimmed — downstream readers misalign columns. Verify the header explicitly after every rewrite.
- Never reuse one awk column list across multiple genomes/files with different numbers of removed samples — compute the kept range per file; copying the previous file's `$7,$8` cut removes a wanted sample and loses data irreversibly (recover only via the .bak).
- Line 1's command comment keeps listing the original full sample set — that is historical metadata; do not edit it and do not treat it as evidence the trim failed.
- The user asks for these by sample name (e.g. drop hFibroblasts4-7); resolve columns from the header BAM paths, and confirm which samples remain before reporting done.
