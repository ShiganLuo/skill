---
name: telomere-centromere-longread
description: Analyze telomere and centromere length from PacBio HiFi / ONT long-read BAM/FASTQ. Species-aware (mouse MaSat/MiSat, human alpha-satellite). Use when measuring repetitive chromosomal regions from long-read sequencing data.
tags: [pacbio, hifi, telomere, centromere, long-read, repeat, satellite, bam, mouse, human]
---

# Telomere & Centromere Analysis from Long-Read Data

## When to Use

- User has PacBio HiFi or ONT data and wants to measure telomere or centromere lengths
- User asks about repetitive region characterization (telomere, centromere, satellite DNA)
- Species is specified (motif sequences differ)

## Tool Selection Rule

**Always prefer established community tools over custom scripts.** Custom regex/k-mer
scripts are fallbacks for when standard tools are unavailable. Established tools have
been validated against known datasets and handle edge cases better.

| Task | Preferred Tool | Fallback |
|------|---------------|----------|
| Telomere length from reads | **Telogator2** (seed-extend, per-chromosome-arm) | pysam + regex scan |
| Telomere from assembly | **tidk** (scan contig ends) | regex on FASTA |
| Telomere assembly contig scan | Custom `scan_assembly_telomere.py` (sliding window on contig ends) | tidk |
| Telomere read-level density | Custom `read_density_telomere.py` (k-mer counting) | — |
| Centromere annotation | **RepeatMasker** (-species <taxon>) | k-mer density scan |
| Centromere assembly | **hifiasm** (HiFi) or **verkko** (HiFi + ONT UL) | — |

## Quick Decision Tree

```
Telomere?
  ├─ Mouse + need full-length measurement → Assembly-based (tidk scan contig ends)
  │   HiFi reads (15-25kb) CANNOT span mouse telomeres (30-150kb)
  ├─ Have HiFi/ONT BAM → Telogator2 (preferred) or pysam direct analysis
  │   NOTE: Telogator2 TL_p75 only measures terminal canonical repeat, not full telomere
  ├─ Have FASTQ → tidk or telogator2
  └─ Have assembly → tidk scan contig ends

Centromere?
  ├─ Have assembly → RepeatMasker (-species <taxon>)
  ├─ Have reads only → hifiasm assembly → RepeatMasker (2-step)
  └─ Need full centromere span → hifiasm/verkko assembly required (ONT UL helps)
```

## Prerequisites Check

Before starting, verify environment:

```bash
source /data/pub/zhousha/miniforge3/etc/profile.d/conda.sh
conda activate DNA
# Required: pysam, biopython, numpy
python -c "import pysam; import numpy; print('OK')"
```

If missing: `pip install pysam biopython numpy` (user preference: no auto-install, wrap in try/except).

For assembly-level analysis additionally need: `hifiasm`, `minimap2`, `samtools`, `RepeatMasker`, `bedtools`.

## Step 1: Telomere Analysis

### Motif Definitions

| Species | Telomere Motif | Notes |
|---------|---------------|-------|
| Mouse   | (TTAGGG)n     | Same as human, but much longer (30-150kb depending on strain) |
| Human   | (TTAGGG)n     | Typically 5-15kb |

**Mouse strain differences matter:**
- CAST/EiJ: ~150kb telomeres
- 129/Ola (E14 cells): long telomeres (~50-100kb)
- C57BL/6J: shorter (~30-50kb)

### Approach A: Telogator2 (Preferred)

```bash
conda install -c bioconda telogator2

telogator2 --reads input.bam \
           --output results/ \
           --threads 48
```

Outputs per-chromosome-arm telomere lengths. Seed-extend matching tolerates
HiFi errors better than pure regex.

### Approach B: Direct BAM Analysis (Fallback)

When Telogator2 is unavailable, use pysam direct analysis.

Script: `scripts/analyze_telomere.py`

