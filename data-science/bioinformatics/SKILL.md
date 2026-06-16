---
name: bioinformatics
description: Bioinformatics tools and genomics pipelines — RNA-seq quantification, gene body coverage, cross-sample reporting, SV visualization (OncoPrint), and Snakemake workflow orchestration.
tags: [genomics, rna-seq, stringtie, quantification, bioinformatics, coverage, oncoprint, sv-visualization, snakemake, summary-report]
triggers:
  - StringTie, featureCounts, HTSeq, or other RNA-seq quantification
  - Gene abundance merging, TPM/FPKM/Coverage calculations
  - GTF/GFF annotation parsing and manipulation
  - Duplicate gene_id handling in quantification output
  - RNA-seq pipeline design or debugging
  - gene body coverage, transcript coverage curves, RSeQC-style analysis
  - summarize bioinformatics tool output, aggregate across samples
  - oncoprint, SV comparison plot, structural variant visualization
  - Snakemake omics workflow, module creation, Nextflow porting
  - sample_id/task_id matching to file paths, path component matching
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

---

## Gene Body / Transcript Coverage Analysis

Compute coverage curves across gene bodies from BAM files with BED annotations. RSeQC-style analysis using `pysam.fetch()` + `read.get_blocks()` (10-50x faster than `pysam.pileup()`).

### Core Algorithm

1. **BED Loading** — group intervals by transcript ID, filter by region type (`exclude_region` uses exact `isin()` match)
2. **Gene Model** — sort exons, compute total length, build bin edges via `np.linspace(0, length, bins+1)`
3. **Coverage Extraction** — use `bam.fetch()` + `get_blocks()`, NOT `pysam.pileup()`
4. **Vectorized Binning** — `np.add.reduceat(gene_vec, bin_edges[:-1])`, reverse for negative strand
5. **Normalization** — per-gene max → range [0, 1], eliminates expression-level differences
6. **Aggregation** — per-BAM average across genes, then across BAMs

### CLI Interface

```bash
python geneBody_coverage.py \
    -i <BAM_INPUT> \       # single, comma-sep, dir, or list file
    -b <BED_FILE> \        # BED/TSV with header
    -o <OUTPUT_PREFIX> \
    -t 4 \                 # threads (one per BAM)
    --bins 100 \           # percentiles across gene body
    --min-length 100 \     # skip short genes
    --exclude-region UTR IVS \
    --plot-format png
```

### Coverage Pitfalls

- **"Batman ears" curve** (high at ends, low middle): UTR or IVS not excluded from gene body. Fix: `--exclude-region UTR IVS`
- **Wrong exclude values**: `exclude_region` uses `isin()` exact match. If BED has "5UTR"/"3UTR" but you exclude "UTR", nothing gets filtered.
- **Missing supplementary filter**: Always filter `is_supplementary` alongside `is_secondary`.
- **Raw coverage dominated by high-expression genes**: Normalize per-gene by max to compare distribution shapes.

### Performance

| Approach | Speed | Notes |
|----------|-------|-------|
| pysam.pileup() | 1x | Baseline, very slow |
| fetch + get_blocks | 10-50x | Recommended |
| samtools depth (C) | 50-100x | External subprocess |
| numpy reduceat binning | O(L) vectorized | vs O(bins×L) Python loop |

Multiprocessing: one worker per BAM (not per gene). See `references/coverage-analysis-detail.md` for full implementation.

---

## Cross-Sample Tool Output Reporting

Build Python scripts that parse bioinformatics tool output (TSV/VCF/BED), aggregate across samples, and produce TSV tables, HTML reports, and publication-quality figures with data-driven conclusions.

### Workflow

1. **Inspect** — read 1-2 example outputs, understand columns and naming conventions
2. **CLI** — two mutually exclusive input modes: `--indir` (scan directories) vs `-p`/`-d` (explicit file lists)
3. **Analysis** — pure functions: `per_sample_stats()`, `find_recurrent_events()`, `find_functional_events()`
4. **Output** — three channels: TSV tables, self-contained HTML report, matplotlib figures

### Standard Figure Set

