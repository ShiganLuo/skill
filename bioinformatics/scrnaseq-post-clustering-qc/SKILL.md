---
name: "scrnaseq-post-clustering-qc"
description: "Post-clustering QC: filter cells, detect doublets."
license: "CC-BY-4.0"
---

# Post-Clustering Quality Control for scRNA-seq

## Overview

Post-clustering QC identifies and filters low-quality cells AFTER clustering, using cluster-level context to make better filtering decisions.

**Key principle:** Cluster before filtering. Clustering provides biological context — a cell with 800 genes might be fine in a healthy cluster but suspicious if it clusters with cells whose markers are mostly unannotated genes.

**Critical user correction:** Never remove entire clusters. Always filter individual cells within flagged clusters.

## When to Use

- Cluster markers are mostly ENSMMUG (unannotated) or MT genes
- A cluster has unusually low gene count/UMI compared to others
- A cell type appears split into distant UMAP populations
- Mixed marker expression suggests doublets
- Top markers are ribosomal genes (RPS/RPL) — ribosomal RNA contamination

## Full Workflow (7 Steps)

```
1. Cluster (scRNAseq.py --mode cluster)
2. Analyze cluster quality → flag suspicious clusters
3. Cell-level filtering within flagged clusters
4. Re-cluster filtered data
5. Check doublet-like clusters (co-expression analysis)
6. Remove doublets if confirmed
7. Re-cluster and re-annotate
```

**Important:** After ANY cell removal, MUST re-cluster. Cluster IDs change after re-clustering, so always re-annotate too.

## Step 1: Identify Suspicious Clusters

| Metric | Threshold | Flag |
|--------|-----------|------|
| Mean genes per cell | < 800 | low_genes |
| Mean UMI per cell | < 3000 | low_counts |
| % ENSMMUG in top N markers | > 50% | high_unannotated |
| % MT genes in top N markers | > 30% | high_mt_genes |
| Top markers are RPS/RPL genes | — | ribosomal_contamination |

## Step 2: Filter Individual Cells in Flagged Clusters

**Do NOT remove entire clusters.** For flagged clusters, apply cell-level QC. For non-flagged clusters, keep all cells.

```python
def filter_cells_in_flagged_clusters(adata, flagged_clusters, cluster_key="leiden"):
    keep_mask = pd.Series(True, index=adata.obs.index)
    for cluster in flagged_clusters:
        cluster_mask = adata.obs[cluster_key] == cluster
        cluster_cells = adata.obs[cluster_mask]
        cell_qc_mask = (
            (cluster_cells["n_genes_by_counts"] >= 800)
            & (cluster_cells["total_counts"] >= 3000)
            & (cluster_cells["pct_counts_mt"] <= 20.0)
        )
        cells_to_remove = cluster_cells[~cell_qc_mask].index
        keep_mask[cells_to_remove] = False
    return adata[keep_mask].copy()
```

## Step 3: Detect Doublets via Co-expression

If a cluster expresses markers from TWO different cell types, it may contain doublets OR a transitional state.

```python
# Check co-expression
sm_expr = adata.raw[cluster_mask, ["MYH11", "ACTA2", "TAGLN"]].X.toarray().mean(axis=1)
stromal_expr = adata.raw[cluster_mask, ["DCN", "SFRP4", "FBLN1"]].X.toarray().mean(axis=1)
co_expr_mask = (sm_expr >= 2) & (stromal_expr >= 2)

# Validate with doublet scores
co_expr_doublet_score = adata.obs[cluster_mask][co_expr_mask]["doublet_score"].mean()
# If higher than non-co-expressing cells → likely doublets
```

### Critical: Doublet vs Transitional State vs Myofibroblast

| Co-expression | Doublet Score | Interpretation | Action |
|---------------|---------------|----------------|--------|
| High (>10%) | High (>0.1) | Likely doublets | Remove |
| High (>10%) | Low (<0.05) | Transitional state or subtype | Keep |
| Low (<5%) | High (>0.1) | Random doublets | Remove high-score cells |