```bash
conda activate DNA
python scripts/analyze_telomere.py \
  --bam input.bam \
  --sample_name SAMPLE \
  --output_dir results/ \
  --min_read_length 5000
```

**Key design decisions in the script:**
- Use `pysam.AlignmentFile(bam, "rb", check_sq=False)` — avoids index requirement
- Cluster nearby telomeric hits (within 30bp gap) to handle HiFi errors
- Classify hits by position: 5prime (<500bp from start), 3prime (>500bp from end), internal
- **Terminal telomere threshold must be >=1000bp** for mouse (not 100bp — too many false positives from subtelomeric noise and ITS)
- Output: per-read TSV, per-hit TSV, statistical summary

### Approach B: tidk (from FASTQ/assembly)

**Pitfall: tidk API uses `--string`, `--output`, `--dir` flags, NOT `-s`/`-o`.**

```bash
conda install -c bioconda tidk
tidk search --string TTAGGG --output <prefix> --dir <output_dir> <FASTA>
# Output: <output_dir>/<prefix>_telomeric_repeat.tsv
```

There is NO `tidk count` subcommand — that was removed in newer versions.
Always run `tidk search --help` to verify the API before writing scripts.

Check which contigs/scaffolds have telomeric repeats at their termini (= potential chromosome ends).

## Step 2: Centromere Analysis

### Motif Definitions

| Species | Centromere Type | Repeat Unit | Location |
|---------|----------------|-------------|----------|
| Mouse   | Major Satellite (MaSat) | ~234bp | Pericentromeric heterochromatin |
| Mouse   | Minor Satellite (MiSat) | ~120bp | Centromeric core |
| Human   | Alpha-satellite | ~171bp | Centromeric |

**Mouse centromeres can span several Mb** — HiFi reads (~15-20kb N50) cannot span them. Assembly required.

### Approach A: RepeatMasker on Assembly (Standard)

```bash
# Assembly first
hifiasm -o asm -t 48 --hifi reads.fastq.gz
awk '/^S/{print ">"$2; print $3}' asm.bp.p_ctg.gfa > asm.fasta

# Annotate
RepeatMasker -species mouse -pa 48 -dir rm_output -gff asm.fasta

# Extract satellite lengths
grep "MSAT\|Satellite" rm_output/asm.fasta.out | \
  awk '{sum += ($7-$6)} END {print "Satellite total:", sum}'
```

### Approach A2: Per-Contig Satellite Block Analysis

After RepeatMasker, use `extract_centromere_stats.py` to find contiguous satellite
DNA blocks on each contig. This identifies potential centromere regions and their boundaries.

```bash
python extract_centromere_stats.py \
  --rm_out rm_output/asm.fasta.out \
  --output centromere_stats.txt \
  --species mouse \
  --max_gap 50000 \
  --min_block_len 100000
```

**Parameters:**
- `--max_gap`: max gap (bp) between satellite hits to merge into one block (default: 50kb)
- `--min_block_len`: minimum block length to report (default: 100kb)

**Output interpretation:**
- Pure GSAT_MM blocks starting at position 1 → contig is centromeric satellite array fragment
- Mixed blocks (IMPB_01 + ZP3AR + MMSAT4) → pericentromeric transition zone
- For mouse, expect blocks of 100kb-3Mb

See `references/centromere_tools.md` for full tool landscape.

### Approach B: Read-level Satellite Scan (Fallback)

When RepeatMasker is unavailable, scan reads for satellite k-mers.

Mouse Major Satellite consensus (simplified):
```
GAAAAACCTCGAGAATGGCGAGAAACTGAGAAGCCCGCAACGAATGGGATG...
```
Key feature: GA-rich strand, long runs of "AATGGAATGG" repeats.

Mouse Minor Satellite consensus:
```
GAAAATGATAAAAACCACACTGTATGGAAATGACATTTATAATATCATAT...
```

### Approach C: Use Existing T2T Reference

C57BL/6J has a T2T reference at NCBI. Map reads to it and extract centromeric region coverage.