| Fig | Content | Type |
|-----|---------|------|
| 1 | Per-sample event counts by confidence/category | Stacked bar |
| 2 | Event type distribution (all samples) | Horizontal bar |
| 3 | Type composition per sample | Stacked bar |
| 4 | Functional category distribution | Grouped bar |
| 5 | Cross-sample recurrence heatmap | Binary heatmap |
| 6 | Top functional events by support | Horizontal bar with color-coded confidence |

### Figure Conclusions — Grouped, Data-Driven

Always group figures under section headers. Compute real numbers (counts, percentages, top-N) — never hardcode. See `references/tool-summary-detail.md` for the full reporting framework and Snakemake integration patterns.

### Reporting Pitfalls

- Don't install packages without asking — wrap in try/except and log warning
- Arriba gene names: strip aliases with `.split("(")[0].split(",")[0]`
- ITD (internal tandem duplication): `gene::gene` self-fusions with in-frame reading frame
- Read-through fusions: transcriptional noise, not structural variants

---

## SV Visualization & OncoPrint

Build Python CLI tools for genomics structural variant (SV) visualization. For general matplotlib plotting patterns (multi-format output, typing, CLI conventions), see `python-scientific-plotting-scripts` skill.

### OncoPrint Layout

CRITICAL — gridspec ratios must be FIXED, never raw data dimensions:

```python
# CORRECT: fixed ratios
gs = fig.add_gridspec(2, 2,
    width_ratios=[4, 1],
    height_ratios=[1, 4],
    wspace=0.04, hspace=0.04)

# WRONG — when n_genes=20, height_ratios=[0.8, 20] compresses main grid to nothing
```

**Pitfalls:**
1. Never use `n_samples`/`n_genes` as gridspec ratios
2. Never use `sharex`/`sharey` between main grid and margin axes
3. Set `xlim`/`ylim` BEFORE drawing bars

### SV Type Colors

DEL=#E74C3C, DUP=#3498DB, INS=#2ECC71, INV=#9B59B6, BND=#F39C12, OTHER=#95A5A6

Multi-type cells: stack colored rectangles vertically (k=0 at bottom).

### CLI Conventions

- Multi-format: `-f`/`--format` with `action="append"`
- Dict-like inputs: `key=value` or `key:path` format (never paired parallel lists)
- Parallel plotting: use `ProcessPoolExecutor` (not ThreadPoolExecutor — SQLite/gffutils thread safety issue)

See `references/sv-visualization-detail.md` for full OncoPrint implementation.

---

## Snakemake Omics Workflow

Add new modules, subworkflows, and pipelines to the Omics Snakemake project, including porting from Nextflow (nf-core).

### Prerequisites — Read First

1. `skill.md` — project overview, run.py responsibilities
2. `subworkflow/subworkflow.md` — subworkflow conventions
3. `modules/modules.md` — module conventions

### Extension Checklist

1. Add model template JSON in `config/<WorkflowName>.json`
2. Add `run<WorkflowName>()` in `run.py`
3. Add to `--workflow_name` choices in `parse_args()`
4. Add elif branch in `__main__` block
5. Create subworkflow snakefile in `subworkflow/<WorkflowName>.smk`
6. Create modules in `modules/<tool>/`

### Module 3-File Pattern

```
modules/<tool>/
  <tool>.smk    # Snakemake rules
  <tool>.json   # Config template
  <tool>.yaml   # Conda environment
```

### Key Conventions

- Config dict: `<tool>_config`
- Rule aliasing: `use rule X from Y as <Workflow>_X`
- Chain outputs: module B's `indir` = module A's `outdir`
- Conditional modules: `if not skip_<X>:` blocks
- Aggregation rules: summary script accepts explicit file paths (`-p`/`-d`), not directory scanning

### Nextflow-to-Snakemake Porting

- `process` → `rule` in module .smk
- `workflow` → subworkflow .smk
- `Channel.join()` → rule input dependencies
- `if (params.X)` → `if not config.get("Params", {}).get("skip_X")`

### Snakemake Pitfalls

