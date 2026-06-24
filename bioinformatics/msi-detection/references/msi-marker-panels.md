# MSI Detection Marker Panels

## Promega MSI Multiplex System (hg19)

5 mononucleotide loci for MSI detection + 2 pentanucleotide loci for sample ID:

| Marker   | Chr | Start      | End        | Type            | Purpose       |
|----------|-----|------------|------------|-----------------|---------------|
| BAT-25   | 4   | 55598209   | 55598333   | Mono, polyT     | MSI detection |
| BAT-26   | 2   | 47641560   | 47641619   | Mono, polyA     | MSI detection |
| NR-21    | 22  | 21168984   | 21169013   | Mono, polyA     | MSI detection |
| NR-24    | 2   | 95147995   | 95148024   | Mono, polyA     | MSI detection |
| MONO-27  | 2   | 129536247  | 129536276  | Mono, polyA     | MSI detection |
| Penta C  | 4   | 39100031   | 39100097   | Penta, control  | Sample ID     |
| Penta D  | 21  | 43636257   | 43636334   | Penta, control  | Sample ID     |

**Classification rule:** ≥2 of 5 unstable → MSI-H; 1 → MSI-L; 0 → MSS.

## NCI Standard (BETHESDA) Panel (hg19)

5 loci recommended by NCI:

| Marker    | Chr | Start      | End        | Type           |
|-----------|-----|------------|------------|----------------|
| BAT-25    | 4   | 55598209   | 55598333   | Mono, polyT    |
| BAT-26    | 2   | 47641560   | 47641619   | Mono, polyA    |
| D2S123    | 2   | 51957017   | 51957155   | Dinucleotide   |
| D5S346    | 5   | 112222871  | 112223044  | Dinucleotide   |
| D17S250   | 17  | 47417220   | 47417378   | Dinucleotide   |

Same classification rule: ≥2 unstable → MSI-H.

## 阅微六位点

Exact composition uncertain. Most likely 6 mononucleotide loci — possibly the 5 Promega markers plus NR-27 (chr2:192020620-192020653) or another mononucleotide locus. Need confirmation from product documentation or project BED file.

## Panel Comparison

| Panel | Loci | Type | Detection Method |
|-------|------|------|------------------|
| NCI Bethesda | 5 | Mono + Di | Capillary electrophoresis (PCR) |
| Promega | 5+2 | Mono + Penta | Capillary electrophoresis (PCR) |
| NGS-based | 500-1000+ | Mono (WES/WGS) | Statistical (msisensor-pro, TopMSI) |

NGS panels cover orders of magnitude more loci, enabling statistical approaches (chi-squared test, entropy-based scoring) rather than binary per-locus calls. This is why NGS-based methods can detect MSI even when PCR panels disagree — they aggregate weak signals across many loci.

## Pitfalls

1. **hg19 vs hg38 coordinates differ** — always verify which reference genome is in use
2. **BAT-25/BAT-26 near-100% instability** in MMR-deficient tumors — these are the most informative single loci
3. **Dinucleotide markers (NCI panel) less sensitive** than mononucleotide markers for MSI detection
4. **Promega Penta C/D are controls**, not MSI markers — do not count them for MSI classification
