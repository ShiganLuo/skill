# Fiberseq Pipeline Architecture Issue: Missing Alignment Step

> **RESOLVED (Sept 2026):** Step 0 (pbmm2 alignment) added. See `references/fiberseq-workflow.md` for current architecture.

## Problem

The Fiberseq subworkflow (`workflow/Omics/subworkflow/Fiberseq.smk`) processes PacBio Revio CCS BAMs through 5 steps:

1. `ft add-nucleosomes` — annotate nucleosomes per-read
2. `ft fire` — call FIRE (footprints of regulatory elements) per-read  
3. `ft extract --all` — extract to BED format
4. `ft call-peaks` — call FIRE peaks (needs genomic coordinates)
5. `ft qc` — collect QC metrics (needs genomic coordinates)

**Critical gap:** Steps 1-3 work on unmapped BAMs (per-read annotation). Steps 4-5 require aligned reads with genomic coordinates. There is NO alignment step between raw CCS BAM and the coordinate-dependent steps.

## Root Cause

PacBio Revio CCS output (ccs → trim → jasmine → lima) produces unmapped BAMs:
- No @SQ header lines (0 reference sequences)
- All reads have flag=4 (unmapped)
- RNAME=`*` (no chromosome assignment)
- `samtools index` produces trivial 16-byte .bai

## Symptoms

- `ft call-peaks` outputs BED with only header line (no data rows)
- Log shows: "BAM has no aligned reads — skipping ft call-peaks"
- `.bai` files are only 16 bytes

## Fix Required

Add alignment step between raw CCS and nucleosome calling:

```bash
pbmm2 align reference.fa input.unmapped.bam output.sorted.bam --sort -j 16
```

Or between fire and call-peaks (if per-read annotation on unmapped BAM is acceptable).

## Reference Genome Issues

Config `genome.fasta` must:
1. Exist on the filesystem (`ls -la $path`)
2. Match the species (check BAM @RG SM field)
3. Be indexed or indexable by pbmm2

Example: Mouse reference (`GRCm39`) is wrong for macaque samples.

## Verification

```bash
# Check if BAM is aligned
samtools view -H bam | grep -c "^@SQ"  # Should be >0 for aligned BAM

# Check reference exists
ls -la /path/to/reference.fa

# Check species match
samtools view -H bam | grep "^@RG" | head -1  # Look for SM field
```

## Related Pitfalls in snakemake-omics-workflow

- Pitfall #33: PacBio Revio CCS BAMs are unmapped by default
- Pitfall #34: Reference genome path must exist and match species
