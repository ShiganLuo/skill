# Asymptotic Smoothing for Saturation Curves

## Problem

When data approaches a known ceiling (y→1.0 for sensitivity, y→Emax for dose-response),
standard interpolation (pchip, cubic spline) produces visible plateaus or kinks in the
high-value region. The curve should asymptotically approach the ceiling, not flatten into it.

## Solution: log(1-y) transform

Transform the problem so the asymptote maps to infinity, interpolate in that space,
then invert.

### Math

Given data points (x_i, y_i) where y ∈ [0, 1) with ceiling at 1.0:

```
z = -log(1 - y)           # maps y=0→z=0, y→1→z→+∞
z_new = PchipInterpolator(x, z)(x_new)   # interpolate in z-space
y_new = 1 - exp(-z_new)   # inverse transform
y_new = clip(y_new, 0, 1) # safety clamp
```

### Why it works

In z-space, the curve near the ceiling is approximately linear (z ≈ -log(ε) for small ε),
so pchip interpolation is smooth. The inverse transform naturally produces exponential
saturation: y = 1 - exp(-z), which is the canonical form for saturation curves.

### Implementation

```python
from scipy.interpolate import PchipInterpolator
import numpy as np

def smooth_asymptotic(x, y, x_new, eps=1e-10):
    y_clamped = np.clip(y, eps, 1.0 - eps)
    z = -np.log(1.0 - y_clamped)
    if len(x) < 4:
        z_new = np.interp(x_new, x, z)
    else:
        z_new = PchipInterpolator(x, z)(x_new)
    return np.clip(1.0 - np.exp(-z_new), 0.0, 1.0)
```

### When to use

- Sensitivity/coverage curves approaching 1.0
- Dose-response curves approaching Emax
- Growth curves approaching carrying capacity
- Any monotone curve with a known theoretical ceiling

### When NOT to use

- Data has no natural ceiling (use regular pchip or spline)
- Data is non-monotone near the ceiling (transform amplifies noise)
- y values already reach exactly 1.0 in raw data (eps clamping distorts)

### Quantitative comparison (tested)

With sparse data [100, 500, 1000, 2000, 3000, 5000] → y=[0.30, 0.85, 0.94, 0.975, 0.988, 0.995]:

| Method     | Overall max\|d²y\| | Overall var(d²y) |
|------------|-------------------|------------------|
| pchip      | 2.59e-03          | 5.66e-08         |
| asymptotic | 1.46e-03          | 4.57e-08         |

Asymptotic method has 44% lower max curvature and 19% lower variance — smoother approach to ceiling.
