# Fiber-seq Workflow Reference

## Overview

Fiber-seq (Fiber sequencing) is a single-molecule chromatin accessibility assay that uses DNA methyltransferase to mark accessible chromatin regions. It provides nucleotide-resolution maps of chromatin accessibility, nucleosome positions, and transcription factor footprints across long chromatin fibers (~10-30 kb).

**Reference:** Shipony et al., 2020, Nature Methods. "Long-range single-molecule mapping of chromatin accessibility in eukaryotes"
**Guide:** https://fiberseq.github.io/

## Tools

- **fibertools-rs (ft):** Main CLI tool for Fiber-seq data processing
  - Install: `conda install bioconda::fibertools-rs`
  - GitHub: https://github.com/fiberseq/fibertools-rs
- **FiberHMM:** HMM-based footprint caller for nucleosomes and MSPs
  - GitHub: https://github.com/fiberseq/FiberHMM
- **pbmm2:** PacBio long-read aligner
- **hiphase:** Haplotype phasing (optional)

## Workflow Steps

### 1. m6A prediction (ft predict-m6a)
Predict m6A methylation positions from PacBio HiFi CCS BAM with polymerase kinetics.

```bash
ft predict-m6a -t 16 input.ccs.bam output.fiberseq.bam
```

**Input:** PacBio CCS BAM with IPD/PL kinetics tags (SPRQ chemistry or newer)
**Output:** Fiber-seq BAM with m6A calls in MM/ML tags

### 2. Add nucleosomes (ft add-nucleosomes)
Infer nucleosome positions and methylase-sensitive patches (MSPs).

```bash
ft add-nucleosomes -t 16 input.fiberseq.bam output.fiberseq.nuc.bam
```

**Note:** `ft predict-m6a` already runs nucleosome calling internally. Only run separately if you want to try different parameters.

### 3. FIRE calling (ft fire)
Identify Fiber-seq Inferred Regulatory Elements (FIREs).

```bash
ft fire input.fiberseq.nuc.bam output.fiberseq.fire.bam
# For ONT data:
ft fire --ont input.fiberseq.nuc.bam output.fiberseq.fire.bam
```

**Output:** BAM with FIRE calls in `aq` tags (scores > 230 = FIRE elements)

### 4. Extract data (ft extract)
Extract Fiber-seq data to BED format for visualization and analysis.

```bash
ft extract -t 8 \
    --m6a m6a.bed.gz \
    --nuc nuc.bed.gz \
    --msp msp.bed.gz \
    --fire fire.bed.gz \
    input.fiberseq.fire.bam
```

## BAM Tags

| Tag | Type | Description |
|-----|------|-------------|
| ns | B,I | Nucleosome starts (0-based query coords) |
| nl | B,I | Nucleosome lengths |
| as | B,I | MSP starts |
| al | B,I | MSP lengths |
| aq | B,C | MSP/FIRE quality scores (0-255) |
| nq | B,C | Nucleosome quality scores (0-255) |

## Key Concepts

- **MSP (Methylase-Sensitive Patch):** Accessible chromatin region marked by methyltransferase
- **FIRE (Fiber-seq Inferred Regulatory Element):** High-confidence regulatory elements identified from MSP patterns
- **Nucleosome:** Protected region (~147 bp) wrapped around histone octamer

## Integration with Omics Pipeline

The Fiber-seq subworkflow (`subworkflow/Fiberseq.smk`) chains:
1. `ft_predict_m6a` → `ft_add_nucleosomes` → `ft_fire` → `ft_extract`

Module: `modules/fibertools/fibertools.smk`
Node function: `runFiberseq()` in `node.py`
