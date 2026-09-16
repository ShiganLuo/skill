# PCA Auto-Detection: detect_n_pcs (方案C: Relative Change + Stability)

## Current Implementation (scRNAseq.py detect_n_pcs)

The pipeline uses **relative change rate + sliding window stability** to find where the variance ratio curve reaches the noise floor.

### Algorithm

1. Compute per-PC relative change: `rel_change = abs(diff(vr) / vr[:-1])` (percentage drop from each PC to the next)
2. Slide a window of size `window` (default 5) from `min_pcs` onward
3. At each position, compute **median** and **std** of relative change inside the window
4. A window is "plateau" when BOTH conditions hold:
   - `median(rel_change) < rel_threshold` (default 0.05 = 5% per PC) — already flat
   - `std(rel_change) < std_threshold` (default 0.03 = 3pp) — no longer fluctuating
5. The first position where `require_n` (default 2) consecutive windows are all "plateau" marks the elbow

### Function Signature

```python
def detect_n_pcs(
    variance_ratio: np.ndarray,
    min_pcs: int = 10,
    max_pcs: int = 100,
    window: int = 5,
    rel_threshold: float = 0.05,
    std_threshold: float = 0.03,
    require_n: int = 2,
) -> Tuple[int, Dict]:
```

Returns `(recommended_n_pcs, diagnostics_dict)` where diagnostics contains:
- `delta`: raw relative change array
- `window_mean_x`, `window_mean_y`: sliding window median positions
- `window_std_y`: sliding window std values
- `threshold`, `std_threshold`: detection thresholds
- `elbow_pc`: detected elbow PC index

### Known Issue: Sensitivity to Single-PC Spikes

A single PC with unusual variance (spike in relative change) can reset the consecutive counter, causing premature plateau detection. Example: if PC13→14 has rel_change=0.16 while others are 0.02-0.06, the counter resets and n_pcs=15 is detected even though PCs beyond 15 still carry signal.

**Potential fix**: Smooth rel_change with a rolling median before detection, or use the window's own median/std to filter spikes.

## Auto-Detection Default

`auto_n_pcs` defaults to **True** (changed from False). CLI flag `--auto-n-pcs` is default-enabled; use `--no-auto-n-pcs` to disable.

**User correction**: "n_pcs是自动决定的，不是说数量越多越好" — n_pcs is auto-determined, not "more is better".

## Visualization — Two-Subplot PCA Variance Plot

When `auto_n_pcs=True`, `plot_pca_variance()` generates TWO subplots:
- **Left**: scree plot (variance ratio per PC), each point labeled PC1..PCn, red dashed line at selected n_pcs
- **Right**: per-PC relative change curve (%), sliding window median overlay, threshold line, elbow marker

When `auto_n_pcs=False`, single scree plot with red line at selected n_pcs.

**CRITICAL**: `detect_n_pcs()` MUST return `(n_pcs, diagnostics_dict)` — never just the number. The dict is required for the right subplot. See Pitfall 51 (mode_auto discarding detect_diag).

## Legacy Methods (Not Currently Used)

The following methods were previously considered but are NOT in the current implementation:

1. **cumvar** — cumulative variance reaches 85%. Standard single-cell practice but doesn't distinguish signal/noise boundary precisely.
2. **plateau** — first PC where absolute delta drops below dynamic threshold. Sensitive to baseline calculation.
3. **curvature** — maximum second derivative (elbow). Assumes clear inflection point; fails on smooth curves.
4. **sliding_window (simple)** — mean delta < baseline * ratio. Less robust than the current dual-condition (median + std) approach.

## Full-Stack Parameter Addition

When adding parameters to the pipeline, update ALL layers:

1. `modules/scanpy/scanpy.json` — add under `cluster`
2. `config/scRNAseq.json` — add to ALL counter sections (scTE, cellranger)
3. `config/scRNAseq.schema.json` — add to ALL 3 cluster schema definitions
4. `modules/scanpy/scanpy.smk` — add to params lambda + CLI passing
5. `modules/scanpy/bin/scRNAseq.py` — add argparse, function signature, dispatch call

**Pitfall**: scRNAseq.json has MULTIPLE counter sections (scTE, cellranger). Schema has 3 cluster definitions. All must be updated.
