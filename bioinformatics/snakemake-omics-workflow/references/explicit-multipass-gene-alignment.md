# Explicit multi-pass gene-specific alignment

Use this reference when implementing or reviewing the gene-specific re-alignment stage in `star_3pass_gene`.

## Corrected design (mapped/unmapped split)

The gene-specific three-pass mirrors the canonical `three_pass_align.py` structure. All passes use the same per-gene index, but with different modes and inputs:

### Per-gene flow

1. Build a gene-specific STAR index using `pass1` parameters (including `genomeSAindexNbases`).
2. **Pass 1** (E2E, all reads): Align all per-gene FASTQ reads with `EndToEnd`, permissive mismatch (0.2).
   - Output prefix: `{gene_dir}/pass1.`
3. **Pass 2** (E2E + clip, all reads): Re-align the **same** input reads with `EndToEnd` + `clip5pNbases`/`clip3pNbases`. Must enable `--outReadsUnmapped Fastx`.
   - Output prefix: `{gene_dir}/pass2.`
   - Produces: mapped BAM + `Unmapped.out.mate1`/`mate2`
4. Extract pass2 mapped reads as FASTQ (name-sort BAM -> samtools fastq).
5. Gzip pass2 unmapped reads for STAR input.
6. **Pass 3a** (Local, mapped reads): Local alignment of pass2 mapped FASTQ with strict mismatch (0.025).
   - Output prefix: `{gene_dir}/pass3a.`
7. **Pass 3b** (Local, unmapped reads): Local alignment of pass2 unmapped FASTQ with same Local params.
   - Output prefix: `{gene_dir}/pass3b.`
8. Merge pass3a + pass3b -> `merged.bam` per gene.
9. Run Tailer on `merged.bam`.
10. Merge all gene `merged.bam` files into sample-level output BAM.
11. Concatenate per-gene tail CSVs (skip header after first file).

### Key helper functions in gene_specific_align.py

```python
_PASS_PARAMS = [
    ("out_filter_multimap_nmax", "--outFilterMultimapNmax", int),
    ("out_filter_multimap_score_range", "--outFilterMultimapScoreRange", int),
    ("out_filter_mismatch_nover_lmax", "--outFilterMismatchNoverLmax", float),
    ("align_intron_min", "--alignIntronMin", int),
    ("align_mates_gap_max", "--alignMatesGapMax", int),
    ("align_ends_type", "--alignEndsType", str),
]

_PASS2_EXTRA_PARAMS = [
    ("out_filter_mismatch_nover_read_lmax", "--outFilterMismatchNoverReadLmax", float),
    ("clip5p_nbases", "--clip5pNbases", str),
    ("clip3p_nbases", "--clip3pNbases", str),
]

def _build_align_cmd(args, pass_name, index_dir, read_files, out_prefix, emit_unmapped=False):
    cmd = [args.star, "--runThreadN", str(args.threads),
           "--genomeDir", index_dir,
           "--readFilesIn", *read_files,
           "--readFilesCommand", "zcat",
           *_star_pass_options(pass_name, args),
           "--outSAMtype", "BAM", "SortedByCoordinate",
           "--outFileNamePrefix", out_prefix]
    if emit_unmapped:
        cmd += ["--outReadsUnmapped", "Fastx"]
    return cmd
```

### Extracting mapped FASTQ from pass2 BAM

```python
def _extract_fastq_from_bam(samtools, threads, bam_path, fq1, fq2, paired):
    name_sorted = bam_path.rsplit(".bam", 1)[0] + ".name_sorted.bam"
    cmds = [[samtools, "sort", "-n", "-@", str(threads), "-o", name_sorted, bam_path]]
    if paired:
        cmds.append([samtools, "fastq", "-@", str(threads), "-n",
                      "-1", fq1, "-2", fq2, "-0", "/dev/null", "-s", "/dev/null", name_sorted])
    else:
        cmds.append([samtools, "fastq", "-@", str(threads), "-n",
                      "-0", fq1, "-s", "/dev/null", name_sorted])
    return cmds
```

## Config structure

```json
"star_3pass_gene": {
    "mode": "strict",
    "ambiguous": "exclude",
    "flank": 50,
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

Only `pass1` has `genomeSAindexNbases`. Pass2 must include `clip5pNbases`, `clip3pNbases`, and `outFilterMismatchNoverReadLmax`.

## .smk parameter forwarding

The `.smk` must forward pass2-specific keys (clip + readLmax) in addition to common params:

```python
if "outFilterMismatchNoverReadLmax" in p2:
    cmd += ["--pass2-out-filter-mismatch-nover-read-lmax", str(p2["outFilterMismatchNoverReadLmax"])]
if "clip5pNbases" in p2:
    cmd += ["--pass2-clip5p-nbases", str(p2["clip5pNbases"])]
if "clip3pNbases" in p2:
    cmd += ["--pass2-clip3p-nbases", str(p2["clip3pNbases"])]
```

## Verification gates

- `python -c "import ast; ast.parse(open(...).read())"` for helper scripts.
- `--help` output shows `--pass1-*`, `--pass2-*` (including `--pass2-clip5p-nbases`, `--pass2-clip3p-nbases`), `--pass3-*` params.
- Config JSON has `passes.pass1/pass2/pass3` with correct `alignEndsType` values (pass1=EndToEnd, pass2=EndToEnd, pass3=Local).
- Run one real sample and verify:
  - pass2 has >0 reads (if 0, the three-pass structure is broken)
  - pass3b has >0 reads for at least some genes
  - Final BAM has >0 alignments
  - Tailer CSV has more than header

## Pitfalls captured from sessions

- **WRONG: unmapped-read chain**: An earlier implementation chained pass1 unmapped -> pass2 -> pass3, all with Local mode and identical params. Pass1 Local mapped 100% of reads on short per-gene references, making pass2/3 no-ops (all genes showed pass2=0, pass3=0). The correct design re-aligns the same input reads in pass2 with clip, then splits mapped/unmapped for pass3a/3b.
- **Missing clip params in .smk**: The `.smk` must forward `clip5pNbases`, `clip3pNbases`, and `outFilterMismatchNoverReadLmax` from config pass2 to the CLI. Without these, pass2 is identical to pass1 and produces no differentiation.
- **Empty pass BAM pitfall**: STAR emits a non-zero BAM even with 0 reads (header-only ~500 bytes). Use `samtools view -c` to count reads, not `os.path.getsize()`.
- **Gene directory naming uses gene symbol, not Ensembl ID.** The BED from `extract_smallrna.py` is BED6+1. `prepare_gene_inputs.py` maps Ensembl ID to gene symbol for display. Duplicate gene symbols get `.N` suffixes.
- **input_dir consolidation**: `input_dir = os.path.join(outdir, wildcards.sample_id)` (the per-sample output directory itself), NOT a separate `gene_inputs/` subdirectory.
- **STAR Log.out stray artifact**: STAR writes `Log.out` to CWD by default. In normal workflow execution, `gene_specific_align.py` redirects all STAR output to the rule log. A stray `Log.out` means manual STAR invocation outside the workflow.
- **Tailer runs on merged.bam, not pass3 BAM**: Tailer should run on the per-gene `merged.bam` (pass3a + pass3b merged), not on individual pass BAMs. The merged BAM contains all aligned reads for the gene.