1. Don't use `execute_code` with triple-quoted Snakemake syntax — use `write_file` directly
2. Subdirectory rules: `conda: "../<parent>.yaml"` (not full path)
3. Rule name conflicts when importing same module twice — use distinct aliases
4. `outfiles` paths must exactly match rule outputs
5. Patch insertion position: verify with `read_file` + `py_compile` after patching

See `references/snakemake-workflow-detail.md` for full templates and the PacVar porting example.

---

## Coordinate Liftover (hg19↔hg38)

Convert genomic coordinates between assemblies using `pyliftover` (pure Python, no external binary needed).

### Key API Behavior

`pyliftover.LiftOver.convert_coordinate(chrom, pos)` returns **single-point** results:
```python
# Returns: [(new_chrom, new_pos, strand, score), ...] or None
result = lo.convert_coordinate('chr1', 69069)
# [('chr1', 69069, '-', 20851231461)]
```

For BED intervals, convert start and end **separately**, then check they land on the same chromosome:
```python
def convert_interval(lo, chrom, start, end, output_chr_style=False):
    chrom_lift = chrom if chrom.startswith('chr') else 'chr' + chrom
    start_result = lo.convert_coordinate(chrom_lift, start)
    end_result = lo.convert_coordinate(chrom_lift, end)
    if not start_result or not end_result:
        return None
    new_chrom_s, new_start, _, _ = start_result[0]
    new_chrom_e, new_end, _, _ = end_result[0]
    if new_chrom_s != new_chrom_e:
        return None
    new_chrom = new_chrom_s
    if output_chr_style:
        if not new_chrom.startswith('chr'):
            new_chrom = 'chr' + new_chrom
    else:
        if new_chrom.startswith('chr'):
            new_chrom = new_chrom[3:]
    return (new_chrom, int(new_start), int(new_end))
```

### Chain Files

Download from UCSC:
```bash
wget http://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz
```

### Pitfalls

- **Single-point API**: `convert_coordinate()` returns `(chrom, pos, strand, score)`, NOT `(chrom, start, end, strand)`. Common mistake: unpacking 4-tuple as interval.
- **chr prefix**: Input must have `chr` prefix for UCSC chain files. `1` → `chr1` before calling.
- **Coordinate style**: Add `--chr` flag to control output style (chr1 vs 1). Default: numeric style (no prefix).
- **GLIBC version**: UCSC precompiled `liftOver` binary requires GLIBC 2.29+, often unavailable on CentOS 7. Use `pyliftover` instead: `pip install pyliftover`.

---

## GMT + GTF → BED Extraction

Extract gene-level BED coordinates from a GMT gene set file and a GENCODE GTF annotation.

### GMT Format

Tab-separated: `geneset_name\turl\tgene1\tgene2\tgene3\t...`

### Pattern

```python
import re

def parse_gmt(gmt_path: str) -> set:
    genes = set()
    with open(gmt_path) as f:
        for line in f:
            fields = line.strip().split('\t')
            if len(fields) >= 3:
                genes.update(fields[2:])
    return genes

def parse_gtf_gene_coords(gtf_path: str) -> dict:
    gene_coords = {}
    name_pat = re.compile(r'gene_name "([^"]+)"')
    with open(gtf_path) as f:
        for line in f:
            if line.startswith('#') or '\tgene\t' not in line:
                continue
            fields = line.split('\t')
            chrom, start, end, strand = fields[0], int(fields[3])-1, int(fields[4]), fields[6]
            m = name_pat.search(fields[8])
            if m:
                name = m.group(1)
                if name not in gene_coords or (end-start) > (gene_coords[name][2]-gene_coords[name][1]):
                    gene_coords[name] = (chrom, start, end, strand)
    return gene_coords
```

### Pitfalls

- GTF is **1-based**, BED is **0-based**: subtract 1 from GTF start coordinate.
- Filter with `'\tgene\t'` in line (column 3) — don't parse transcript/exon records.
- When multiple gene records exist (patch haplotypes), keep the longest span.
- GMT may contain aliases not matching GTF `gene_name` — report unmatched genes for review.

---

## Path Matching Utilities

Two-phase matching pattern for resolving sample/task IDs to file paths: regex full component match first, substring fallback if no exact match. See `references/path-matching-utilities.md` for implementation templates and pitfalls.
