# TE (Transposable Element) Overlap Analysis Patterns

## TE hierarchy levels

The TE GTF (`rmsk_TE.gtf`) has three levels in its attributes:

| Level | Attribute | Examples | Count |
|-------|-----------|----------|-------|
| class | `class_id` | LINE, SINE, LTR, DNA, Satellite | ~10 |
| family | `family_id` | L1, B2, ERV1, ERVL, Alu, MIR | ~50-100 |
| subfamily | `gene_id` | Lx2B2, B1_Mur1, B2_Mm1a, L1MdV_III | ~hundreds |

When the user says "subfamily", they mean `gene_id` (most specific). `family_id` is the middle level (what UCSC calls "family"). Use `gene_id` first, fallback to `family_id`.

## Two overlap metrics

### 1. Interval overlap (method="interval")

Fraction of each TE locus covered by peaks:
```python
te_length = gtf_end - gtf_start
overlap_start = max(peak_start, gtf_start)
overlap_end = min(peak_end, gtf_end)
overlap_length = max(0, overlap_end - overlap_start)
overlap_frac = overlap_length / te_length if te_length > 0 else 0.0
```

### 2. Peak count (method="count")

Number of unique peaks overlapping each subfamily:
```python
subfamily_peak_ids[te_subfamily].add(peak_id)  # deduplicate per peak
# Output: count of unique peaks per subfamily
```

The y-axis of the box plot MUST match the method:
- `method="interval"` → y-axis: "Overlap fraction per locus" (0-1)
- `method="count"` → y-axis: "Peak overlap count"

## Configurable parameters

Exposed through the full chain: `PeakCalling.json` → `PeakCalling.smk` → `peak_te_overlap.smk` → `plot_te_overlap.py`

```json
// PeakCalling.json → Params.peak_te_overlap
{
    "method": "count",           // "count" or "interval"
    "sort_by": "te_length",      // "te_length" (ascending) or "overlap_fraction" (descending)
    "top_n": 30                  // number of subfamilies to display
}
```

**Selection**: top N subfamilies by overlap metric (method), descending (highest overlap first).
**Display sort**: by `sort_by` parameter (default: ascending mean TE length).

## Data extraction from BED intersect

bedtools intersect `-wa -wb` produces:
- Fields 0-9: peak (narrowPeak format)
- Fields 10-18: TE GTF (chrom, source, feature, start, end, score, strand, frame, attributes)

## Reference visualization style

The standard TE overlap figure has two panels sharing x-axis (TE subfamilies):

1. **Top panel**: Line plot of mean TE length (bp) per subfamily
   - Black line, no markers
   - X-axis: subfamilies sorted by mean TE length (ascending)

2. **Bottom panel**: Grouped box plot
   - Blue = Control/Input, Orange = Treatment/IP
   - Y-axis matches method (overlap fraction or peak count)
   - Whiskers = 1.5×IQR

Layout: `gridspec_kw={"height_ratios": [1, 2]}`, `sharex=True`

## Filtering

Filter subfamilies with < 3 total loci to avoid noisy boxes. Limit to top N subfamilies by overlap metric.

## Output files per sample

- `{sample}_te_subfamily_overlap.tsv` — locus-level detail with columns:
  - `sample_id`, `te_subfamily` (gene_id), `te_class` (class_id), `te_length`, `interval_overlap_frac`, `overlap_peak_count`, `[ip_reads, input_reads]`
  - `te_class` is merged into this file (no separate class-level TSV needed)
- `{sample}_peak_te_overlap.bed` — raw bedtools intersect output
- `{sample}_peak_centric_te.tsv` — peak-centric view (te_count, te_classes, te_coverage_frac per peak)

The chart rule uses the subfamily TSV, NOT the class-level TSV.
