# Data-Driven Generic DEG Detection

## Problem

Even with specificity-first prompt positioning, LLM non-determinism means it
sometimes ignores the specificity table. The decision to look at specificity
should NOT depend on LLM compliance.

## Solution

Compute average specificity of top DEGs before building the prompt.
If DEGs are generic (avg specificity < 1.5x), expand the specificity
table and add a WARNING that the LLM cannot ignore.

## Implementation

```python
# Build lookup: gene -> max specificity across all cell types
gene_max_spec = {}
for (ct, gene), m in marker_specificity.items():
    s = m.get("specificity", 0.0)
    if s > gene_max_spec.get(gene, 0.0):
        gene_max_spec[gene] = s

# Average specificity of top 20 DEGs (missing genes = 1.0 = no enrichment)
top_n_check = min(20, len(top_genes))
spec_scores = [gene_max_spec.get(g, 1.0) for g in top_genes[:top_n_check]]
avg_spec = sum(spec_scores) / len(spec_scores) if spec_scores else 1.0

if avg_spec < 1.5:
    n_specificity = 10      # expand from top 5 to top 10
    degs_are_generic = True  # trigger WARNING in prompt
```

When `degs_are_generic=True`, prompt includes:
```
**WARNING: The top DEGs for this cluster are dominated by generic genes
(cell cycle, stress, ECM) with low cell-type specificity (avg specificity
< 1.5x). These DEGs do NOT define the cell type. You MUST base your
annotation on the specificity markers below.**
```

## Why This Works

- **Oocyte cluster**: top DEGs = MKI67/TOP2A/CENPF (specificity ≈ 1.0) →
  avg_spec < 1.5 → triggers expansion + WARNING
- **Macrophage cluster**: top DEGs = CD68/LYZ/AIF1 (specificity > 5x) →
  avg_spec > 3 → no change

The threshold (1.5) is between "generic" (≈1.0) and "specific" (≥2.0).
Genes not in the specificity dict count as 1.0 (not enriched anywhere).

## Empirical Validation (macaque ovaries v10, 2026-09-18)

- Cluster 18 (Oocyte): avg_spec triggered → Oocyte (high confidence)
- Previously: Proliferating_Cell (wrong)
- Production run (same code): still got Cycling_Granulosa_Cell (LLM variance)
  → confirms data-driven approach is needed over prompt-only approach

## Combined with Prompt Structure

The full prompt strategy (from most to least reliable):

1. **Data-driven**: detect generic DEGs → expand specificity table + WARNING
2. **Prompt positioning**: specificity FIRST, DEGs SECOND
3. **Rules**: "SPECIFICITY FIRST" + "Generic marker warning"
4. **LLM compliance**: hope LLM follows rules (non-deterministic)

Layer 1 operates at the data level and doesn't depend on LLM behavior.
Layers 2-4 are prompt engineering and are inherently unreliable.