---
name: expression-batch-clustering
description: Cluster expression matrices across studies with ComBat.
---

# When to use

- User asks to cluster expression matrices from multiple studies
- User asks about batch correction (ComBat, removeBatchEffect)
- User asks to compare samples across datasets (e.g. totipotency vs embryo stages)
- User asks about distance metrics for expression data

# Preprocessing pipeline order

Standard: filter → log2(x+1) → batch correction → z-score per gene → distance

Never reorder. Z-score before batch correction amplifies noise in low-count genes. Batch correction before log2 doesn't work (assumes additive model on raw counts).

### Top-HVG fast path (when ComBat overcorrects or QN too slow)

When ComBat overcorrects or QN is too slow on >100k genes:
1. Filter → log2(x+1) (no batch correction, no z-score yet)
2. Compute variance per gene on the full log2 matrix
3. Select top N most variable genes (N=5000 typical)
4. Z-score only the selected genes
5. Transpose → cosine distance → average linkage

This focuses on genes with real biological variation and sidesteps both batch correction artifacts and QN runtime.

# ComBat batch correction

## Implementation (pure numpy/scipy, no scanpy required)

Formula: `y_corrected = (y - gamma_star) / delta_star * sqrt(var_pooled) + grand_mean`

Where:
- gamma_star: shrunken additive batch effect (location)
- delta_star: shrunken multiplicative batch effect (scale)
- var_pooled: residual variance across all samples
- grand_mean: overall gene mean

## Pitfalls

- **When batch is perfectly confounded with biology, ComBat overcorrects even with ≥3 batches.** If all embryo samples come from one study and all stem cells from another, ComBat treats the biological group difference as a batch effect and removes it. The dendrogram will show stem cells as a completely separate cluster at maximum distance from all embryo stages. Solution: use marker gene approach or direct cosine on HVGs (no batch correction).

- **Deduplicate gene names before join.** TEcount/featureCounts output can have duplicate gene names (Y_RNA, Metazoa_SRP, rRNA entries). Joining two DataFrames with duplicate indices produces a Cartesian product — 80k × 80k → 689k rows instead of ~78k. Fix: `df = df.groupby(df.index).sum()` on each matrix before any join. Always check `df.index.has_duplicates` after loading.

- **Remove TEs before clustering.** TEcount output mixes genes and TEs. In the raw `all_TEcount.tsv`, TEs have `:` separators (e.g., `AluSx1:Alu:SINE`). The name version (`all_TEcount_name.tsv`) strips the prefix but TEs remain in the index. Filter: `te_names = {idx.split(':')[0] for idx in df_raw.index if ':' in str(idx)}`, then `df = df[~df.index.isin(te_names)]`. Use the raw file to identify TEs, apply filter to the name version.

- **Filter to protein-coding genes for cleaner signal.** lncRNAs and pseudogenes dominate PC1 loadings (LINC genes, C11orf40, etc.) and act as noise in developmental clustering. Use `geneIDAnnotation.csv` (tab-separated: gene_id, gene_name, gene_type) to filter: `pc_genes = set(ann.loc[ann['gene_type'] == 'protein_coding', 'gene_name'])`. This typically reduces PC1 variance by 10-15% and makes top PC loadings biologically meaningful.

- **Quantile normalization is O(n·m·log(m)) with pandas overhead.** On matrices with >100k genes, QN takes minutes to hours. Either filter genes first (<50k), or use the top-HVG fast path instead.

- **ComBat with only 2 batches degenerates.** When batch=study and there are exactly 2 studies, ComBat removes ALL between-study variation — including biological signal. Need ≥3 batches for shrinkage to distinguish batch from biology. Use study_id as batch label, not dataset origin.

- **Single-sample batches cause NaN.** n_b=1 → no variance estimate → division by zero. Guard: if n_b <= 1 or tau2 == 0 or var_pooled.min() == 0, skip shrinkage for that batch (use raw gamma_hat/delta_hat).

- **NaN/inf after correction.** Always `np.nan_to_num(df_out, nan=0.0, posinf=0.0, neginf=0.0)` on the output matrix before downstream use.

