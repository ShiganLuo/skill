---
name: bioinformatics
description: Bioinformatics tools and genomics pipelines — RNA-seq quantification, gene body coverage, cross-sample reporting, SV visualization (OncoPrint), Snakemake workflow orchestration, sequencing depth analysis, CNV analysis (CNVkit), genomic interval filtering, and scientific plotting patterns.
tags: [genomics, rna-seq, stringtie, quantification, bioinformatics, coverage, oncoprint, sv-visualization, snakemake, summary-report, cnv, cnvkit, copy-number, sequencing-depth, variant-detection, power-analysis, bed-annotation, genomic-interval, depth-filtering, large-file-processing, matplotlib, plotting, typing, argparse, docstrings]
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
  - depth analysis, minimum depth, sequencing depth requirements
  - detection sensitivity, power analysis variant calling
  - LOD score GATK, imputation accuracy low depth, UMI consensus detection
  - coverage uniformity Poisson
  - cnvkit output, segment size, copy number segments, cnv analysis
  - .cns file, .cnr file, per-gene cnv, HRD score, median segment
  - filter depth by BED, exclude intron UTR, BED annotation filtering
  - genomic interval containment, filter depth file regions
  - remove intronic positions, exon-only depth
  - dbSNP VCF, chromosome naming mismatch, reference version mismatch
  - GCF accession, dbsnp download, common SNP VCF
  - assertion aux itr failed, housekeeping gene BED, gene list to BED
  - refGene download, UCSC gene coordinates
  - liftOver, pyliftover, coordinate conversion, assembly conversion, hg19 to hg38
  - GMT file parse, MSigDB gene set, GTF gene extraction, GENCODE gene BED
  - refactor plotting script, multi-format image output, significance brackets
  - matplotlib scientific plot, seaborn analysis, broken axis, chi2 contingency
  - ProcessPoolExecutor plotting, parallel gene plotting
  - MSI detection, microsatellite instability, bMSI blood-based MSI
  - weighted entropy baseline, repeat-length distribution, per-locus XGBoost
  - MSI feature engineering, msiRatio, msimssRatio, Fisher scatter ratio
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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.
   Coverage_merged = sum(Cov_i * L_i) / sum(L_i)
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.
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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

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

## Sequencing Depth Analysis

Compute minimum sequencing depth for variant detection across clinical, population, and research scenarios. 6 statistical models × 5 scenarios.

### Quick Reference: Model Selection

| Scenario | Best model | Why |
|----------|-----------|-----|
| Clinical somatic (VAF 1-10%) | LOD + error-aware binomial | Matches GATK/Mutect2 logic |
| Liquid biopsy ctDNA (0.1-1%) | UMI-aware | Molecular consensus is critical |
| Germline (VAF ~50%) | LOD (vaf_model=0.5) | Standard germline calling |
| Population low-depth (1-4x) | Population imputation | LD-based imputation compensates |
| Site-level coverage | Poisson uniformity | Depth at site ≠ average depth |

### Key Results

| Scenario | VAF | Required depth (95% power) |
|----------|-----|---------------------------|
| Clinical somatic | 5% | 120-230x (model-dependent) |
| Clinical somatic | 1% | 570-2000x |
| Germline het | 50% | 14-17x |
| Population (1000 samples) | MAF 10% | ~1x/sample (R²≥0.80) |
| Coverage uniformity | — | 537x avg for P(site≥500x)≥0.95 |

### CLI

```bash
python cli.py list
python cli.py sweep clinical_somatic --vaf 0.05 --output results/
python cli.py min-depth germline --vafs 0.3 0.5 1.0
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

See `references/depth-analysis-framework.md` for full framework, `references/depth-analysis-models.md` for mathematical formulations, `references/depth-analysis-pitfalls.md` for common mistakes.

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

model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

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

## CNV Analysis (CNVkit)

Analyze CNVkit output files (.cns, .cnr, .cnn, segments.txt) for copy number variation in clinical oncology pipelines.

### File Structure

| File | Description | Key Columns |
|------|-------------|-------------|
| `*.cnr` | Bin-level log2 ratios | chromosome, start, end, gene, log2, depth, weight |
| `*.cns` | Segmented CN calls | chromosome, start, end, gene, log2, depth, probes, weight, ci_lo, ci_hi |
| `*.call.cns` | Called CN states | adds total_cn, A_cn, B_cn |
| `*.bintest.cns` | Per-bin significance | significant hit bins |

Pipeline: BAM → .targetcoverage.cnn + .antitargetcoverage.cnn → .cnr → .cns → .call.cns

### Gene Column Parsing

The `gene` column in `.cns` is **comma-separated**:
```python
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### HRD Score Components

In `tumor/risk{threshold}/{sample}_HRDresults.txt`:
- **HRD-LOH**: Loss of heterozygosity segments
- **LST**: Large-scale state transitions
- **TAI**: Telomeric allelic imbalance
- **HRD-sum**: Total (= HRD-LOH + LST + TAI)