## Snakemake Pipeline Integration

When integrating telomere analysis into the Omics Snakemake pipeline, use the
"3-file + bin/" module pattern. The telomere module provides multiple approaches:

```
modules/telomere/
  telomere.smk          # rules for all approaches
  telomere.yaml         # conda: telogator2, tidk, pysam, numpy
  telomere.json         # config template
  bin/
    scan_assembly_telomere.py   # Approach A: assembly contig end scan
    read_density_telomere.py    # Approach B: read-level k-mer density
```

### Cross-module dependency (telomere → centromere assembly)

Approach A (assembly scan) and C (tidk) need the hifiasm assembly from the
centromere module. Pass the assembly directory via config:

```python
# In subworkflow (e.g., PacVar.smk):
telomere_config = {
    ...
    "assembly_dir": f"{outdir}/repeat/centromere",  # centromere output dir
    ...
}
```

The telomere module constructs the FASTA path:
```python
def get_assembly_fasta(wildcards):
    if assembly_dir:
        return os.path.join(assembly_dir, f"{wildcards.sample_id}/assembly/asm.bp.p_ctg.fa")
    return os.path.join(outdir, f"../centromere/{wildcards.sample_id}/assembly/asm.bp.p_ctg.fa")
```

### Telogator2 output directory pitfall

**Do NOT use `output.dir`** — it's not a declared output attribute. Telogator2
needs an output directory, but the rule should declare specific output files
and derive the directory path:

```python
# CORRECT — declare files, derive directory in run block
output:
    allele_tsv = outdir + "/{sample_id}/telogator2/tlens_by_allele.tsv",
    ...
run:
    output_dir = os.path.join(outdir, f"{wildcards.sample_id}/telogator2")
    cmd = ["telogator2", "-i", input.bam, "-o", output_dir, ...]
```

```python
# BROKEN — output.dir is not a declared attribute
output:
    allele_tsv = outdir + "/{sample_id}/tlens_by_allele.tsv",
    ...
run:
    cmd = ["telogator2", "-i", input.bam, "-o", output.dir, ...]  # AttributeError!
```

### Approach selection decision tree

```
Mouse telomere needed?
├─ Have hifiasm assembly? → Approach A: assembly_telomere_scan (recommended)
├─ No assembly, quick estimate? → Approach B: read_density_telomere
├─ Want standardized tool? → Approach C: tidk_scan
└─ Need per-allele with subtelomere? → Telogator2 (note TL_p75 limitation)
```

## Pitfalls

1. **BAM index not required** — use `check_sq=False` in pysam. Many PacBio BAMs lack BAI.
2. **HiFi quality is high but not perfect** — telomeric motif matching needs gap tolerance. Pure regex misses reads with 1-2 mismatches in repeat.
3. **Mouse telomeres are VERY long** — standard human-centric thresholds (e.g., >100bp) produce many false positives from subtelomeric noise. Use >=1000bp for mouse.
4. **Terminal threshold is critical** — a TTAGGG repeat at a read end is NOT necessarily a telomere. Could be subtelomeric scattered repeats or ITS near a random break point. Length >1000bp filters these out. For mouse E14 (129/Ola), true telomeres are typically 30-150kb.
5. **Centromere assembly collapse** — highly repetitive satellite DNA collapses in short contigs. Need high coverage + long reads. ONT ultra-long (>100kb) + HiFi is best.
6. **Species matters for RepeatMasker** — always specify `-species mouse` (not human). Wrong species gives wrong satellite annotations.
7. **E14 is 129/Ola, not C57BL/6J** — telomere length differs significantly between strains.
8. **BAM conversion to FASTQ is slow for 100GB files** — prefer direct pysam access or Telogator2's native BAM support to avoid the conversion step.
9. **User preference: use established tools** — when user asks to analyze telomere/centromere, check for existing tools (Telogator2, tidk, RepeatMasker) before writing custom scripts. Custom scripts are only for:
   - Parsing/summarizing tool output (e.g., extracting stats from RepeatMasker `.out`)
   - Visualization (plotting from tool TSV output)
   - Glue logic between tools
   If the user explicitly discussed and agreed on a tool earlier in the session, honoring that decision is mandatory.
