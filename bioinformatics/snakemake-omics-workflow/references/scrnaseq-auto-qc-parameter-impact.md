# scRNAseq Auto Mode QC Parameter Impact

Tested on macaque ovary scTE merged h5ad (19,816 cells initial) with `scRNAseq.py --mode auto`.

## Test Comparison

| Parameter | v3 (strict) | v4 (relaxed) |
|-----------|-------------|--------------|
| min_genes | 800 | 300 |
| min_counts (UMI) | 3,000 | 1,500 |
| max_pct_mt | 20 | 100 (no filter) |
| Initial resolution | 0.8 | 0.8 |
| Final cells | 15,211 | 17,528 (+15.2%) |
| Final resolution | 0.8 | 0.6 (auto-decreased) |
| Clusters (iter 1) | 19 | 19 |
| Clusters (iter 3/final) | 18 | 18 |
| Cell types | 10 | 9 |
| Unknown/Unverified | 2 clusters | 0 |

## Key Findings

### 1. MT% filter has minimal effect on ovary data
Actual MT% distribution: mean=0.15%, max=13.12%, median=0.11%. Almost all cells pass even strict MT=20 filter. The MT filter is more important for tissues with high mitochondrial content (liver, heart).

### 2. min_genes and min_counts drive cell retention
Relaxed QC (300/1500) retained 2,317 more cells than strict (800/3000). These are likely real low-UMI cells (granulosa, immune) that strict QC removes.

### 3. Orchestrator auto-decreases resolution
When relaxed QC retains more (possibly noisier) cells, the orchestrator decreased resolution from 0.8 to 0.6 to avoid over-clustering. This is adaptive behavior.

### 4. Cell type identification differs
**v3 (strict QC) identified but v4 missed:**
- Theca_cell (2,156 cells in v3)
- Pericyte (as standalone cluster)

**v4 (relaxed QC) identified but v3 missed:**
- luteal_cell (295 cells)
- lymphatic_endothelial_cell (263 cells)
- T_cell (254 cells)
- pre_granulosa_cell (replaced Granulosa_cell_mural)

**Both eliminated Unknown/Unverified in v4** — relaxed QC paradoxically produced cleaner annotations.

### 5. Resolution auto-adjustment is the key mechanism
The orchestrator's quality check lowers resolution when:
- Too many small clusters
- Poor cluster separation
- High proportion of Unknown annotations

This prevents over-clustering that strict QC + high resolution would cause.

## Recommendations

- For ovary data: min_genes=300, min_counts=1500 is sufficient (MT% is naturally low)
- For other tissues: test both strict and relaxed QC, compare cell type recovery
- Monitor orchestrator resolution changes between iterations — it's adapting to data quality
- If Theca_cell is expected but missing: check if relaxed QC merged it into fibroblast/smooth_muscle clusters

## Running the test

```bash
cd /path/to/ovaries/test
python scRNAseq.py \
    --mode auto \
    --input ovaries_scTE_merged.h5ad \
    --output ovaries_scTE_auto_test_v4.h5ad \
    --tissue ovaries \
    --resolution 0.8 \
    --max-iterations 3 \
    --min-genes 300 \
    --min-counts 1500 \
    --max-pct-mt 100.0 \
    --batch-method harmony \
    --batch-key sample_id \
    --species Mmul_10 \
    --auto-n-pcs \
    --skip-te \
    --llm-method openai \
    --llm-model mimo-v2.5-pro \
    --plot-dir plots_v4
```

Runtime: ~2h15m for 19,816 cells × 3 iterations × 18-22 clusters (LLM annotation is the bottleneck).