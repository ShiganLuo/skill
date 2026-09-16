# Auto-Annotation Pipeline Detailed Flow

## Step-by-step pipeline (scRNAseq.py --mode auto)

### Step 0: Tissue-Specific Cell Type Query (once per run)
- LLM queries known cell types for the tissue (e.g., ovary)
- Species-aware: maps Mmul_10→macaque, GRCh38→human, GRCm39→mouse
- Returns canonical markers per cell type (5-8 per type)
- Each marker includes a PMID for literature support
- Stored in `tissue_cell_types` dict

### Step 0.5: Tissue Marker Verification (v15+)
- Sample 3 markers per cell type, search PubMed
- **Query: `{gene} AND {cell_type}` ONLY — do NOT include tissue** (see pubmed-query-pitfalls.md)
- Call `_search_pubmed(gene, ct, tissue="", max_results=1)`
- Unverified markers flagged in audit trail, NOT dropped from scoring
- Results in `ctx["marker_verification"]`

### Step 1: Clustering (per round)
- normalize_total → log1p → HVG (3000) → scale → PCA → Harmony → UMAP → Leiden
- TE genes filtered before HVG if `--skip-te`
- Auto n_pcs detection via variance ratio sliding window

### Step 2: Per-Cluster Annotation (program scoring + LLM disambiguation)
For each cluster:
1. Extract top 50 DEGs from rank_genes_groups
2. Program scores against tissue_cell_types (specificity-weighted, see scoring-algorithm.md)
3. Three regimes:
   - score >= 1.5 AND margin >= 0.3 → program decides, PMID pre-check, no LLM
   - 0.5 <= score < 1.5 OR small margin → LLM disambiguation (top-3 candidates)
   - score < 0.5 OR no match → LLM free annotation
4. PMID gate: search PubMed for chosen cell_type + markers
   - 0 refs → confidence forced to "low"
   - < 2 refs → confidence capped at "medium"
5. Name normalization against tissue_cell_types canonical names

### Sensors (per round)
- `_basic_qc_check`: per-cluster QC flags (relative to dataset median)
- `_compute_boundary_sharpness`: k-NN composition, inter-cluster proximity
- `_check_cluster_continuity`: UMAP spatial continuity per cluster
- `_check_cell_type_separation`: same-type cluster distance + Jaccard

### CP: Single Orchestrator Checkpoint (per round)
- `_collect_full_state`: compresses all sensor data into clusters_payload
  - Each cluster: cell_type, top_markers (10), trust, alternative, should_drop,
    low_quality_cell_pct, score, n_matched, n_cells, mean_genes, mean_counts,
    pct_mt, qc_flags
- LLM sees full state, chooses one action:
  - `accept` → save and exit
  - `correct_annotations` → relabel cell_type strings
  - `filter_and_recluster` → drop cells/clusters, re-cluster
  - `adjust_resolution_and_recluster` → change Leiden resolution

### Report Generation
- annotation_report.tsv: per-cluster annotations with confidence and flags
- references.tsv: PubMed citations per marker gene
- audit_report.md: Chinese markdown audit summary (LLM-generated)
- Plots: UMAP (leiden, sample_id, cell_type), dotplot, rank_genes_groups

## QC Data Flow (v15+)
```
_basic_qc_check(adata) → basic_qc_reports
    └→ passed to _collect_full_state as basic_qc_reports parameter
    └→ built into basic_qc_lookup dict (cluster → QC metrics)
    └→ merged into clusters_payload (n_cells, mean_genes, mean_counts, pct_mt, qc_flags)
    └→ orchestrator sees raw QC data alongside trust/lq_pct

_analyze_cluster_quality(adata, cluster, ann) → quality_reports
    └→ used for annotation_report.tsv and filter decisions
    └→ NOT passed to orchestrator (different from basic_qc_reports)
```

## te_dominated Handling (unified v15+)
Both `_compute_cluster_assessment` and `_analyze_cluster_quality` use same logic:
- `low_quality` / `unknown` → artifact
- `te_dominated` → artifact ONLY if combined with bad QC (lq_pct > 10%)
  - scTE data has real ERVK_high/Alu_high populations
  - te_dominated alone does NOT trigger filtering

## Key Design Decisions
- No manual marker dictionaries — fully automated via tissue query
- PubMed verification ensures annotations have literature support
- Program scoring saves 80-90% LLM calls vs per-cluster LLM annotation
- TE-dominated clusters get special handling (not silently ignored)
- Orchestrator makes ALL policy decisions — program is sensor + executor only
