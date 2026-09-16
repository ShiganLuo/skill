# auto-n-pcs Detection: Diagnosis and Fix

## Problem

`detect_n_pcs(ratio=0.15)` returns n_pcs=10-14 for scTE (single-cell
transposable element) data. This is catastrophically low — downstream
UMAP and Leiden clustering lose most biological signal.

## Observed Values (BEFORE fix)

| Dataset | Tissue | Cells | auto-n_pcs | Expected |
|---------|--------|-------|------------|----------|
| ovaries scTE | macaque ovary | 19,816 | 11 | 25-40 |
| uterus scTE | macaque uterus | 47,464 | 10→14 | 30-50 |
| ovaries cellranger | macaque ovary | ~20K | 20-30 | 20-40 |

## Observed Values (AFTER fix)

| Dataset | auto-n_pcs (v2) | variance_ratio at elbow |
|---------|----------------|------------------------|
| ovaries scTE | 23 | 0.002092 |
| uterus scTE | 23 | 0.001778 |

## Root Cause Analysis

The old algorithm used absolute delta: `delta = abs(diff(variance_ratio))`.
The threshold was `baseline * ratio` where baseline = median of first 10 deltas.

Problem: variance_ratio decays exponentially, so delta decays with it.
The baseline (from early high-variance PCs) was much larger than the
deltas at PC 10+. Even with ratio=0.15, the threshold was too easy to
trigger on the small absolute deltas of later PCs.

**Actual data (ovaries scTE)**:
```
PC1:  0.036375   PC5:  0.009816   PC10: 0.005254
PC20: 0.002636   PC30: 0.001499   PC50: 0.000935

Old algorithm:
  delta[0:10] = [0.006534, 0.004361, 0.008953, 0.006711, 0.001242,
                 0.000612, 0.000547, 0.001317, 0.000845, 0.000697]
  baseline = median(delta[:10]) = 0.001279
  threshold = 0.001279 * 0.15 = 0.000192
  → triggers at PC13-14 (window_mean drops below 0.000192)
```

The absolute deltas at PC 10+ are tiny (~0.0001-0.0007) because the
variance_ratio itself is tiny. The threshold catches the noise floor
of the delta curve, not the noise floor of the variance curve.

## Fix: Relative Change Rate + Stability (方案C)

**Algorithm**: Instead of absolute delta, use relative change:
```python
rel_change = abs(diff(vr) / vr[:-1])  # percentage drop per PC
```

**Stopping criterion** (both must hold):
1. `median(rel_change in window) < 5%` — change rate is LOW
2. `std(rel_change in window) < 3%` — change rate is STABLE

**Why both?**
- Low alone: a single outlier PC (e.g. PC18 at 0.6%) can pull the
  mean/median below threshold while surrounding PCs are still changing
  at 5-6%. The std check prevents premature triggering.
- Stable alone: change rate could be consistently high (e.g. 10% ± 1%)
  — stable but not at the noise floor.

**Additional safeguard**: `require_n=2` — need 2 consecutive windows
satisfying both conditions. Prevents one-off false positives.

**Robustness**: Uses median (not mean) to resist outlier PCs.

## Relative Change Rate Profile (ovaries scTE)

```
PC 1→2:  18.0%    PC 5→6:  12.6%    PC10→11: 13.3%
PC15→16:  4.9%    PC20→21:  6.0%    PC30→31:  5.7%
PC40→41:  1.7%    PC50→51:  1.2%

Signal zone (PC 1-25):  fluctuates 0.6%-18%, window std > 2
Noise zone (PC 30-50):  stable 0.5%-4%, window std < 1.5
Transition (PC 25-30):  mixed
```

The algorithm correctly identifies PC23 as the elbow — the point where
relative change drops below 5% AND stabilizes.

## Implementation

```python
def detect_n_pcs(variance_ratio, min_pcs=10, max_pcs=100, window=5,
                 rel_threshold=0.05, std_threshold=0.03, require_n=2):
    rel_change = abs(diff(variance_ratio) / maximum(variance_ratio[:-1], 1e-12))
    # Slide window, check median < rel_threshold AND std < std_threshold
    # Need require_n consecutive plateau windows to confirm elbow
```

Parameters:
- `rel_threshold=0.05` (5% per PC) — "already flat"
- `std_threshold=0.03` (3 percentage points) — "no longer fluctuating"
- `require_n=2` — "not a one-off dip"
- `window=5` — same as before

## Plot Update

The right panel of the PCA variance plot now shows:
- Per-PC relative change (%) instead of absolute delta
- Window median curve (smoothed)
- Threshold line at 5%
- Elbow marker

## Diagnostic Log Signatures

**Before fix** (too low):
```
Auto-detected n_pcs: 10
Auto-detected n_pcs: 11
Auto-detected n_pcs: 14
```

**After fix** (correct):
```
Auto-detected n_pcs: 23
```