## Batch label design

For multi-study comparisons:
- Use `study_id` as batch (e.g. GSE185005, GSE224794, EED_embryo)
- NOT "study_A" vs "study_B" — that's only 2 batches, ComBat can't shrink
- Each study with ≥2 samples gets proper variance estimation
- Single-sample studies: assign to "other" batch, ComBat falls back to raw correction

## When ComBat fails

ComBat removes systematic differences between batches. If the biological signal IS correlated with batch structure (e.g. all totipotency samples from one study, all embryos from another), ComBat removes biology too.

### Diagnosis: biology-correlated batch structure

Check batch label distribution: if one batch contains ALL samples of one biological group (e.g. batch=EED_embryo has all embryo samples, batch=GSE224794 has all stem cells), ComBat will treat the group difference as a batch effect and remove it. The dendrogram will show overcorrection — biologically distinct groups collapse together.

### Alternatives when ComBat overcorrects (ordered by aggressiveness)

1. **PCA remove-PC1** (best for developmental mapping): log2 → top 5000 HVGs → z-score → PCA → drop PC1 → cosine distance on remaining PCs. PC1 typically captures the dominant grouping (in vitro/vivo, study effect). Removing it reveals biology in PC2+. Always plot PCA first to verify PC1 captures the expected split.
2. **Top HVGs + z-score + cosine distance** (mildest, no PCA): select top 5000 variable genes from log2 data, z-score only those genes, compute cosine distance. Focuses on genes with biological variation, sidesteps batch correction entirely.
3. Use marker genes specific to the biological question
4. Quantile normalization (QN) — equalizes value distributions across samples without removing group means. Gentler than ComBat. BUT: too slow on >100k genes. Only use after filtering to <50k genes.
5. Skip batch correction entirely — log2 + euclidean distance, accept study effect in clustering

# Default parameters for sample-level clustering

When clustering samples across multiple studies (the common case), use:
- `combat=True` (study_id as batch), `zscore=True`
- `metric="cosine"`, `method="average"` (linkage)
- `min_mean=1.0` (not 10 — aggressive filtering loses TFs and signaling genes)

Do NOT default to euclidean + ward on log2 counts — high-expression housekeeping genes dominate distance, and batch effects are uncorrected.

# Distance metrics

Supported: euclidean, maximum, manhattan, canberra, binary, minkowski, cosine

## Pitfalls

- **Ward linkage requires euclidean.** If metric != euclidean and method=ward, override metric to euclidean with warning. Use complete/average linkage for non-euclidean metrics.

- **Cosine + ward is invalid.** Ward assumes euclidean geometry. Cosine measures angle, not magnitude. Combine cosine with average or complete linkage.

- **KMeans only supports euclidean.** For non-euclidean metrics, fall back to hierarchical (average linkage).

# Debugging: clustering doesn't match biology

When dendrogram groups are biologically implausible (e.g. Oocyte clusters with 4-cell, stem cells mixed with embryo stages), check in order:

1. **Gene names deduplicated?** Duplicate gene names in index cause Cartesian product on join (80k → 689k rows). Check `df.index.has_duplicates` after loading. Fix: `df.groupby(df.index).sum()`.
2. **ComBat actually running?** Title says "ComBat" but `combat=False` (default) — verify the preprocessor parameters match the title.
3. **Z-score enabled?** Without z-score, euclidean distance is dominated by a few highly-expressed genes.
4. **min_mean too high?** Threshold >5 filters out transcription factors and signaling genes that define cell identity. Use min_mean=1.0 for sample clustering.
5. **Linkage compatible with metric?** Ward + cosine silently produces garbage. Verify method matches metric.
6. **Batch label count ≥3?** ComBat with exactly 2 batches removes all between-study variation including biology.
7. **Biology correlated with batch?** If all samples of one biological group share a batch label, ComBat overcorrects. Switch to top-HVG approach or PCA remove-PC1.
8. **In vitro vs in vivo?** If stem cells don't cluster with their modeled embryo stages, use PCA remove-PC1 approach (see domain insight section).

## Domain insight: in vitro vs in vivo transcriptomes

