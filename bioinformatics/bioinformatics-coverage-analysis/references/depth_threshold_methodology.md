# Depth Threshold & DepFactor Analysis Methodology

## DepFactor Concept

DepFactor = site_depth / sample_average_depth. Ratio of per-site (or per-region)
sequencing depth to the sample-wide mean. Captures systematic biases:
GC content, mappability, capture probe efficiency (WES), PCR amplification.

Typical DepFactor distributions:
- WGS: relatively uniform, 5th percentile ~0.6-0.7
- WES: long tail due to capture efficiency variation, 5th percentile ~0.3-0.4

## VAF Detection Thresholds

To detect variant allele frequency (VAF) at a given rate, the site-level depth
must meet a minimum. Classical binomial model:

| Target VAF | Min site depth (power ~80%) | Notes |
|------------|---------------------------|-------|
| 5%         | ~150x                     | Common somatic threshold |
| 2%         | ~384x                     | Low-frequency somatic |
| 1%         | ~1500x                    | ctDNA / liquid biopsy |
| 0.5%       | ~6000x                    | Ultra-sensitive |

These are theoretical minimums; practical thresholds should add a safety margin
(1.5-2x) to account for sequencing errors (~0.1-1%) and strand bias.

## Required Sample Average Depth

Formula: `sample_avg_depth = min_site_depth / depfactor_quantile`

Example (WES, 2% VAF, 5th percentile DepFactor):
  384 / 0.35 ≈ 1097x

**Caveat**: This is the most conservative estimate. The 5th percentile sites
are often in regions with inherent capture limitations (extreme GC, repeats).
Increasing sample depth does NOT improve their DepFactor — it's a chip design
constraint, not a sequencing depth issue.

## Site-Level vs Region-Level Aggregation

Site-level: individual positions (Chr, Pos). High variance, long tails.
Region-level: genomic intervals (Chr, Start, Stop). Averaging within a region
smooths out per-position noise (law of large numbers).

Region DepFactor distributions are significantly more concentrated:
- Site 5th percentile:    ~0.35 (WES)
- Region 5th percentile:  ~0.6-0.7 (WES, same data)

This makes region-level analysis more appropriate for depth planning.

## Hash-Based Deterministic Sampling

For large datasets (billions of sites × many samples), full aggregation is
memory-intensive. Hash-based sampling selects a deterministic subset:

```python
import hashlib

def hash_key(key_str: str) -> int:
    return int.from_bytes(
        hashlib.md5(key_str.encode()).digest()[:8], "little"
    )

# Keep site if hash < threshold (sample_rate * 2^64)
threshold = int(sample_rate * (2 ** 64))
if hash_key(f"{chrom}:{pos}") < threshold:
    # keep this site
```

Properties:
- Deterministic: same sites selected across all files → cross-file aggregation correct
- Uniform: MD5 gives good distribution, no positional bias
- Tunable: sample_rate=0.05 keeps 5% of sites, sufficient for distribution estimation

## Industry Standard Depth Reporting

Peers do NOT report DepFactor distributions directly. Standard practice:

| Metric | Description | Typical value |
|--------|-------------|---------------|
| Mean target coverage | Sample average depth on target regions | 500-1000x (WES) |
| On-target rate | % reads mapping to target regions | 70-90% (WES) |
| Fold enrichment | Target depth / off-target depth | 50-200x (WES) |
| Coverage uniformity | % target bases ≥ 20% of mean depth | ≥ 90% |
| % bases ≥ Nx | Choose N to look good | Context-dependent |

**Key insight**: DepFactor is an internal QC metric for depth planning.
External reports should use mean depth + coverage percentage combination.
Example: "500x mean depth, 95% target regions ≥ 100x" — both honest and competitive.

## Script Pattern: depth_threshold.py

The `depth_threshold.py` script implements:
1. Site-level aggregation: Chr, Pos, DepFactor(average)
2. Region-level aggregation: Chr, Start, Stop, DepFactor(average)
3. Hash-based sampling with configurable sample_rate
4. Violin plot with quantile threshold line
5. Parallel file I/O with ThreadPoolExecutor

Key refactoring: extract `_aggregate_files()` and `_map_to_dataframe()` as
generic helpers shared by both site and region workflows.