**Do NOT remove cells just because of co-expression if doublet score is low.** This was a key lesson — the user corrected this contradiction.

### Myofibroblast Identification

Myofibroblasts (MFCs) express BOTH smooth muscle and stromal markers:
- SM markers: ACTA2, MYH11, TAGLN
- Stromal markers: DCN, SFRP1, IGFBP5, COL1A1

**Key distinction from doublets:**
- Doublet score is LOW (<0.05) — not doublets
- PCA/UMAP distance closer to Stromal than Smooth_muscle
- Literature: PMC 2024, mouse ovary mesenchymal cell subtypes

**annotate_all.py markers:** `ACTA2, MYH11, TAGLN, POSTN, IGFBP5, SFRP1`

**Problem:** Automatic annotation often fails because markers overlap with Smooth_muscle. Use `--manual-annotation` to override.

## Step 4: Validate with PCA Distances

**Critical:** UMAP distances can be misleading. Always check PCA distances.

```python
pca_coords = adata.obsm["X_pca_harmony"]
center1 = pca_coords[mask1].mean(axis=0)
center2 = pca_coords[mask2].mean(axis=0)
pca_dist = np.sqrt(np.sum((center1 - center2)**2))
```

## Step 5: Re-cluster After Filtering

### Save RAW Counts, Not Processed Data

```python
# CORRECT: Save raw counts from original merged file
adata_raw = ad.read_h5ad("merged.h5ad")
adata_raw_filtered = adata_raw[filtered_cell_indices].copy()
adata_raw_filtered.write_h5ad("filtered.h5ad")
```

**Why:** scRNAseq.py expects raw counts. Processed data causes "Bin edges must be unique" error.

### anndata Nullable Strings Error

If you get `RuntimeError: anndata.settings.allow_write_nullable_strings is None`, add at top of script:

```python
import anndata as ad
ad.settings.allow_write_nullable_strings = True
```

## Step 6: Re-annotate

Use `annotate_all.py` for annotation. Input filename must contain `_clustered.h5ad` for output to work correctly.

```bash
# If your file is named differently, copy with correct suffix
cp clustered_v2.h5ad v2_clustered.h5ad
python annotate_all.py --input v2_clustered.h5ad --tissue hystera --counter cellranger
```

### Manual Annotation Override

When automatic annotation fails (e.g., marker overlap between cell types), use `--manual-annotation`:

```bash
python annotate_all.py --input clustered.h5ad --tissue ovaries --counter cellranger \
    --manual-annotation '{"2":"Myofibroblast","13":"Smooth_muscle"}'
```

**When to use:**
- Cell types share markers (Myofibroblast vs Smooth_muscle share ACTA2, MYH11, TAGLN)
- Automatic scoring can't distinguish cell types
- You have strong biological evidence for a specific annotation

**Workflow:** Run automatic annotation first, then override specific clusters.

## TE-Dominated Clusters (scTE-specific)

In scTE data, some clusters are dominated by transposable element expression (ERVK_high, Alu_high).

### Identification
- Top markers are TE elements (MacERVK2, AluSz, etc.)
- Gene count and UMI may be normal
- Does NOT match any known cell type

### Handling
- Keep as ERVK_high/Alu_high — do NOT assign cell type names
- Check sample distribution — if biased (>70% from one sample), may indicate technical issues
- Do NOT manually annotate without strong evidence

### Higher Resolution Clustering for TE Clusters

TE-dominated clusters may contain multiple cell types that got grouped together because of high TE expression. Use higher resolution to split them:

```bash
# Use resolution=1.5 instead of default 0.8
python scRNAseq.py --mode cluster --input filtered.h5ad --output clustered.h5ad \
    --resolution 1.5 --n-pcs 50 --n-neighbors 50 --batch-method harmony
```