Stem cells (hESC, ciTotiSC, mESC, TLSC) cultured in vitro will NOT cluster with their modeled in vivo embryo stages in whole-transcriptome clustering. Culture conditions, signaling environment, and cell density create transcriptional differences that dominate over developmental stage similarities. This is biology, not a preprocessing failure.

### Direct cosine on z-scored HVGs (preferred for developmental mapping)

When the goal is to map stem cells onto embryo developmental trajectories:
1. Preprocess: remove TEs → filter protein-coding → deduplicate → filter low expression → log2(x+1)
2. Select top 5000 HVGs by variance
3. Z-score per gene
4. Cosine distance directly on the z-scored sample × gene matrix → average linkage

This preserves the full biological signal. In practice: hESC clusters nearest to Blastocyst (ICM origin), mESC near Blastocyst, ciTotiSC/TLSC near 2-8-cell (totipotent stages). Validated against pairwise cosine distances: hESC↔Blastocyst should be smallest among embryo stages.

### DEG-based gene selection (when marker genes aren't discriminating enough)

When stem cells cluster together regardless of marker genes, distance metrics, or normalization, the issue is that marker genes include many genes shared by all stem cell types (e.g., core pluripotency genes NANOG, POU5F1, SOX2). Use DEG analysis to find genes that discriminate between stem cell types.

1. Run DESeq2 for each stem cell type vs hESC (or appropriate control)
2. Select significant DEGs (padj < 0.05, |log2FC| > 1)
3. Combine DEGs from all comparisons
4. Filter expression matrix to DEGs + markers
5. log2(TPM+1) → z-score → correlation distance → average linkage

This approach successfully separated stem cell types (hESC, hTBLC, ci8CLC, prEpiSC) into distinct clusters and mapped them closer to their expected developmental stages.

### Correlation distance for developmental mapping

For mapping stem cells onto embryo developmental trajectories, correlation distance (1 - Pearson r) often outperforms cosine distance:

```python
corr = np.corrcoef(samples)  # samples: (n_samples, n_genes)
dist = np.maximum(1 - corr, 0)
# Convert to condensed form
n = dist.shape[0]
condensed = []
for i in range(n):
    for j in range(i + 1, n):
        condensed.append(dist[i, j])
dist = np.array(condensed)
```

Correlation distance measures the similarity of expression patterns (relative expression), not absolute levels. This makes it more robust to batch effects and sequencing depth differences.

### Marker gene limitation

Marker genes work well for embryo stage clustering, but fail to discriminate between stem cell types because:
- Core pluripotency genes (NANOG, POU5F1, SOX2, KLF4) are expressed in all stem cells
- In vitro culture conditions create shared expression patterns that dominate over stage-specific signals
- The marker gene list (100-200 genes) is too small to capture the full complexity of stem cell states

When marker genes fail, switch to DEG-based approach or use projection analysis to directly test stem cell → stage mapping.

### PCA remove-PC1 approach (use with caution)

PC1 captures in vitro/vivo split (40-55% variance). Removing it CAN reveal developmental relationships, BUT:

**Pitfall: PC2 may mix naive pluripotency with early embryo features.** After removing PC1, PC2 becomes the dominant axis. If PC2's top loadings include both pluripotency markers and ZGA genes, hESC will cluster near 2-cell instead of Blastocyst. This is biologically wrong — hESC is derived from ICM (Blastocyst stage).

**Diagnosis:** Always check PCA loadings. If PC1 top genes are lncRNAs (LINC*, C*orf*, ENSG000002*) rather than developmental markers, filter to protein-coding genes first. If PC2 still mixes signals, skip PCA and use direct cosine.

**Validation:** After any clustering, compute pairwise cosine distances between hESC/mESC and all embryo stages. The closest embryo stage should be Blastocyst (for pluripotent cells derived from ICM) or 2-8-cell (for totipotent cells like ciTotiSC/TLSC). If not, the method is wrong.

### Marker gene approach (preferred when batch confounded with biology)

