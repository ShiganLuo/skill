# Projection Analysis: Stem Cells onto Developmental Trajectory

## When to use

When clustering fails to map stem cells to expected developmental stages, use projection analysis to directly test stem cell → stage mapping without being affected by batch effects in clustering.

## Method

### Step 1: Compute stage profiles

For each embryo stage, compute mean expression profile:

```python
def compute_stage_profiles(log2_df, sample_names, group_map, dev_order):
    profiles = {}
    for stage in dev_order:
        stage_samples = [s for s in sample_names if assign_group(s, group_map) == stage]
        if stage_samples:
            profiles[stage] = log2_df[stage_samples].mean(axis=1)
    return profiles
```

### Step 2: Compute correlation matrix

For each stem cell sample, compute Pearson correlation with each stage profile:

```python
def compute_correlation_matrix(log2_df, sample_names, group_map, stem_cells, dev_order):
    stage_profiles = compute_stage_profiles(log2_df, sample_names, group_map, dev_order)
    stem_samples = [s for s in sample_names if assign_group(s, group_map) in stem_cells]
    
    corr_matrix = pd.DataFrame(index=stem_samples, columns=dev_order, dtype=float)
    for stem in stem_samples:
        stem_expr = log2_df[stem]
        for stage in dev_order:
            if stage in stage_profiles:
                corr, _ = pearsonr(stem_expr, stage_profiles[stage])
                corr_matrix.loc[stem, stage] = corr
    return corr_matrix
```

### Step 3: Visualize

Four types of visualizations:

1. **Heatmap** - correlation matrix with samples × stages
2. **Grouped barplot** - per stem cell type, show correlation with all stages
3. **PCA projection** - stem cells projected onto embryo trajectory in PCA space
4. **Radar plot** - correlation profile of each stem cell across all stages

## Expected results

For the Totipotent20251031 project:

### Human
- hESC → Blastocyst (r=0.73) ✓
- hTBLC → Blastocyst (r=0.68) ✗ (expected: 2-4 cell)
- ci8CLC → Blastocyst (r=0.76) ✗ (expected: 8-cell)
- prEpiSC → Blastocyst (r=0.78) ✓

### Mouse
- mESC → Early-blastocyst (r=0.77) ✓ (E3.5 ICM)
- TLSC → Early-blastocyst (r=0.73) ✗ (expected: 2-cell)
- ciTotiSC → Early-blastocyst (r=0.75) ✗ (expected: 2-cell)

## Limitations

- Correlation with stage profiles doesn't account for batch effects
- In vitro expression patterns dominate over stage-specific signals
- TPM vs counts doesn't significantly change results
- May need DEG-based approach for better discrimination

## Script

Located at: `/data/pub/zhousha/Totipotent20251031/workflow/Omics/src/cluster/totipotency_projection.py`

Generates:
- `human_GRCh38_heatmap.png`
- `human_GRCh38_barplot.png`
- `human_GRCh38_pca_projection.png`
- `human_GRCh38_radar.png`
- Same for mouse
