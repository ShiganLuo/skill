---
name: rna-seq-degradation-artifact
description: Use when a sample fakes low pathway scores in RNA-seq QC.
tags: [rna-seq, qc, degradation, gsva, bulk-rna-seq, 3prime-bias]
triggers:
  - sample shows abnormally low activity in gene-set/heatmap but biology says otherwise
  - unique mapping rate much lower than group peers
  - pathway score collapses for one sample across related pathways
  - long genes look downregulated while short genes look normal
---

# RNA-seq Degradation Artifact (Long-Gene / 3'-Bias) Diagnosis

A degraded RNA library systematically underestimates LONG genes (fragmentation plus 3'-biased capture means 5' ends of long transcripts are lost). Any gene-set score computed from such a sample will look collapsed if the set is long-gene-rich. Genome-stability / DNA-repair / chromatin sets (REACTOME telomere maintenance, HDR, NER, MMR, spindle checkpoint) are long-gene-rich, so one bad library fakes a whole "axis" of low pathway activity. Do NOT interpret it as biology until the artifact is excluded.

Real case: a totipotent-stem-cell sample showed "low telomere maintenance" vs peers; root cause was a degraded library (66.75% unique mapping vs ~90% peers), and length correction removed 75-100% of the apparent signal.

## Decision workflow (run in order)

### 1. Alignment QC — find the outlier
Parse `Log.final.out` from the STAR stage whose BAM feeds featureCounts (often stage-specific, e.g. `common/11_featureCounts_bam/<genome>/<sample>/<sample>.Log.final.out`, not `log/sample/`):

```python
# per sample: Number of input reads, Uniquely mapped reads %,
# % of reads mapped to multiple loci, % too short
```

Red flags: unique% 10-25 points below group peers, multi% 3-4x peers.
Depth alone is NOT evidence — a degraded library can still have normal depth.
Also collect: STAR `Average insert size` (degraded = shorter), Trim Galore adapter
read counts normalized per million reads (degraded = more adapter).

### 2. Gene-length vs deviation test (decisive, genome-wide)
Compute each gene's deviation of the suspect sample from the group mean, then
correlate with gene length:

```python
# dev = log2TPM[suspect] - mean(log2TPM[peers])
# spearman rho(gene Length, dev) across expressed genes (median log2TPM > 1)
```

- Healthy sample: |rho| ~ 0.02 (TLSC1 control: -0.020)
- Degraded sample: rho ~ -0.3 or stronger (real case: -0.346)
- Quantile view: mean deviation per length decile — degraded shows monotone
  decline from ~0 (shortest) to ~-1.5 log2 (longest)

Length source: featureCounts TSV `Length` column mapped to gene_name via the
pipeline's gene_id->name pickle (or GTF).

### 3. Per-gene-set length correction (quantify the artifact)
Fit `dev ~ a + b*log10(Length)`, then per gene set compare raw mean deviation
to the mean residual:

```
raw -1.2  -> residual -0.1  :  artifact explains ~100%
raw -1.0  -> residual -0.25 :  mostly artifact, small residual signal
```

Interpretation rule: if residuals are near 0, drop the sample; do NOT build
biology on the pre-correction scores.

### 4. Direct 3'-bias check on BAM (physical evidence)
For 6-8 long genes from the collapsed pathway + 6-8 SHORT housekeeping genes,
compute coverage in gene-body thirds with samtools depth:

```bash
samtools depth -a -r chr:start-end sample.bam   # mean per window: 10-30%, 40-60%, 70-90% of gene body
```

Decisive metric: mean 5'-window coverage of suspect / healthy samples,
- long-gene group ratio ~ 0.3 or lower  (5' lost)
- short-gene group ratio ~ 1.0          (preserved)

Also compare 3'/5' coverage ratio per gene: degraded sample shows ratios 2-6x
higher than peers on long genes.
Note: housekeeping controls MUST be short (Gapdh/Actb are short enough;
long TFs like Tbp are not valid controls here).

### 5. Cross-checks that discriminate artifact vs biology
| Observation | Artifact (degradation) | Real biology |
|---|---|---|
| Short marker genes (pluripotency, 2C-like: Zscan4, Dppa3, Tdpoz4) | preserved or even higher-looking | co-regulated with the pathway |
| Global sample correlation with peers | drops (long genes dominate variance) | drops coherently |
| Within-sample rank scores (GSVA KS) | can also shift | consistent |
| Multi-mapping fraction | often elevated (TE/repeat reads relatively enriched) | normal |

Watch out: high TE fraction (e.g. MERVL/MT2 up) is a genuine 2C-like state but
also inflates multi-mapping — check the TE read fraction (TEtranscripts) before
attributing multi-mapping to degradation alone. Degradation and 2C-like state
can co-exist in one sample.

## Reporting to user
- State the causal chain plainly: degraded library -> long genes underestimated -> long-gene-rich sets look collapsed.
- Give the numbers: unique%, rho, per-set raw vs residual, 5'-coverage ratio.
- Recommend: exclude sample from cross-sample normalization (mean-z, GSVA panels), re-extract RNA / re-library if material exists, and add pipeline QC (gene-body 5'/3' coverage + unique% threshold alarm).
- Explicitly retract earlier biological interpretations built on the artifact.

## Pitfalls
- STAR logs may live next to the stage BAM dir, not in `log/sample/` — glob `common/*/gen/*.Log.final.out`.
- gene_name aggregation: expression matrices converted from gene_id have duplicate names — `groupby(level=0).mean()` before concat, or pandas raises `cannot reindex on an axis with duplicate labels`.
- Length bias is intrinsic in TPM cross-sample mean-z: z-scores use cross-sample standardization, so one degraded sample shifts the peer mean for long genes; the suspect's deviation and peers' deviation are coupled — always verify with an internal control sample run through the same pipeline.
- featureCounts column name is `Geneid` (not `gene_id`); index_col="Geneid".
- Samtools may live in a specific conda env; use the absolute path.
- venv notes (this machine): project `.venv` lacks pandas — use `/home/<USER>/miniforge3/envs/DNA/bin/python` for pandas/numpy/scipy work.