### Key Pitfalls

- **Tool vs data questions**: "Does CNVkit use purity?" is a tool-property question — don't write a script.
- **Gene column is comma-separated**, not tab-separated.
- **Antitarget bins** use literal string `Antitarget` in gene column — filter these out.
- **Risk threshold variants**: Pipeline runs 0.5/0.8/1.1 thresholds; primary results in `risk1.1/`.
- **Duplicate rows** in annotation CSV: deduplicate by `(Gene, ExonStart, ExonEnd)`.
- **Empty segments file**: Check both `tumor/{sample}.segments.txt` and `tumor/risk1.1/{sample}.segments.txt`.
- **execute_code AF_UNIX path limit**: Use `terminal` with `python3` instead on long workspace paths.

See `references/cnv-analysis-detail.md` for full file structure, per-gene analysis patterns, and clinical pipeline layout.

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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.
modules/<tool>/
  <tool>.smk    # Snakemake rules
  <tool>.json   # Config template
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Chain Files

Download from UCSC:
```bash
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Pitfalls

- **Single-point API**: `convert_coordinate()` returns `(chrom, pos, strand, score)`, NOT `(chrom, start, end, strand)`. Common mistake: unpacking 4-tuple as interval.
- **chr prefix**: Input must have `chr` prefix for UCSC chain files. `1` → `chr1` before calling.
- **Coordinate style**: Add `--chr` flag to control output style (chr1 vs 1). Default: numeric style (no prefix).
- **GLIBC version**: UCSC precompiled `liftOver` binary requires GLIBC 2.29+, often unavailable on CentOS 7. Use `pyliftover` instead: `pip install pyliftover`.

---

## Genomic Interval Filtering

Filter large genomic data files (depth, coverage, VCF) by BED annotation intervals. Stream multi-GB files with constant memory.

### BED Coordinate Convention (CRITICAL)

BED uses **0-based half-open** `[start, end)`. Depth/VCF `Pos` is **1-based inclusive**.

Containment: `s < pos <= e` (equivalently: `pos >= s+1 and pos <= e`)

Convert to 1-based: `[s + 1, e]` — NOT `[s+1, e-1]` (loses last base).

### Interval Containment (Sorted Arrays, preferred over IntervalTree)

```python
from bisect import bisect_right

def in_excluded(pos: int, intervals: tuple[list[int], list[int]]) -> bool:
    starts, ends = intervals
    idx = bisect_right(starts, pos) - 1
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

**Why NOT IntervalTree**: rejects zero-width intervals (single-base BED after conversion). Sorted arrays are cache-friendly for 100M+ queries, `bisect_right` is C-implemented.

### Streaming Large Files

```python
with open(depth_path) as fin, open(output_path, "w") as fout:
    fout.write(fin.readline())  # header
    for line in fin:
        parts = line.split("\t", maxsplit=2)  # only parse needed columns
        chrom = normalize_chrom(parts[0])
        pos = int(parts[1])
        if not in_excluded(pos, intervals_by_chrom.get(chrom, ([], []))):
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Multiprocessing Pitfall

Local functions inside `main()` cannot be pickled. Use module-level worker + `initializer=` pattern:
```python
TREES: dict | None = None
def _init_worker(trees):
    global TREES; TREES = trees
def _worker(depth_path, output_path):
    assert TREES is not None
    ...
with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(trees,)) as pool:
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Key Pitfalls

- **BED coordinate formula**: `[s+1, e]` not `[s+1, e-1]`.
- **Chromosome mismatch**: Always normalize `chr` prefix. Silent miss = all positions kept (wrong).
- **Reference version mismatch**: Using annotation from different assembly causes `Assertion 'aux->itr' failed` in htslib tools.
- **GTF 1-based vs BED 0-based**: `bed_start = gtf_start - 1`.
- **maxsplit in parsing**: Don't `split("\t")` entire 9+ column lines when you only need columns 0-1.

See `references/genomic-interval-filtering-detail.md` for full implementation, `scripts/filter_intron_utr_reference.py` for production script. Assembly conversion and gene BED extraction overlap with Coordinate Liftover and GMT+GTF sections above — see those for details.

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
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Pitfalls

- GTF is **1-based**, BED is **0-based**: subtract 1 from GTF start coordinate.
- Filter with `'\tgene\t'` in line (column 3) — don't parse transcript/exon records.
- When multiple gene records exist (patch haplotypes), keep the longest span.
- GMT may contain aliases not matching GTF `gene_name` — report unmatched genes for review.

---

## MSI / bMSI Detection

Microsatellite instability detection from tissue (tMSI) and liquid biopsy (bMSI). Covers repeat-length distribution features, weighted entropy, baseline QC chain, Fisher-like scatter metrics, bMSI data simulation (tissue signal injection at low AF), per-locus XGBoost classifiers, and msisensor-pro source analysis.

