# Statistical Models for Depth Analysis

## 1. Binomial (ideal baseline)

```
X ~ Binom(n, p_obs)
p_obs = VAF * (1-e) + (1-VAF) * e
Sensitivity = P(X >= min_alt)
```

When e=0, reduces to textbook `X ~ Binom(n, VAF)`.

## 2. Beta-Binomial (overdispersion)

Models heterogeneous per-read error rates. Per-read probability follows Beta(α, β):
```
α = VAF / overdispersion
β = (1-VAF) / overdispersion
X ~ BetaBinom(n, α, β)
```

### Overdispersion parameter tuning

The parameterization `α = vaf/od` means:
- od=0.005: variance multiplier ≈ 1.02x (near-binomial, realistic for QC'd data)
- od=0.01: ≈ 6x variance inflation
- od=0.05: ≈ 26x variance inflation (conservative)
- od=0.5: ≈ 251x variance inflation at n=500 (absurdly conservative)

**Use od=0.005 for clinical sequencing with quality filtering.**
**Use od=0.01-0.05 for noisier data (FFPE, low-BQ regions).**

Variance of BetaBinom(n, α, β):
```
Var[X] = n·p·(1-p)·(n(α+β+n)) / ((α+β)·(α+β+1))
```

## 3. Error-aware Binomial

Same as binomial but with e > 0 (typically 1e-3 for Q30):
```
p_obs = VAF * (1-e) + (1-VAF) * e
```

At VAF=5%, e=1e-3: p_obs=0.0495 (barely different from VAF).
At VAF=0.1%, e=1e-3: p_obs=0.001099 (error dominates — detection nearly impossible without UMI).

## 4. LOD Model (Bayesian, GATK-style)

```
H0: no variant, all variant reads are errors → p_ref = e
H1: variant present → p_var = vaf_model * (1-e) + (1-vaf_model) * e

LOD = log10[P(H1|data) / P(H0|data)]
    = (log_prior_var + log_pmf(x|p_var) - log_prior_ref - log_pmf(x|p_ref)) / ln(10)
```

### Critical: vaf_model parameter

- **Germline het**: vaf_model = 0.5
- **Germline hom-alt**: vaf_model = 1.0
- **Somatic**: vaf_model = expected somatic VAF (e.g., 0.05 for 5% tumor)

Using vaf_model=0.5 for somatic calling gives LOD≈-78 at x=25/n=500 → 0% sensitivity.
The LOD model compares observed data against the *expected* variant model — if you set vaf_model=0.5 but true VAF is 0.05, 25 variant reads look like noise, not signal.

GATK LOD thresholds: 3.0 (SNPs), 6.75 (indels).

## 5. UMI-aware Model

```
n_eff = n_molecules * (1 - p_pcr_dropout) * (1 - p_collision * n_molecules)
X ~ Binom(n_eff, VAF)
Sensitivity = P(X >= min_consensus_alt)
```

Typical parameters:
- umi_family_size: 3 (minimum reads per UMI family)
- p_pcr_dropout: 0.1
- reads_per_molecule: 5 (raw reads per consensus molecule)
- min_consensus_alt: 2

Required raw depth = n_molecules × family_size × reads_per_molecule.

## 6. Population Imputation

Imputation R² as function of per-sample depth, sample size, and MAF:

```
gl_info = depth / (1 + depth)                    # genotype likelihood info
ld_score = 10 * (1 - MAF) + 5                    # approx informative flanking SNPs
effective_n = n_samples * gl_info
geno_var = 2 * MAF * (1 - MAF)
residual_var = 1 / (effective_n * geno_var * (1 + ld_score * gl_info))
R² = max(1 - residual_var, 0)
```

Key insight: At 2x depth with 1000 samples, R²>0.99 for MAF=10%.
This is correct — GLIMPSE/BEAGLE achieve this in practice with reference panels.

## 7. Coverage Uniformity

Site-level depth ~ Poisson(avg_depth):
```
P(site_depth >= k) = 1 - CDF(k-1; λ=avg_depth)
```

At 30x average: P(site≥500) ≈ 0. Need ~537x average for P(site≥500)≥0.95.

## Monte Carlo validation

Use `monte_carlo_sensitivity(n, vaf, min_alt, error_rate, n_simulations)` to validate
any analytical model. Compares binomial draws against threshold.
