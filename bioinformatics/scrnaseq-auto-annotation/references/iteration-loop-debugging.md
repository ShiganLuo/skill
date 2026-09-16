# Iteration-Loop Debugging Cheatsheet

Reference for verifying that `mode_auto` runs to completion correctly and that the
filter/break control flow is intact. Built from the v7 → v12 debugging cycle.

## Run-time expectations

A clean run with `--max-iterations 3` typically finishes in **10–20 minutes** on
macaque ovary scale (~20k cells, 18 initial clusters, M3 model):
- Step 0 tissue query: ~30s
- Step 1 cluster + harmony + DEG: ~90s per iteration
- Step 2 annotation: ~15–25s per cluster × 15–18 clusters per iteration
- Step 3 quality + separation + continuity: ~5s

Total: 2–3 iterations × 2 min setup + ~5–7 min LLM = ~13–20 min wall clock.

## How to launch as a background process

Foreground terminal will time out at 600s. Use `terminal(background=true)`:

```python
terminal(
    command="bash -c 'set -a; source /home/luosg/.hermes/.env; set +a; "
            "python /home/luosg/Data/genomeStability/workflow/Omics/modules/scanpy/bin/scRNAseq.py "
            "--mode auto --input <merged.h5ad> --output <out_dir>/out.h5ad "
            "--plot-dir <out_dir>/plots "
            "--tissue ovary --species Mmul_10 "
            "--llm-method anthropic --llm-model MiniMax-M3 "
            "--llm-api-key \"$MINIMAX_CN_API_KEY\" "
            "--llm-base-url https://api.minimaxi.com/anthropic "
            "--resolution 0.8 --max-iterations 3 --auto-n-pcs "
            "--batch-method harmony --batch-key sample_id --skip-te "
            "> <out_dir>/run.log 2>&1'",
    background=True,
)
```

Returns `session_id` (e.g. `proc_6c3cf56c742b`). The wrapper exits quickly;
the actual python process keeps running as PID 2513443 or similar.

## How to monitor

The wrapper shell exits fast (conda init noise). The real python PID is NOT the
session_id PID. Find it:

```bash
ps aux | grep scRNAseq | grep -v grep
# or
pgrep -f "scRNAseq.py --mode auto"
```

Then `tail -f <out_dir>/run.log` and check key markers:
- `AUTO ITERATION N / 3` — iteration progress
- `Cluster N (X cells): annotating...` — annotation in flight
- `WHOLE-CLUSTER removal (N cells)` — quality filter fired
- `n_removed / N cells (cell-level QC)` — cell-level filter fired
- `Iteration N complete. M cells remaining.` — filter took effect
- `All clusters clean. Saving final results.` — early-break worked
- `AUTO MODE COMPLETE` — final exit

## The 4 grep checks for a healthy run

```bash
# 1. Did iterations actually finish (no infinite loop)?
grep -c "AUTO ITERATION" run.log
# Expect: 1 to max_iterations

# 2. Did the early-break fire (the key fix signal)?
grep -E "outcome|All clusters clean|no_cells_removed" run.log
# Expect: at least one "All clusters clean" or "outcome=" line per run
# If ABSENT but "AUTO MODE COMPLETE" present → control-flow bug still active

# 3. Did whole-cluster removal actually run?
grep -E "WHOLE-CLUSTER removal|cells removed|cells remaining" run.log
# Expect: at least one line for any cluster with low quality + same-type separation

# 4. Did audit report include species?
python3 -c "
import re
with open('<out_dir>/<name>_reports/audit_report.md') as f:
    txt = f.read()
m = re.search(r'```json\n(.+?)\n```', txt, re.DOTALL)
import json
if m:
    ctx = json.loads(m.group(1))
    print('species:', ctx.get('species'))
    print('tissue:', ctx.get('tissue'))
"
# Expect: species not None, tissue matches --tissue arg
```

## The "outcome missing" diagnostic pattern

If `grep "outcome"` returns zero hits but `AUTO MODE COMPLETE` is present, the
iteration loop spun without ever reaching Step 4's `break` (or its early-break
equivalent). Symptom: every iteration ends with `Found N spatially discontinuous
clusters` → `Increasing resolution` → `continue`, and the next iteration
starts with the same data. To confirm:

```bash
grep -c "AUTO ITERATION" run.log        # matches max_iterations
grep -c "Clustering done" run.log       # matches max_iterations
grep -c "WHOLE-CLUSTER" run.log         # may be 0 if filter never ran
```

If all three show `max_iterations` and the second/third show 0 in iteration 1
(no filter despite flagged clusters existing), the early-break fix is missing.

## Environment variables to load before launching

The MiniMax credentials live in `~/.hermes/.env`, NOT exported by default:

```bash
set -a
source /home/luosg/.hermes/.env
set +a
# Now $MINIMAX_CN_API_KEY, $MINIMAX_API_KEY, $XIAOMI_API_KEY are available
```

`XIAOMI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1` was the old mimo
endpoint; `MINIMAX_API_KEY` quota may be exhausted. For M3 use
`MINIMAX_CN_API_KEY` against `https://api.minimaxi.com/anthropic`.

## Output directory layout (per run)

```
ovaries_auto_test_vN/
├── ovaries_auto_annotated_vN.h5ad     # final annotated data (~700MB)
├── ovaries_auto_annotated_vN_reports/
│   ├── annotation_report.tsv          # per-cluster annotations + flags
│   ├── references.tsv                 # PubMed citations (one per gene/cell_type)
│   ├── audit_report.md                # full iteration summary + JSON ctx
│   └── decision_log.sh                # bash-formatted decision log
├── plots/
│   ├── annotate_umap_cell_type.png     # UMAP colored by cell_type
│   ├── annotate_umap_llm_label.png     # UMAP colored by LLM-before-refinement
│   ├── annotate_deg_dotplot.png        # top markers per cluster
│   └── cluster_umap_leiden.png         # raw leiden cluster IDs
└── run.log                            # full stdout/stderr
```

## Cross-version comparison pattern

To compare two runs (e.g. v12 vs v7) cell-by-cell, the indices must align.
v12 may have fewer cells than v7 (filtering happens), so use AnnData subset:

```python
import scanpy as sc
import pandas as pd

v12 = sc.read_h5ad("ovaries_auto_test_v12/ovaries_auto_annotated_v12.h5ad")
v7  = sc.read_h5ad("ovaries_auto_test_v7/ovaries_auto_annotated_v7.h5ad")

# v12 is a subset of v7's cells
v7_subset = v7[v12.obs.index.tolist()]

mapping = pd.DataFrame({
    "v12_label": v12.obs["cell_type"].values,
    "v7_label":  v7_subset.obs["cell_type"].values,
})

with pd.option_context("display.max_columns", None, "display.width", 250):
    print(pd.crosstab(mapping["v12_label"], mapping["v7_label"]))
```

This shows where the new annotation agrees/disagrees with the baseline, per
original v7 cell type — useful for spotting systematic confusions
(e.g. Theca cells labeled as Fibroblasts, Granulosa confused with Theca).