**When to use:** When TE clusters are >20% of total cells and you suspect they contain multiple cell types.

### Sample Distribution Analysis
```python
for ct in ['ERVK_high', 'Alu_high']:
    mask = adata.obs['cell_type'] == ct
    print(adata.obs[mask]['sample_id'].value_counts())
```

If heavily biased (>70% from one sample), may indicate sample-specific technical issues.

## Lymphatic vs Blood Endothelial

Endothelial populations often split into two distant clusters:

| Type | Markers | Function |
|------|---------|----------|
| Lymphatic | MMRN1, CCL21, PROX1, LYVE1, PDPN | Lymphatic vessels |
| Blood | VWF, ERG, KDR, FLT1, EMCN | Blood vessels |

This is biologically meaningful — always annotate separately.

## Differential Abundance Analysis (Comparing Cell Composition Between Samples)

When comparing cell type proportions between samples (e.g., different conditions, timepoints), use statistical tests instead of just comparing percentages.

### Method: Chi-square Test + Standardized Residuals

**Why this method:** Chi-square test detects overall composition differences. Standardized residuals identify which specific cell types contribute most to the difference.

```python
import numpy as np
from scipy import stats

# Create contingency table
contingency = []
for ct in cell_types:
    row = []
    for sample in samples:
        n = ((adata.obs['cell_type'] == ct) & (adata.obs['sample_id'] == sample)).sum()
        row.append(n)
    contingency.append(row)
contingency = np.array(contingency)

# Chi-square test
chi2, p, dof, expected = stats.chi2_contingency(contingency)
print(f'Chi-square: {chi2:.2f}, p-value: {p:.2e}')

# Standardized residuals (significant if |z| > 2)
std_residuals = (contingency - expected) / np.sqrt(expected)

# Fisher's exact test for individual cell types
for i, ct in enumerate(cell_types):
    table = np.array([[contingency[i, 0], contingency[:, 0].sum() - contingency[i, 0]],
                      [contingency[i, 1], contingency[:, 1].sum() - contingency[i, 1]]])
    _, pval = stats.fisher_exact(table)
    fc = (contingency[i, 1] / contingency[:, 1].sum()) / (contingency[i, 0] / contingency[:, 0].sum())
    log2fc = np.log2(fc)
    print(f'{ct}: FC={fc:.2f}, log2FC={log2fc:.2f}, p={pval:.2e}')
```

### Gold Standard: Milo (Nature Biotechnology 2022)

**Milo** is the most widely recognized method for differential abundance analysis in single-cell data. It's based on KNN graphs and tests changes in cell abundance across neighborhoods.

**Advantages over simple proportion comparison:**
- Considers cell transcriptomic similarity (not just cell type labels)
- Higher statistical power
- Can detect subtle composition changes
- Can discover new cell states

**R package:** `miloR`

**When to use:** For publication-quality analysis, especially when comparing conditions/treatments.

### Visualization: Heatmap of Changes

```python
# Create heatmap of cell type proportion changes
changes = []
for comp_name, ct1, ct2 in comparisons:
    changes.append([ct2.get(ct, 0) - ct1.get(ct, 0) for ct in all_cts])
changes = np.array(changes)

fig, ax = plt.subplots(figsize=(14, 5))
im = ax.imshow(changes, cmap="RdBu_r", aspect="auto", vmin=-30, vmax=30)
# Add annotations, labels, colorbar
```

### Key Metrics to Report

| Metric | Description |
|--------|-------------|
| Chi-square p-value | Overall composition difference |
| Standardized residual | Which cell types contribute most (|z| > 2) |
| Fold change | Magnitude of change per cell type |
| Fisher's exact p-value | Significance per cell type |

## Common Pitfalls

