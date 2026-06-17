# CNV Analysis

Analyze CNVkit output files for copy number variation detection in clinical oncology pipelines.

## CNVkit Output File Structure

A typical CNVkit run produces these files in the `tumor/` directory:

| File | Description | Key Columns |
|------|-------------|-------------|
| `*.cnr` | Bin-level log2 ratios (target + antitarget) | chromosome, start, end, gene, log2, depth, weight |
| `*.cns` | Segmented copy number calls | chromosome, start, end, gene, log2, depth, probes, weight, ci_lo, ci_hi |
| `*.targetcoverage.cnn` | Target region coverage | bin-level read counts |
| `*.antitargetcoverage.cnn` | Antitarget coverage | off-target bin counts |
| `*.call.cns` | Called CN states (after thresholding) | adds total_cn, A_cn, B_cn columns |
| `*.bintest.cns` | Per-bin significance test | significant hit bins |

### File Relationships

```
BAM → targetcoverage.cnn + antitargetcoverage.cnn
    → .cnr (GC/density corrected, reference normalized)
    → .cns (CBS segmentation)
    → .call.cns (threshold-based CN calling)
```

### Gene Column in .cns

The `gene` column in `.cns` is **comma-separated** — one segment can cover multiple genes. Parse with:
```python
genes = [g.strip() for g in row['gene'].split(',') if g.strip() and g.strip() != '-']
```

## Clinical Pipeline Directory Layout

In the OncoTOP/CNC pipeline, CNV output lives under `variation/cnv/`:

```
variation/cnv/
├── tumor/
│   ├── {sample}_cancer_dedup_realign.cnr          # bin-level ratios
│   ├── {sample}_cancer_dedup_realign.cns          # segments (81 typical)
│   ├── {sample}_cancer_dedup_realign.call.cns     # called CN states
│   ├── {sample}_cancer_dedup_realign.bintest.cns  # significant bins
│   ├── {sample}.segments.txt                      # simplified segments
│   ├── {sample}.result.tsv                        # purity/ploidy/risk summary
│   ├── {sample}_fD.log                            # CNVkit run log
│   ├── risk1.1/ risk0.8/ risk0.5/                 # risk threshold variants
│   │   ├── {sample}.segments.txt
│   │   ├── {sample}.shift.cnr                     # shifted ratios
│   │   ├── {sample}_HRDresults.txt
│   │   ├── {sample}_cnv.LOH.txt / .LST.txt / .TAI.txt
│   │   └── {sample}.model.tsv / .cal_signal.tsv
│   └── second_cns/                                # refined segments
├── {sample}.tumor.cnvkit.anno.csv                 # exon-level annotated CNV
├── {sample}.tumor.final.anno.tsv / .filter.csv    # final annotated results
├── {sample}_trendinfo.tsv / {sample}.arm.tsv      # chromosomal arm-level
├── metpolysomy/                                    # MET polysomy results
└── cnv_png/                                        # visualization PDFs
```

## Target vs Segment vs Bin: Terminology

Understanding the hierarchy is critical when interpreting questions about CNVkit:

| Concept | What it is | Typical size | Source file |
|---------|-----------|-------------|-------------|
| **Target** | A capture probe region (e.g. one exon) | 100–300 bp | `.targetcoverage.cnn` |
| **Bin** | A binned window (target or antitarget) | ~100 kb (antitarget) | `.cnr` |
| **Segment** | A CBS-merged region of similar CN | 1 Mb – 100+ Mb | `.cns` |

Key relationships:
- One **segment** covers **many targets/bins** (segment >> target).
- Segments are formed by merging adjacent bins with similar log2 ratios.
- The `probes` column in `.cns` = number of bins in that segment.

When someone asks "segment size per target", they are asking about **tool resolution** — how small can segments be in the target (capture) regions — NOT a per-gene statistical query.

## CNVkit Tool Characteristics (for Q&A)

When answering questions about CNVkit's parameters and behavior (not running analysis):

| Question | Answer |
|----------|--------|
| Uses tumor purity for classification? | No. CNVkit itself uses fixed log2 thresholds (default -1.24, 0.58). Purity is used downstream (ABSOLUTE, FACETS) to correct log2 → true CN. |
| Allele-specific? | No. Standard CNVkit outputs total CN only (log2 ratio). The `A_cn`/`B_cn` in `.call.cns` is a naive split, not true allele-specific analysis. Use FACETS/ASCAT for that. |
| SNP count for confidence? | CNVkit does NOT use SNP counts. Confidence comes from `probes` count (bins per segment) and `ci_lo`/`ci_hi` intervals. ≥10 probes is generally reliable. |
| Median segment size per target? | A tool resolution metric. For WES, minimum segment ~100 kb–1 Mb. Depends on probe density and bin size. |