10. **HiFi reads cannot span mouse telomeres** — mouse telomeres are 30-150kb, HiFi reads are ~15-25kb. Telogator2 only captures a fragment. For full-length mouse telomere measurement, use assembly-based methods (tidk on hifiasm contig ends) or ONT ultra-long reads (>100kb).
11. **Telogator2 TL_p75 ≠ full telomere length** — TL_p75 measures only the terminal canonical repeat (CCCTAA)n. Full telomeric region on read ≈ TL_p75 + tvr_len. Don't report TL_p75 as "telomere length" without clarifying what it measures.
12. **Telogator2 output can look misleadingly short** — if you see TL_p75 of 200-700bp for mouse, that's the terminal canonical portion only, not a biological anomaly. Check tvr_len for the variant repeat region. The combination is still shorter than true telomere length because the read doesn't span the full telomere.
13. **tidk API uses long flags** — `tidk search --string <MOTIF> --output <PREFIX> --dir <DIR> <FASTA>`. Short flags `-s`/`-o` are NOT valid. There is NO `tidk count` subcommand.
14. **tidk requires `tidk build` first** — stores database at `~/.local/share/tidk/tidk_database.csv`. Check this file's existence to determine if init is needed, NOT a sentinel file in the workflow output directory.
15. **Init rule pattern: check actual database, not sentinel** — when gating a tool's init rule, check the tool's actual database/config file (e.g., `~/.local/share/tidk/tidk_database.csv`), not a `touch`ed sentinel in the output directory. Sentinel files only work for same-run chaining, not cross-run persistence.
16. **read_density method is fundamentally unreliable for non-T2T genomes** — BOTH metrics (total tel_bp and terminal_tel_len) are flawed:
    - `total_tel_bp / n_chrom_arms`: counts ALL telomeric k-mers regardless of genomic position → includes ITS, subtelomeric noise
    - `terminal_tel_len`: checks telomeric signal within 500bp of read end, BUT a read ending with telomeric k-mers could simply be a HiFi read that starts/ends within an internal ITS region — the "terminal" signal is an artifact of read fragmentation, not evidence of a chromosome end
    - **Root cause**: isolated reads cannot distinguish true chromosome-end telomeres from internal ITS. No filtering logic (clustering, thresholds, position checks) can fix this without external positional information.
    - For non-T2T genomes, `assembly_scan` is more reliable (contig ends have positional meaning), but also has limitations (see pitfall 17).
    - For T2T genomes, position-based filtering on the reference (map reads to chromosome ends) can make read_density meaningful.
17. **assembly_scan limitations for non-T2T genomes** — contigs may break in subtelomeric regions, so contig ends with scattered telomeric repeats are not necessarily true chromosome ends. Watch for suspicious results:
    - `tel_length > 0` but `supporting_windows = 0`: k-mers cluster by gap tolerance (<30bp) but no 200bp window reaches 50% telomeric fraction → likely ITS, not real telomere
    - Identical telomere lengths at both ends of a contig (e.g., ptg000725c: 4693bp at both 5' and 3') → possible assembly artifact
    - Detection count far below expected chromosome arm count (e.g., 14/40) → assembly doesn't span most telomeres
    - For mouse (telomeres 30-150kb), max detected telomere of ~5-6kb suggests assembly breaks within the telomeric array