When batch is perfectly correlated with biology (e.g. all embryo samples from one study, all stem cells from another), ComBat will overcorrect and PCA remove-PC1 is not batch correction. The marker gene approach avoids this entirely.

1. Define marker genes for each developmental stage from literature (see references/developmental_markers.py)
2. Filter expression matrix to marker genes only
3. log2(x+1) → z-score per gene → cosine distance → average linkage

No batch correction needed — markers are specific to biology, so batch effects are minimal.

Validation: hESC should cluster nearest Blastocyst (ICM-derived), ciTotiSC/TLSC near 2-8-cell (totipotent stages).

### TPM normalization for cross-study comparison

When comparing samples across studies with different sequencing depths, convert counts to TPM before clustering:

1. Extract gene lengths from GTF (sum of exon lengths per gene)
2. RPK = counts / (gene_length_kb)
3. TPM = RPK / sum(RPK) × 10^6

Gene length extraction from GTF:
```python
def extract_gene_lengths_from_gtf(gtf_path):
    gene_exons = {}  # gene_name -> list of (start, end)
    with open(gtf_path) as f:
        for line in f:
            if line.startswith('#') or '\texon\t' not in line:
                continue
            fields = line.strip().split('\t')
            start, end = int(fields[3]), int(fields[4])
            # Extract gene_name from attributes
            for attr in fields[8].split(';'):
                if 'gene_name' in attr:
                    gene_name = attr.split('"')[1]
                    gene_exons.setdefault(gene_name, []).append((start, end))
                    break
    # Merge overlapping exons and sum lengths
    gene_lengths = {}
    for gene, exons in gene_exons.items():
        exons.sort()
        merged = [exons[0]]
        for s, e in exons[1:]:
            if s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        gene_lengths[gene] = sum(e - s for s, e in merged)
    return gene_lengths
```

TPM conversion:
```python
def counts_to_tpm(counts_df, gene_lengths):
    genes = [g for g in counts_df.index if g in gene_lengths]
    df = counts_df.loc[genes]
    lengths_kb = pd.Series({g: gene_lengths[g] / 1000 for g in genes})
    rpk = df.div(lengths_kb, axis=0)
    tpm = rpk.div(rpk.sum(axis=0), axis=1) * 1e6
    return tpm
```

### PCA remove-PC1 is NOT batch correction

Removing PC1 is dimensionality reduction, not batch correction. It removes the dominant source of variance (which correlates with batch in confounded designs), but does not statistically model or remove batch effects. Do not call it "batch correction" — it confuses the analysis.

PCA remove-PC1 can reveal biology hidden by dominant batch signal, but it also removes biological variance correlated with the batch structure. Use with caution and always validate against known biology.

# Dendrogram leaf ordering for developmental biology

scipy's `dendrogram()` orders leaves by the linkage structure, which may scatter developmental stages across the x-axis. For biological presentations, leaves must appear in developmental order (earliest stage on the left, latest on the right, stem cells last).

**Pitfall: reordering leaves breaks U-shape visual integrity.** When developmental stages are interleaved in the linkage (e.g., hESC+hTBLC merges with 2-cell+Zygote at distance 0.65), the remapped U-shapes span across unrelated samples (Oocyte, other stages), creating visually misleading crossing lines. The underlying cluster structure is unchanged, but the dendrogram LOOKS wrong. Use the standard dendrogram (no reordering) when presenting cluster structure; use PCA scatter plots to show developmental trajectory.

If leaf reordering is still desired, remap the U-shape coordinates:

```python
dn = dendrogram(Z, labels=sample_names, no_plot=True)
n = len(sample_names)

# Sort leaves by developmental stage
dev_order = ["Oocyte", "Zygote", "2-cell", "4-cell", "8-cell", "Morula", "Blastocyst", ...]
def sort_key(idx):
    g = sample_groups.get(sample_names[idx], "")
    return dev_order.index(g) if g in dev_order else len(dev_order)
new_order = sorted(dn["leaves"], key=sort_key)
new_leaf_pos = {leaf: 5 + 10 * i for i, leaf in enumerate(new_order)}

# Build leaf sets per internal node (merge row i → node n+i)
leaf_sets = {}
for i in range(n - 1):
    left, right = int(Z[i, 0]), int(Z[i, 1])
    leaf_sets[n + i] = (
        (leaf_sets[left] if left >= n else {left}) |
        (leaf_sets[right] if right >= n else {right})
    )

def center_of(leaves):
    return sum(new_leaf_pos[lf] for lf in leaves) / len(leaves)

# Remap icoord to new leaf positions
new_icoord = []
for i in range(len(dn["icoord"])):
    left, right = int(Z[i, 0]), int(Z[i, 1])
    left_leaves = leaf_sets[left] if left >= n else {left}
    right_leaves = leaf_sets[right] if right >= n else {right}
    lo, hi = sorted([center_of(left_leaves), center_of(right_leaves)])
    new_icoord.append([lo, lo, hi, hi])

# Draw manually
for xs, ys in zip(new_icoord, dn["dcoord"]):
    ax.plot(xs, ys, color="C0", linewidth=0.8)
ordered_labels = [sample_names[lf] for lf in new_order]
ax.set_xticks([new_leaf_pos[lf] for lf in new_order])
ax.set_xticklabels(ordered_labels, rotation=45, fontsize=9, ha="right")
```

Pitfalls:
- **Dendrogram icoord uses center-of-cluster positions, not leaf positions.** A U-shape connecting leaves 0 and 5 has its verticals at x=5 and x=55 (centers), not at the leaf edges. When remapping, always compute the center of each subtree's leaves in the NEW ordering.
- **leaf_sets key: internal node i in linkage → index n+i in leaf_sets.** Linkage row 0 is merge 0 → node n+0. Leaf indices are 0..n-1. Mixing these up produces KeyError or wrong U-shape positions.

# User preferences

- **Dendrogram natural ordering.** User prefers natural leaf ordering from hierarchical clustering. Do NOT reorder leaves by developmental stage — it breaks U-shape visual integrity and has no biological meaning. Use PCA scatter plots to show developmental trajectory instead.
- **Provide file paths, not descriptions.** When user asks about a figure, give the file path so they can view it themselves. Do not describe the image content unless asked.
- **TPM normalization preferred.** When working with count data, convert to TPM before clustering. The project has `RNASeqNormalizer` class in `/data/pub/zhousha/Totipotent20251031/workflow/Omics/src/count/normalization.py` with `compute_tpm()` method. Gene lengths can be extracted from GTF by summing exon lengths per gene.
- **Expected stem cell → developmental stage mappings:**
  - hTBLC → 2-4 cell (totipotent)
  - hESC → blastocyst (ICM-derived, pluripotent)
  - prEpiSC → blastocyst (primed pluripotency)
  - ci8CLC → 8-cell (totipotent)
  - TLSC → 2-cell (totipotent, mouse)
  - ciTotiSC → 2-cell (totipotent, mouse)
  - mESC → E3.5 ICM (pluripotent, mouse)
- **Compare all combinations systematically.** When testing methods × distances, generate all combinations and save results to CSV for easy comparison. Don't just test one method at a time.
- **Python environment:** Use `/home/zhousha/miniforge3/envs/DNA/bin/python` for clustering scripts. The project venv at `.venv` doesn't have pip installed.

# Clustering validation

Always validate by checking known biological groups:
- Embryo stages should cluster in developmental order: Oocyte → Zygote → 2-cell → 4-cell → 8-cell → 16-cell → Morula → Blastocyst
- If known groups don't cluster correctly, the preprocessing is destroying biological signal — reduce correction aggressiveness
- Compute pairwise cosine distances: hESC should be nearest to Blastocyst (ICM-derived), NOT to 2-cell/Zygote. If hESC clusters near early embryo, the method is removing the wrong signal.
- PCA loadings must be biologically meaningful genes, not lncRNAs or pseudogenes. If top PC1 loadings are LINC*/ENSG* entries, filter to protein-coding genes first.
- Plot PCA grid (PC1-2, PC2-3, PC1-3, PC3-4) to identify which PCs carry developmental vs noise signal

# Non-linear clustering methods