## Common Analysis Patterns

### Per-Gene Median Segment Size

Compute the median segment size covering each target gene from the `.cns` file:

```python
import csv
from collections import defaultdict
import statistics

gene_segment_sizes = defaultdict(list)
with open('path/to/*.cns') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        size_kb = (int(row['end']) - int(row['start'])) / 1000
        genes = [g.strip() for g in row['gene'].split(',') if g.strip() and g.strip() != '-']
        for gene in genes:
            gene_segment_sizes[gene].append(size_kb)

results = [(gene, statistics.median(sizes), len(sizes))
           for gene, sizes in gene_segment_sizes.items()]
results.sort(key=lambda x: x[1], reverse=True)
```

**Interpretation:**
- Small median segment → high resolution CNV call (e.g. focal deletion/amplification)
- Large median segment → gene sits in a broad CN region (less specific)
- Genes sharing the same segment were called as a single CN unit

### Extracting Gene-Level CN from Annotation File

The `*.tumor.cnvkit.anno.csv` file has exon-level detail. For gene-level CN:

```python
import csv
from collections import defaultdict

gene_cn = defaultdict(list)
with open('{sample}.tumor.cnvkit.anno.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        gene = row['Gene']
        gcn = row.get('GCN', '.')
        if gene and gcn != '.':
            gene_cn[gene].append(int(gcn))

# Most common CN per gene
for gene, cns in sorted(gene_cn.items()):
    from collections import Counter
    most_common = Counter(cns).most_common(1)[0]
    print(f"{gene}: CN={most_common[0]} (n={most_common[1]}/{len(cns)} exons)")
```

### HRD Score Components

HRD results are in `tumor/risk{threshold}/{sample}_HRDresults.txt` with three components:
- **HRD-LOH**: Loss of heterozygosity segments
- **LST**: Large-scale state transitions
- **TAI**: Telomeric allelic imbalance
- **HRD-sum**: Total score (= HRD-LOH + LST + TAI)

### Purity/Ploidy/Risk Summary

From `tumor/{sample}.result.tsv`:
```
sample    purity  ploidy  shift   mse_cal  risk    risk_s  pu100  risk_th
{sample}  0.5     1.33    -0.38   0.15     1.17    0.44    0.38   1.1
```

- `risk`: combined risk score (threshold typically 1.1)
- `purity`: tumor purity estimate
- `ploidy`: estimated ploidy

## Pitfalls

7. **Tool-parameter questions vs statistical analysis**: When a user asks about "median segment sizes per target" or similar, check if they are asking about the TOOL'S CHARACTERISTICS (resolution, parameters) or requesting a STATISTICAL COMPUTATION on their data. Questions grouped with "does the caller use purity?" / "is it allele-specific?" / "how many SNPs for confidence?" are tool-property questions — answer conceptually, don't write a script. Only write analysis code when explicitly asked to compute on specific files.

8. **execute_code AF_UNIX path limit**: On this server, `execute_code` can fail with "AF_UNIX path too long" when the working directory path is very long (common in LIMS workspace paths). Workaround: use `terminal` with `python3 -c "..."` or `python3 script.py` instead of `execute_code`.

2. **Gene column is comma-separated, not tab-separated**: In `.cns` files, multiple genes in one segment are comma-separated within the single `gene` field. Do NOT split by tab expecting separate gene columns.

3. **Antitarget bins are named "Antitarget"**: The `gene` column in `.cnr` uses the literal string `Antitarget` for off-target bins. Filter these out when computing per-gene statistics.

4. **risk threshold variants**: The pipeline runs multiple risk thresholds (0.5, 0.8, 1.1). The primary results are typically in `risk1.1/`. Check `{sample}.result.tsv` for the actual risk score to determine which threshold directory is relevant.

5. **Duplicate rows in annotation CSV**: The `{sample}.tumor.cnvkit.anno.csv` can have duplicate rows for the same exon (one per splice variant annotation). Deduplicate by `(Gene, ExonStart, ExonEnd)` before counting.

6. **Empty segments file**: `tumor/{sample}.segments.txt` may be empty (header only) while the actual segments are in `tumor/risk1.1/{sample}.segments.txt`. Always check both locations.