See `references/msi-bmsi-detection.md` for feature engineering formulas, QC thresholds, simulation patterns, prediction workflow, pitfalls, and msisensor-pro algorithm details.
See `references/msisensor-pro-analysis.md` for msisensor-pro v1.3.0 source code deep-dive: Hunter method, chi-squared+FDR, baseline construction, and comparison with original msisensor.

---

## Path Matching Utilities

Two-phase matching pattern for resolving sample/task IDs to file paths: regex full component match first, substring fallback if no exact match. See `references/path-matching-utilities.md` for implementation templates and pitfalls.

---

## Scientific Plotting Patterns

Refactor and author Python scientific plotting scripts — multi-format output, proper typing, unified CLI, NumPy docstrings, significance brackets. For general matplotlib plotting patterns used across bioinformatics workflows.

### Multi-Format Output

Use `PlotFormat = Literal["png", "pdf", "svg", ...]` type alias. CLI: `-f`/`--format` with `action="append"`.

**Pitfall**: Short-flag collision when retrofitting — reassign old `-f` first.

### Container Environment (Cromwell, Docker)

Set env vars BEFORE matplotlib import:
```python
_tmp_cache = os.path.join(os.environ.get("TMPDIR", "/tmp"), "matplotlib_cache")
os.environ.setdefault("MPLCONFIGDIR", _tmp_cache)
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Parallel Plotting

**Always ProcessPoolExecutor, never ThreadPoolExecutor** — GIL prevents Python parallelism; SQLite (gffutils) is not thread-safe. `create_db()` must be inside worker function.

**Container OOM**: `os.fork()` can hang in background thread. Use `map_async` with timeout + sequential fallback.

### Significance Brackets (宝盖头 Style)

Horizontal line from bar1 to bar2 center, with OUTWARD diagonal ticks `\` and `/`. Draw as SINGLE polyline. Store ALL pairs including `ns`. Reset `bracket_offset` per SV type, not globally.

### Curve Smoothing for Asymptotic Data

When pchip produces visible plateaus near ceiling (e.g. sensitivity→1.0), use `log(1-y)` asymptotic transform:
```python
z = -np.log(1.0 - np.clip(y, eps, 1.0 - eps))
z_new = PchipInterpolator(x, z)(x_new)
model/{site_name}/                 # per-locus XGBoost models
```

## Anomaly Detection for MSI-H

When labeled MSI-H samples are scarce, anomaly detection trains only on MSS samples and flags deviations.

### Mahalanobis Distance (No sklearn)

```python
class MahalanobisDetector:
    def fit(self, X_mss, n_sigma=3):
        self.mean_ = np.mean(X_mss, axis=0)
        cov = np.cov(X_mss, rowvar=False) + np.eye(n) * 1e-6
        self.cov_inv_ = np.linalg.inv(cov)
        dists = [mahalanobis(x, self.mean_, self.cov_inv_) for x in X_mss]
        self.threshold_ = np.mean(dists) + n_sigma * np.std(dists)
```

**Relationship to Gaussian**: Mahalanobis distance = negative log-likelihood under multivariate Gaussian. `d²(x) = -2 log p(x) + const`.

### ROC from Scratch

```python
from scipy.integrate import trapezoid
sorted_idx = np.argsort(scores)[::-1]
tps = np.cumsum(y_true[sorted_idx])
fps = np.cumsum(1 - y_true[sorted_idx])
tpr = np.concatenate([[0], tps / tps[-1]])
fpr = np.concatenate([[0], fps / fps[-1]])
roc_auc = trapezoid(tpr, fpr)
```

### Key Finding

Coverage features (mean_coverage, std_coverage) dominate Mahalanobis distance, masking MSI signal. **Remove coverage features**, keep only pro_p/pro_q-derived features.

## Cancer Type Stratification

| Cancer | n | MSI-H mean | MSS mean | AUC | Threshold |
|--------|---|-----------|----------|-----|-----------|
| CRC | 422 | 14.09% | 6.56% | 0.969 | 8.39% |
| Endometrial | 130 | 9.47% | 6.46% | 0.912 | 7.24% |

MSS baseline ~6.5% across cancer types. MSI-H signal varies → different thresholds needed.

## Large-Scale File Processing

```python
# FAST: os.scandir() for 5000+ files
for entry in os.scandir(result_dir): ...

# SLOW: glob.glob() may timeout on NFS
```

**Performance**: 100 site.txt ≈ 2-6s, 8000 files ≈ 400-500s.

### Key Pitfalls

- **`ax.legend()` does NOT accept `alpha`** — use `framealpha`.
- **ns color MUST be black** (same as stars) — distinguish by fontsize (12 vs 9) and weight.
- **Never add threshold values to x-ticks** — use `ax.annotate` with leader line below axis.
- **`os.environ.setdefault()`** so callers can override; use `TMPDIR` not hardcoded `/tmp`.

See `references/python-scientific-plotting-detail.md` for full conventions, `references/asymptotic-smoothing.md` for transform details.
