# star_3pass_gene: Per-Gene Three-Pass Local Alignment

Design (Ma et al 2024): per-gene FASTQ re-aligned to single-gene genomic
sequences in three Local passes, each feeding unmapped reads to the next.

## Three-pass parameter table

| Pass | alignEndsType | outFilterMismatchNoverLmax | clip | Purpose |
|------|--------------|----------|------|---------|
| pass1 | Local | 0.2 | none | Capture most reads (lenient) |
| pass2 | Local | 0.2 | clip5pNbases + clip3pNbases | Trim non-template tails, realign read body |
| pass3 | Local | 0.025 | none | High-precision final alignment |

Config structure (`Params.star_3pass_gene.passes`):
```json
{
  "pass1": {"genomeSAindexNbases": 3, "alignEndsType": "Local", ...},
  "pass2": {"alignEndsType": "Local", "clip5pNbases": "20 0", "clip3pNbases": "0 20", ...},
  "pass3": {"alignEndsType": "Local", ...}
}
```
Only pass1 has `genomeSAindexNbases` (used for per-gene STAR genomeGenerate).

## Pass2 clip rationale

Small-RNA reads often carry 3' non-template additions (poly-A, poly-U, CCA).
Pass1 Local alignment may fail to map these because the tail causes mismatches
at the read end. Pass2 clips both ends (default `clip5pNbases="20 0"`,
`clip3pNbases="0 20"` for PE), letting the read body align cleanly. Pass3 then
applies strict mismatch (0.025) to the remaining unmapped reads.

## Known bug (as of 2026-08-06)

`gene_specific_align.py` CLI defines `--pass2-clip5p-nbases` and
`--pass2-clip3p-nbases` (defaults "20 0" / "0 20"), but `star_3pass_gene.smk`
**never passes them** from config to the command line. Config's `pass2` section
has no `clip5pNbases`/`clip3pNbases` keys. Result: pass2 parameters are identical
to pass1, all reads map in pass1, unmapped is empty, pass2 and pass3 always
produce 0 reads -- making the three-pass design a no-op.

### Fix

1. `star_3pass_gene.smk`: add clip param forwarding:
```python
if "clip5pNbases" in p2:
    cmd += ["--pass2-clip5p-nbases", str(p2["clip5pNbases"])]
if "clip3pNbases" in p2:
    cmd += ["--pass2-clip3p-nbases", str(p2["clip3pNbases"])]
if "outFilterMismatchNoverReadLmax" in p2:
    cmd += ["--pass2-out-filter-mismatch-nover-read-lmax", str(p2["outFilterMismatchNoverReadLmax"])]
```
2. `config/ncRNAseq.json`: add to `Params.star_3pass_gene.passes.pass2`:
```json
"clip5pNbases": "20 0",
"clip3pNbases": "0 20",
"outFilterMismatchNoverReadLmax": 0.05
```

## Tailer BAM selection

After three passes, `gene_specific_align.py` walks backwards (pass3->pass1) to
find the last pass with >0 reads (checked via `samtools view -c`). That BAM is
used for Tailer. When all reads map in pass1 (due to the clip bug above), pass1
BAM is always selected.

## gene_inputs directory

`prepare_gene_inputs.py` output (genes.tsv, read_gene_overlaps.tsv, per-gene
subdirs) goes directly into `outdir/<sample_id>/` -- NOT a separate
`gene_inputs/` subdirectory. The `input_dir` variable in the .smk equals
`os.path.join(outdir, wildcards.sample_id)`.

## File locations

- `.smk`: `modules/star/star_3pass/star_3pass_gene.smk`
- Main script: `modules/star/star_3pass/bin/gene_specific_align.py`
- Prepare script: `modules/star/star_3pass/bin/prepare_gene_inputs.py`
- Canonical 3-pass: `modules/star/star_3pass/bin/three_pass_align.py`
- Config: `config/ncRNAseq.json` -> `Params.star_3pass_gene`
- Subworkflow: `subworkflow/ncRNAseq.smk` (aligner == "star_3pass_gene")

## Comparison: canonical star_3pass vs gene-specific

| Aspect | canonical (three_pass_align.py) | gene-specific (gene_specific_align.py) |
|--------|------|------|
| pass1 index | whole genome | per-gene reference |
| pass2 index | smallRNA reference | per-gene reference (same) |
| pass3 index | whole genome | per-gene reference (same) |
| pass2 mode | EndToEnd + clip | Local + clip (intended) |
| Input reads | raw FASTQ | per-gene FASTQ from pass1 BAM |
| Output | pass3a + pass3b merged BAM | per-gene BAMs merged |
