# STAR Alignment Rate Diagnostics

Systematic approach for diagnosing low STAR alignment rates in RNA-seq pipelines.

## Key Log Files

| File | Content |
|------|---------|
| `*.Log.final.out` | Summary metrics (alignment rates, splice counts) |
| `*.Log.out` | Full parameters and genome index info |
| `*.Log.progress.out` | Per-minute alignment progress |

## Log.final.out Key Metrics

### Red Flags

| Metric | Normal Range | Problem Signal |
|--------|--------------|----------------|
| Uniquely mapped % | 70-95% | <50% = investigate |
| Unmapped: too short % | <10% | >80% = data or index problem |
| Unmapped: too many mismatches % | <5% | >20% = wrong reference or contamination |
| Annotated splices | >0 for RNA-seq | 0 = missing sjdb annotation |

### Interpreting "Unmapped: too short"

STAR classifies reads as "too short" when they cannot be extended to meet minimum seed length after soft-clipping. Common causes:

1. **Missing splice junction annotation** (sjdbOverhang=0, no GTF): Reads spanning introns cannot be aligned
2. **Empty/corrupt input files**: Reads are truncated or missing
3. **Severe RNA degradation**: Fragments too short to map uniquely
4. **Wrong reference genome**: Reads don't match the organism

## Diagnostic Workflow

### Step 1: Check Log.final.out

```
Key values to extract:
- Uniquely mapped reads %
- Unmapped: too short %
- Annotated splices count
```

### Step 2: Check Log.out for Index Info

```
Look for:
- sjdbOverhang value (0 = no splice annotation)
- sjdbGTFfile value (- = no GTF used)
- genomeFastaFiles (verify correct reference)
```

### Step 3: Trace Data Chain Upstream

For LIMS-based pipelines, check file sizes at each level:

```
1_raw_fq/       → Original sequencing data
2_clean_fq/     → After adapter trimming + QC
3_transcript_fq/ → After rRNA removal
4_transcript_bam/ → STAR alignment output
```

**Critical check**: If files are only 29 bytes, they are empty (just gzip header).

### Step 4: Check Upstream Step Logs

Read stderr from each processing step:
- `CNC.*.MergeFq.stderr` - FastQ merging
- `CNC.*.FqQc.stderr` - Quality control
- `CNC.*.RmrRNA.stderr` - rRNA removal

For rRNA removal (Bowtie2), check:
- Total input reads
- Alignment rate to rRNA (should be 5-30% for good RNA)
- Output file size

## Common Root Causes

### Case 1: Single Sample Low Rate, Others Normal

**Likely cause**: Sample-specific data issue
- Check raw data file sizes
- Check RNA quality metrics (RIN, DV200)
- Look for FFPE or degraded samples

### Case 2: All Samples Low Rate

**Likely cause**: Pipeline or reference issue
- Wrong reference genome
- Corrupted genome index
- Missing splice junction annotation

### Case 3: High "Too Short" with Normal Read Length

**Likely cause**: Missing splice annotation
- Check sjdbOverhang in Log.out
- Verify GTF file was provided
- Rebuild index with annotation if needed

## LIMS Pipeline File Size Checks

```bash
# Check if fastq files are empty (29 bytes = just gzip header)
ls -la */cancer/2_clean_fq/*.fq.gz
ls -la */cancer/3_transcript_fq/*_rmr.*.gz

# Normal sizes should be GB, not bytes
```

## Example: 29-byte Empty File Detection

A gzip file with only 29 bytes contains no actual data:
- Bytes 0-9: gzip header (10 bytes)
- Bytes 10-27: empty deflate block + footer (18 bytes)
- Total: 28-29 bytes for empty content

If you see 29-byte .gz files, the upstream process failed to write data.