DBSCAN, Spectral clustering, and GMM do NOT solve the in vitro vs in vivo clustering problem. The culture effect is systemic — it affects global gene expression patterns, not just linear relationships. Non-linear methods still group stem cells together because the culture signature dominates the expression profile.

Only use non-linear methods when:
- The biological question involves non-convex clusters (e.g., cell subtypes within a homogeneous population)
- You have already solved the batch effect problem and need better cluster boundaries

Do NOT try non-linear methods as a fix for batch-confounded data — they will fail for the same reason hierarchical clustering fails.

# When to stop trying methods

When stem cells cluster together regardless of:
- Distance metric (cosine, euclidean, correlation, cityblock)
- Gene set (all genes, marker genes, HVGs, DEGs)
- Normalization (counts, TPM)
- Clustering method (hierarchical, KMeans, DBSCAN, Spectral, GMM)
- Batch correction (ComBat, none)

The problem is biological, not methodological. In vitro culture conditions create systemic transcriptomic differences that dominate over developmental stage signals. No clustering method can solve this.

Instead, use supervised approaches:
1. Projection analysis (correlation with stage profiles)
2. Stage-specific signature scoring
3. DEG-based discriminative gene selection

The embryo data serves as an INTERNAL REFERENCE — same pipeline, same platform, same normalization as the stem cell data. Public databases have marker gene lists, but the embryo data provides comparable expression values for direct quantitative comparison.

# Projection analysis (stem cells onto developmental trajectory)

When clustering fails to map stem cells to expected developmental stages, use projection analysis:

1. Compute mean expression profile for each embryo stage
2. Compute Pearson correlation between each stem cell sample and each stage profile
3. Visualize with: heatmap, grouped barplot, PCA projection, radar plot

This directly tests whether stem cells map to their expected developmental stages without being affected by batch effects in clustering.

Script: `/data/pub/zhousha/Totipotent20251031/workflow/Omics/src/cluster/totipotency_projection.py`

See `references/projection-analysis.md` for detailed implementation and expected results.

# DEG-based clustering

When marker genes fail to discriminate stem cell types, use DEG analysis to find genes that distinguish between stem cell states. See `references/deg-based-clustering.md` for the full workflow.

# Three-class architecture (expression_cluster.py)

```
ExpressionPreprocessor  — load, filter, log2, combat, z-score
DistanceCalculator      — pairwise distances + clustering algorithms
ClusterPlotter          — heatmap, UMAP, dendrogram, elbow
```

Connected by `ClusterResult` dataclass (labels, Z, method, metric, n_clusters).

## ExpressionPreprocessor pitfalls

- **Static methods need explicit parameter passing.** `_filter_low_expression(self._df)` silently uses default `min_mean=1.0` instead of `self.min_mean`. Must call `self._filter_low_expression(self._df, self.min_mean, self.min_samples)`. Always verify filter output in logs matches the intended threshold.

- **`from_dataframe()` accepts batch directly.** Pass batch as a `pd.Series` with index matching `df.columns`: `prep.from_dataframe(df, batch=batch_series)`. This triggers `_process()` automatically — do NOT call `_process()` again afterward.

- **ComBat API call pattern:**
  ```python
  prep = ExpressionPreprocessor(min_mean=0, min_samples=1,
                                log_transform=True, combat=True, zscore=False)
  batch_series = pd.Series(batch_labels, index=sample_names)
  prep.from_dataframe(df, batch=batch_series)
  result = prep._raw  # log2 + ComBat corrected (before z-score)
  ```
  The `_raw` attribute holds the log2+ComBat result. The `_scaled` attribute holds the z-scored result (only if `zscore=True`).

- **Do not mix `set_batch()` with `from_dataframe(batch=...)`.** If you pass `batch` to `from_dataframe()`, it sets `self._batch` AND runs `_process()`. Calling `set_batch()` afterward does nothing — the pipeline already ran.

- **min_mean for sample clustering.** Use min_mean=1.0. Threshold ≥10 drops most transcription factors and signaling genes — the genes that define cell identity. High thresholds only make sense for gene-level clustering where you want robustly expressed genes.