| Column | Meaning |
|--------|---------|
| `#chr` | Chromosome arm (e.g. chr9q) |
| `position` | Genomic position of telomere on reference |
| `ref_samp` | Reference genome used |
| `allele_id` | Haplotype/allele number (0, 1, 2) |
| `TL_p75` | **75th percentile of terminal canonical repeat (CCCTAA)n length** — NOT full telomere length |
| `read_TLs` | Per-read terminal telomere lengths (bp); negative = read didn't capture telomeric end |
| `read_lengths` | Per-read total lengths (bp) |
| `read_mapq` | Per-read mapping quality |
| `tvr_len` | TVR (Telomeric Variant Repeat) region length (bp) |
| `tvr_consensus` | TVR sequence using letter codes: C=canonical, L/D/V/A/M/P/S/E/N/T=variant repeats |
| `supporting_reads` | Read names supporting this allele |

**CRITICAL: `TL_p75` is NOT the full telomere length.** It measures only the pure
canonical repeat (CCCTAA)n at the read terminus. The full telomeric region on a read
≈ `TL_p75 + tvr_len`. Mouse telomeres have extensive variant repeat (TVR) regions
upstream of the canonical repeats.

Telomere structure on a read:
```
[Subtelomeric] → [TVR: variant repeats L,D,V,A,M,P,S,E,N,T] → [TTR: canonical CCCTAA repeats] → [read end]
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  tvr_len + tvr_consensus                        TL_p75 only measures this part
```

For mouse (telomeres 30-150kb), HiFi reads (~15-25kb) CANNOT span the full telomere.
Each read captures only a fragment. Assembly-based methods (tidk on contig ends) are
needed for full-length measurement.

## Support Files

- `references/mouse_repetitive_sequences.md` — Mouse satellite/telomere consensus sequences
- `references/snakemake-implementation.md` — Omics pipeline module implementation patterns

Telogator2's `TL_p75` only measures the **terminal canonical repeat (CCCTAA)n** at the very end of the read — NOT the full telomere length. Mouse telomere structure:

```
[Subtelomeric] --- [TVR (variant repeats)] --- [TTR (canonical CCCTAA)] --- [Chromosome end]
                    ^^^^^^^^^^^^^^^^^^^^^^^     ^^^^^^^^^^^^^^^^^^^^^^^^
                    tvr_len (L,D,V,A,M,P,S...)   TL_p75 (only this part)
```

For mouse telomeres (30-150kb), HiFi reads (~15-25kb N50) **cannot span the full telomere**. Each read captures only a fragment. Combined TL_p75 + tvr_len is typically only 1-4kb, far below the true length.

**When Telogator2 is sufficient:** Human telomeres (5-15kb) — HiFi reads can span most of the telomere.

**When Telogator2 is insufficient:** Mouse telomeres (30-150kb) — need alternative approaches.

## Alternative Approaches for Mouse Telomeres

### Approach 1: Assembly-based contig end scanning (recommended)

Scan hifiasm assembly contig ends (first/last 50kb) for contiguous telomeric repeats using a sliding window. Assembly contigs may span the full telomere.

```bash
# Input: hifiasm assembly (already produced by centromere module)
# Output: per-contig telomere length at each end
python scan_assembly_telomere.py --fasta assembly.fa --output results/
```

Pros: May capture full telomere length; no additional tools needed beyond existing assembly.
Cons: Assembly may not span very long telomeres; depends on centromere assembly not being skipped.

### Approach 2: Read-based k-mer density estimation

Count telomeric k-mers (CCCTAA/TTAGGG) across all HiFi reads. Divide total telomeric bp by number of chromosome arms (~40 for diploid mouse) to estimate average telomere length.

```bash
python read_density_telomere.py --bam input.bam --output results/
```

Pros: No assembly needed; works directly from raw reads; gives genome-wide average.
Cons: Only gives global average, not per-chromosome-arm; noisy for low coverage.

### Approach 3: tidk (community tool)

Install tidk and scan assembly contig ends for telomeric repeats.

```bash
conda install -c bioconda tidk
tidk search --string TTAGGG --output <prefix> --dir <output_dir> assembly.fasta
# Output: <output_dir>/<prefix>_telomeric_repeat.tsv
```

Pros: Standard community tool; standardized output.
Cons: Requires installation; still assembly-dependent. No `tidk count` subcommand.

