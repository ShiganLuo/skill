# RNA degradation QC for bulk RNA-seq sample outliers

Concrete recipe for the long-gene artifact check (step 4b of SKILL.md). Use the project's pandas-capable python; featureCounts TSV + gene_map pickle provide gene lengths.

## 1. Per-sample alignment metrics

Glob `common/<stage>/<genome>/<sample>/<sample>.Log.final.out` (stage = the BAM that fed featureCounts). Parse the `|`-delimited key/values:

```python
stats[k.strip()] = v.strip()
# Number of input reads, Uniquely mapped reads %, % of reads mapped to multiple loci,
# Average insert size
```

Degradation signature: one sample at ~67% unique / ~16% multi while peers sit ~90% / ~4%, insert size a few bp short, depth normal.

## 2. Length-vs-deviation test (decisive)

```python
lx = np.log2(tpm + 1)                       # genes x samples
d = lx[sample] - lx[peers].mean(axis=1)     # peers = healthy replicates of same class
from scipy.stats import spearmanr
rho = spearmanr(gene_length, d)             # healthy ~ -0.02; degraded ~ -0.35
```

Also bin genes into length deciles and show mean deviation per decile — degradation is monotone (shortest ~ -0.2, longest ~ -1.5). Always run a healthy replicate as control; the control's near-zero slope proves the method, not the sample, creates the effect.

Gene lengths: `pd.read_csv(featureCounts_tsv, sep='\t', index_col='Geneid', usecols=['Geneid','Length'])`, map gene_id->gene_name via the project's gene_map pickle, groupby gene_name median. Dedupe both indexes (`groupby(level=0).mean()`) before concat — duplicate gene_name rows make pandas concat raise.

Pitfall — gene_map pickle structure: it is a dict `{'signature': ..., 'gene_map': {...}}`, not a flat map — read `['gene_map']`. Its keys are VERSIONED gene_ids (e.g. `ENSMUSG00000051951.6`) matching featureCounts `Geneid` exactly, so do NOT strip the version suffix before mapping; stripping silently maps nothing and you analyze 0 genes.

Pitfall — STAR log values carry a trailing `%` (e.g. `'83.37%'`); `rstrip('%')` before float().

## 3. Per-gene-set residual

```python
b, a = np.polyfit(np.log10(df['Length']), df['d'], 1)
df['resid'] = df['d'] - (a + b * np.log10(df['Length']))
per_set = df.loc[set_genes, 'resid'].mean()  # compare with raw mean d
```

Degradation bias is monotone but NOT linear in log-length (short genes flat, long genes plunge), so a linear fit under-corrects. Add a nonparametric decile correction alongside it and report both: subtract the genome-wide mean deviation of the gene's length decile. A set that still shrinks under linear correction can drop further under decile correction — cite the larger number.

Interpretation: the fraction of collapse explained by length varies widely (28-100% per set across two real cases). A partial percentage does NOT weaken the artifact verdict when (a) the length-decile profile is monotone, and (b) the collapse pattern tracks gene length — include each set's median gene length in the residual table; collapsed sets should be long-gene-rich (median 2.5-3.5 kb) while unaffected sets are short (1.3-2.1 kb). That 'long sets collapse, short sets don't' split is itself degradation evidence, independent of the residual size.

The reference interpretation from a real case: sets with raw d of -1.0 to -1.3 (ATR stress, HDR, MMR, NER, FA, spindle checkpoint, TLS) shrank to residuals of -0.4 to +0.03 — 75-100% of the collapse was length bias. Expect less under linear correction alone.

## 4. BAM 5'/3' confirmation

```bash
samtools depth -a -r chrX:start-end sample.bam   # mean per window
```

Window the gene body into 10-30% / 40-60% / 70-90% of its span (skip UTR edges). Compare across samples: long genes lose the 5' third (TLSC2/healthy ~ 0.27) while short housekeeping controls keep it (~1.1); 3'/5' ratio per gene blows out versus replicates (e.g. Tert 9.1 vs 1.6).

## 5. Reporting

- Established: metrics + rho + residual table (the artifact exists).
- Ruled out: pathway biology for the collapsed sets (residuals ~0).
- Unresolved: small residual core-gene depression (-0.25 in the case above) — note as uninterpretable on a degraded library; do not build a story on it.
- Action: exclude the sample from z-scored cross-sample figures, or re-extract RNA / rebuild the library (check Bioanalyzer trace).
- Evidence phrasing: lead with the monotone decile profile (the trend), not the coefficient; name correlation strength honestly — |rho| 0.2-0.4 is "moderate", not "strong", and the healthy control's rho is never exactly 0 (genome-wide length structure contributes a baseline negative), so present the sample-vs-control CONTRAST as the evidence, not either rho alone.

Deliverables (user requirement — the verdict alone is not enough):
- A written report file IN THE OUTPUT DIR with methods (the three tests, in order) + tiered conclusions + file list, so the analysis is reproducible without re-reading the script.
- An evidence figure: length-decile deviation bars (sample vs healthy control) + per-set raw-vs-residual bars.
- Ready-to-paste paper prose that weaves the exclusion into the main result paragraph in the order: main result -> anomaly -> decisive evidence (pick the 3 strongest numbers: mapping %, rho, corrected residual) -> exclusion decision. State it once in Results; do not re-explain in Discussion.

Figure/table label rule: pathway names must match the project's display convention (the plot script's REACTOME_-id -> human-style label mapping), never raw GMT ids or truncated labels. Truncating a name to fit (`[:28]`) is a label bug, not a label — wrap long names onto two lines instead.