1. **Removing entire clusters** — filter individual cells instead
2. **Saving processed data** — always save raw counts for re-clustering
3. **Trusting UMAP distances** — check PCA distances
4. **Not checking co-expression** — mixed markers might be doublets
5. **Forgetting to re-annotate** — cluster IDs change after re-clustering
6. **Removing cells based on co-expression alone** — check doublet score first
7. **Not re-clustering after cell removal** — MUST re-cluster after any filtering
8. **annotate_all.py filename** — input must contain `_clustered.h5ad`
9. **Assigning cell types to TE-dominated clusters** — keep as ERVK_high/Alu_high
10. **Not checking sample distribution** — TE clusters may be sample-biased

## Differential Abundance Analysis (Comparing Cell Composition Between Samples)

When comparing cell type proportions between samples (e.g., different conditions, timepoints), use statistical tests instead of just comparing percentages.

### Method: Chi-square Test + Standardized Residuals

**Why this method:** Chi-square test detects overall composition differences. Standardized residuals identify which specific cell types contribute most to the difference.

```python
import numpy as np
from scipy import stats

# Create contingency table
contingency = []
for ct in cell_types:
    row = []
    for sample in samples:
        n = ((adata.obs['cell_type'] == ct) & (adata.obs['sample_id'] == sample)).sum()
        row.append(n)
    contingency.append(row)
contingency = np.array(contingency)

# Chi-square test
chi2, p, dof, expected = stats.chi2_contingency(contingency)
print(f'Chi-square: {chi2:.2f}, p-value: {p:.2e}')

# Standardized residuals (significant if |z| > 2)
std_residuals = (contingency - expected) / np.sqrt(expected)

# Fisher's exact test for individual cell types
for i, ct in enumerate(cell_types):
    table = np.array([[contingency[i, 0], contingency[:, 0].sum() - contingency[i, 0]],
                      [contingency[i, 1], contingency[:, 1].sum() - contingency[i, 1]]])
    _, pval = stats.fisher_exact(table)
    fc = (contingency[i, 1] / contingency[:, 1].sum()) / (contingency[i, 0] / contingency[:, 0].sum())
    log2fc = np.log2(fc)
    print(f'{ct}: FC={fc:.2f}, log2FC={log2fc:.2f}, p={pval:.2e}')
```

### Handling Zero-Frequency Cell Types

When a cell type is absent in one sample, add a small pseudocount to avoid zeros in chi-square test:

```python
# Add pseudocount to avoid zeros
contingency = contingency + 0.5
```

### Gold Standard: Milo (Nature Biotechnology 2022)

**Milo** is the most widely recognized method for differential abundance analysis in single-cell data. It's based on KNN graphs and tests changes in cell abundance across neighborhoods.

**Advantages over simple proportion comparison:**
- Considers cell transcriptomic similarity (not just cell type labels)
- Higher statistical power
- Can detect subtle composition changes
- Can discover new cell states

**R package:** `miloR`

**When to use:** For publication-quality analysis, especially when comparing conditions/treatments.

### Visualization: Heatmap of Changes

```python
# Create heatmap of cell type proportion changes
changes = []
for comp_name, ct1, ct2 in comparisons:
    changes.append([ct2.get(ct, 0) - ct1.get(ct, 0) for ct in all_cts])
changes = np.array(changes)

fig, ax = plt.subplots(figsize=(14, 5))
im = ax.imshow(changes, cmap="RdBu_r", aspect="auto", vmin=-30, vmax=30)
# Add annotations, labels, colorbar
```

### Key Metrics to Report

| Metric | Description |
|--------|-------------|
| Chi-square p-value | Overall composition difference |
| Standardized residual | Which cell types contribute most (|z| > 2) |
| Fold change | Magnitude of change per cell type |
| Fisher's exact p-value | Significance per cell type |

## New Cell Type Markers (Validated)

These markers were validated in this session for macaque reproductive tissues:

### Myofibroblast (SM+Stromal hybrid)
- Markers: `ACTA2, MYH11, TAGLN, POSTN, IGFBP5, SFRP1`
- Key feature: PCA distance closer to Stromal than Smooth_muscle
- Doublet score LOW (<0.05) — NOT doublets
- Literature: PMC 2024, mouse ovary mesenchymal cell subtypes
- **Problem:** Automatic annotation fails because markers overlap with Smooth_muscle. Use `--manual-annotation` to override.

### Lymphatic Endothelial
- Markers: `MMRN1, CCL21, PROX1, LYVE1, PDPN, CAVIN2, FLT4`
- Key feature: Separated from blood endothelial in UMAP
- Literature: Wigle & Oliver (1999) Cell PMID:10499794
- Always annotate separately from blood endothelial

### Mesothelial
- Markers: `MSLN, ITLN1, WT1, UPK3B`
- Key feature: Ovarian surface epithelium origin
- Literature: Nature 2022, Macaca fascicularis cell atlas
- **Note:** PKHD1L1 is NOT specific — also expressed in Endothelial. Use MSLN+ITLN1 as primary markers.

### Cumulus
- Markers: `FST, NR5A2, PPARG, CRHBP, GRB14, HAS2, PTX3`
- Specialized granulosa cells surrounding oocyte

### Luteal
- Markers: `STAR, CYP11A1, HSD3B1, PTCH2, GPC5`
- Corpus luteum cells, steroidogenesis

## Manual Annotation Override (annotate_all.py)

When automatic annotation fails (marker overlap between cell types), use `--manual-annotation`:

```bash
python annotate_all.py --input clustered.h5ad --tissue ovaries --counter cellranger \
    --manual-annotation '{"2":"Myofibroblast","13":"Smooth_muscle"}'
```

**When to use:**
- Cell types share markers (Myofibroblast vs Smooth_muscle share ACTA2, MYH11, TAGLN)
- Automatic scoring can't distinguish cell types
- You have strong biological evidence for a specific annotation

**Workflow:** Run automatic annotation first, then override specific clusters.

**Code fix for categorical errors:** When adding new cell types via manual annotation, must add new categories first:

```python
new_cats = set(manual_annotation.values()) - set(adata.obs["cell_type"].cat.categories)
if new_cats:
    adata.obs["cell_type"] = adata.obs["cell_type"].cat.add_categories(new_cats)
```

**annotate_all.py implementation:**
```python
# In annotate_one() function, after automatic annotation:
if manual_annotation:
    log.info("Applying manual annotations: %s", manual_annotation)
    # Add new categories if needed
    new_cats = set(manual_annotation.values()) - set(adata.obs["cell_type"].cat.categories)
    if new_cats:
        adata.obs["cell_type"] = adata.obs["cell_type"].cat.add_categories(new_cats)
    for cluster, cell_type in manual_annotation.items():
        if cluster in adata.obs["leiden"].cat.categories:
            mask = adata.obs["leiden"] == cluster
            old_ct = adata.obs.loc[mask, "cell_type"].iloc[0]
            adata.obs.loc[mask, "cell_type"] = cell_type
            n = mask.sum()
            log.info("  Cluster %s: %s -> %s (%d cells)", cluster, old_ct, cell_type, n)
    # Remove unused categories
    adata.obs["cell_type"] = adata.obs["cell_type"].cat.remove_unused_categories()
```

## User Preferences

- Don't remove entire clusters — filter individual cells
- Use existing tools (scRNAseq.py, annotate_all.py)
- Cluster provides biological context — cluster before filtering
- Save raw counts — not processed data
- PCA distances > UMAP distances
- No fallback logic — fail loudly
- Don't contradict analysis conclusions — if analysis says "not doublets", don't remove them
- Discuss design before implementing — don't rush to code
- Need literature support for new cell type annotations
- MT% filtering not always necessary (macaque data has very low MT%)
- Check sample distribution for TE-dominated clusters
- Filtering parameters vary by tissue and quantification method — don't hardcode one set
- PPT reports must include ALL datasets, marker lists, and use proper image layout