### Approach 4: TelomereHunter (alternative tool)

TelomereHunter estimates telomere content from BAM files with filtering for terminal vs internal hits.

## Decision Tree for Mouse Telomeres

```
Mouse telomere needed?
├─ Have hifiasm assembly? → Assembly-based scan (Approach 1)
├─ No assembly, need quick estimate? → Read-based k-mer density (Approach 2)
├─ Want standardized tool output? → tidk (Approach 3)
└─ Need per-allele with subtelomere context? → Telogator2 (but note TL_p75 limitation)
```

## Snakemake Module Integration

The telomere module uses the "3-file + bin/" pattern with all approaches unified:

```
modules/telomere/
  telomere.smk          # rules: telogator2_run, assembly_telomere_scan, read_density_telomere, tidk_scan
  telomere.yaml         # conda: telogator2, tidk, pysam, numpy
  telomere.json         # config template
  bin/
    scan_assembly_telomere.py   # Approach A: assembly contig end scan
    read_density_telomere.py    # Approach B: read-level k-mer density
```

### Cross-module dependency (telomere → centromere assembly)

Approach A (assembly scan) and C (tidk) need the hifiasm assembly from the
centromere module. Pass the assembly directory via config:

```python
# In subworkflow (e.g., PacVar.smk):
telomere_config = {
    ...
    "assembly_dir": f"{outdir}/repeat/centromere",  # centromere output dir
    ...
}
```

### Pitfall: run.py outfiles must match rule outputs

When adding new rules to the telomere module, **update `run.py`'s `runPacVar()` outfiles**
to match the new output paths. This is part of the SKILL.md extension checklist and is
easy to forget.

### Pitfall: README updates required

When adding new analysis approaches, update both:
1. `README.md` (main) — update the workflow table row
2. `subworkflow/README.md` — update the workflow description section

This is in the SKILL.md extension checklist. User explicitly corrected forgetting this.

## Key Insight: TVR vs TTR

Mouse telomeres have extensive **Telomeric Variant Repeats (TVR)** — non-canonical repeats (L, D, V, A, M, P, S, E, N, T) interspersed with canonical (C=CCCTAA) repeats. The TVR region can be several kb long and is a significant portion of the total telomere.

When interpreting Telogator2 output:
- `TL_p75` = length of pure canonical repeat at read end (TTR only)
- `tvr_len` = length of TVR region (variant repeats)
- **Total captured telomere ≈ TL_p75 + tvr_len** (still only a fragment for mouse)

## Verification

After telomere analysis:
- Check that `*_telomere_stats.txt` shows reasonable numbers (mouse: median terminal telomere >5kb)
- Verify reads with telomere hits exist in `*_telomere_reads.tsv`
- Confirm 5' and 3' distributions are roughly symmetric
- **For mouse**: If Telogator2 TL_p75 values are <1kb, the telomeres are NOT necessarily short — the tool is only measuring the terminal canonical repeat, not the full telomere

After centromere analysis:
- Satellite DNA should be 3-6% of mouse genome assembly
- MaSat should be more abundant than MiSat
- Check that satellite annotations are on expected chromosomes

## Pitfall: Exome Data Cannot Measure Telomere Length

**Exome sequencing is fundamentally unsuitable for telomere length estimation.** Exome capture
probes target exonic/coding regions, not the repetitive TTAGGG sequences at chromosome ends.

**Symptoms when analyzing Exome data:**
- read_density: ~0.8% telomeric fraction, median terminal telomere ~6bp
- assembly_scan: Only 7/40 chromosome arms detected
- tidk: Zero telomeric repeats found
- telogator2: Only 3 alleles across entire genome

**User insight**: "这几个方法貌似都不能准确估计端粒长度" — all methods fail on Exome data
because the underlying data doesn't contain sufficient telomeric sequences.

**Solution**: Use WGS data, PacBio HiFi/ONT long reads, or dedicated assays (TRF, Q-FISH, TeSLA).
