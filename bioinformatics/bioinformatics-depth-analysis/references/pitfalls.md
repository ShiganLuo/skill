# Pitfalls in Depth Analysis

## 1. LOD model: wrong vaf_model for somatic calling

**Symptom**: `gatk_lod_sensitivity(500, 0.05, lod_threshold=3.0)` returns 0.0.

**Cause**: Default vaf_model=0.5 (germline het). At VAF=0.05 with 500x depth, observing 25 variant reads is perfectly consistent with error under the het model (expected 250 reads), so LOD is massively negative.

**Fix**: Pass `vaf_model=0.05` (or whatever the expected somatic VAF is):
```python
gatk_lod_sensitivity(500, 0.05, vaf_model=0.05)  # → 0.9999
```

The LOD model asks "does the data look like this VAF?" — if you set vaf_model=0.5, you're asking "does the data look like a het?" and 25/500 reads looks nothing like a het.

## 2. Beta-binomial overdispersion too high

**Symptom**: Sensitivity stays flat at ~0.35 regardless of depth (e.g., 500x, 5000x).

**Cause**: overdispersion=0.5 creates 251x variance inflation at n=500. The model assumes read-level error rates are wildly heterogeneous, making it impossible to distinguish signal from noise.

**Fix**: Use overdispersion=0.005 for quality-filtered clinical data:
- od=0.005: Var multiplier ≈ 1.02x → behaves like binomial with slight noise
- od=0.01: ≈ 6x → noticeable but manageable
- od=0.05: ≈ 26x → very conservative, use only for noisy data (FFPE)

The parameterization is: `α = vaf/od, β = (1-vaf)/od`. Test with:
```python
for d in [100, 500, 1000, 2000]:
    print(d, beta_binomial_sensitivity(d, 0.05, 3, od))
# Sensitivity should increase with depth. If flat, od is too high.
```

## 3. Population imputation R² "too high" at low depth

**Symptom**: R²=0.999 at 0.1x depth with 1000 samples. Seems unrealistic.

**Reality**: This is correct. GLIMPSE and BEAGLE achieve this in practice because:
- Reference panels provide strong priors from LD
- With 1000 samples, haplotype estimation is very accurate
- Even 0 reads at a site, the imputed dosage can be correct from flanking markers

Don't "fix" the model by adding artificial penalties. The model is theoretical; actual accuracy depends on reference panel quality and local recombination rate.

## 4. CLI matplotlib import scope

**Symptom**: `NameError: name 'plt' is not defined` in CLI commands.

**Fix**: Import at module top level, not inside `main()`:
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
```

Don't put matplotlib imports inside `main()` or conditional blocks — the cmd_* functions need them in scope.

## 5. required_depth_beta_binomial exceeds max_depth

**Symptom**: "Depth exceeds 1000000" for beta_binomial at low VAF.

**Cause**: With overdispersion=0.05 and VAF=0.01, the model needs >1M depth. This is the model telling you "detection is not feasible under these noise assumptions."

**Diagnostic**: Check if sensitivity improves at all with depth:
```python
for d in [100, 1000, 10000, 100000]:
    print(d, beta_binomial_sensitivity(d, 0.01, 3, 0.05))
```

If sensitivity plateaus, reduce overdispersion or accept that the model is too conservative for this VAF.

## 6. Coverage uniformity max_avg too low

**Symptom**: "Average depth exceeds 1000.0" for `required_avg_depth_for_site(1000, 0.95)`.

**Fix**: Increase max_avg to 5000:
```python
required_avg_depth_for_site(1000, 0.95, max_avg=5000)  # → 1053x
```
