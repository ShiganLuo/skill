#!/usr/bin/env python3
"""Nature-standard scRNA-seq re-clustering and annotation pipeline.

Complete pipeline with:
- QC filtering
- HVG selection (seurat flavor, 2000 genes)
- Harmony batch correction (direct harmonypy 2.0 call)
- Leiden clustering with igraph
- Marker-based annotation with confidence scoring
- Cluster merging for fragmented cell types
- Comprehensive plotting

Usage:
  python recluster_annotate.py \
    --input merged.h5ad \
    --output annotated.h5ad \
    --marker-file markers.tsv \
    --plot-dir plots/ \
    --n-top-genes 2000 --n-pcs 50 --n-neighbors 50 --resolution 0.6
"""
import argparse
import csv
import logging
import os
import warnings
from pathlib import Path
from typing import Dict, List

import anndata as ad
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc

warnings.filterwarnings("ignore")
ad.settings.allow_write_nullable_strings = True

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def save_fig(fig_or_plotter, path: str, dpi: int = 300):
    """Save figure or scanpy plotter and close."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if hasattr(fig_or_plotter, "savefig"):
        fig_or_plotter.savefig(path, dpi=dpi, bbox_inches="tight")
    elif hasattr(fig_or_plotter, "fig"):
        fig_or_plotter.fig.savefig(path, dpi=dpi, bbox_inches="tight")
    else:
        plt.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close("all")
    logger.info("Saved: %s", path)


def step_qc(adata: ad.AnnData, plot_dir: str) -> ad.AnnData:
    """QC metrics and filtering."""
    logger.info("=== Step 1: QC ===")
    n_before = adata.n_obs
    # MUST use np.array() — pandas BooleanArray breaks scipy sparse indexing
    adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-") | adata.var_names.str.startswith("mt"))
    adata.var["ribo"] = np.array(adata.var_names.str.startswith(("RPS", "RPL")))
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo"], inplace=True)
    adata = adata[adata.obs.n_genes_by_counts >= 200].copy()
    adata = adata[adata.obs.n_genes_by_counts <= 6000].copy()
    adata = adata[adata.obs.pct_counts_mt <= 20].copy()
    logger.info("QC: %d -> %d cells (%d removed)", n_before, adata.n_obs, n_before - adata.n_obs)
    return adata


def step_normalize(adata: ad.AnnData, n_top_genes: int = 2000) -> ad.AnnData:
    """Normalize, log transform, select HVGs."""
    logger.info("=== Step 2: Normalize + HVG (top %d) ===", n_top_genes)
    if "counts" not in adata.layers:
        adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    # Use flavor="seurat" — seurat_v3 requires skmisc
    sc.pp.highly_variable_genes(
        adata, n_top_genes=n_top_genes,
        batch_key="sample_id" if "sample_id" in adata.obs else None,
        flavor="seurat",
    )
    logger.info("Selected %d HVGs", adata.var.highly_variable.sum())
    return adata


def step_batch_correct(adata: ad.AnnData, n_pcs: int = 50) -> ad.AnnData:
    """Scale HVGs, PCA, Harmony batch correction."""
    logger.info("=== Step 3: Batch correction (Harmony) ===")
    hvg_mask = adata.var.highly_variable.values
    adata_hvg = adata[:, hvg_mask].copy()
    sc.pp.scale(adata_hvg, max_value=10)
    n_comps = min(n_pcs, max(2, adata_hvg.n_obs - 1), adata_hvg.n_vars)
    sc.tl.pca(adata_hvg, n_comps=n_comps, svd_solver="arpack")
    adata.obsm["X_pca"] = adata_hvg.obsm["X_pca"]
    adata.uns["pca"] = adata_hvg.uns["pca"]

    # Direct harmonypy call — scanpy wrapper broken with harmonypy 2.0
    batch_key = "sample_id" if "sample_id" in adata.obs else "batch"
    if batch_key in adata.obs:
        from harmonypy import run_harmony
        meta_data = pd.DataFrame({batch_key: adata.obs[batch_key].values})
        ho = run_harmony(adata.obsm["X_pca"], meta_data, vars_use=[batch_key], max_iter_harmony=20)
        corrected = ho.Z_corr.T
        if corrected.shape[0] != adata.n_obs:
            corrected = corrected.T
        adata.obsm["X_pca_harmony"] = np.ascontiguousarray(corrected)
        logger.info("Harmony complete (key=%s, shape=%s)", batch_key, corrected.shape)
    else:
        adata.obsm["X_pca_harmony"] = adata.obsm["X_pca"].copy()
    return adata


def step_cluster(adata, n_neighbors=30, resolution=0.5, plot_dir=""):
    """Build neighbor graph, UMAP, Leiden clustering."""
    logger.info("=== Step 4: Clustering (resolution=%.2f) ===", resolution)
    pca_key = "X_pca_harmony" if "X_pca_harmony" in adata.obsm else "X_pca"
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=50, use_rep=pca_key)
    sc.tl.umap(adata, min_dist=0.1, spread=0.8)  # Tighter for cleaner separation
    sc.tl.leiden(adata, resolution=resolution, key_added="leiden", flavor="igraph", n_iterations=2, directed=False)
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon", n_genes=100)
    logger.info("Found %d clusters", adata.obs["leiden"].nunique())

    if plot_dir:
        fig, ax = plt.subplots(figsize=(10, 8))
        sc.pl.umap(adata, color="leiden", legend_loc="on data", legend_fontsize=8, ax=ax, show=False, title="Leiden Clusters")
        save_fig(fig, os.path.join(plot_dir, "umap_leiden.png"))
        fig, ax = plt.subplots(figsize=(10, 8))
        sc.pl.umap(adata, color="sample_id" if "sample_id" in adata.obs else "batch", ax=ax, show=False, title="Samples")
        save_fig(fig, os.path.join(plot_dir, "umap_sample.png"))
        sc.pl.pca_variance_ratio(adata, n_pcs=50, show=False)
        plt.savefig(os.path.join(plot_dir, "pca_variance.png"), dpi=300, bbox_inches="tight")
        plt.close("all")
    return adata


def _merge_fragmented_clusters(adata, cluster_anno):
    """Merge disconnected clusters of the same cell type using connected components."""
    from scipy.sparse.csgraph import connected_components
    if "connectivities" not in adata.obsp:
        return
    ct_clusters = {}
    for cluster, info in cluster_anno.items():
        ct_clusters.setdefault(info["cell_type"], []).append(cluster)
    merge_map, merged_id = {}, 0
    for ct, clusters in ct_clusters.items():
        if len(clusters) == 1:
            merge_map[clusters[0]] = merged_id; merged_id += 1; continue
        ct_mask = adata.obs["leiden"].isin(clusters).values
        ct_indices = np.where(ct_mask)[0]
        if len(ct_indices) == 0: continue
        sub_conn = adata.obsp["connectivities"][np.ix_(ct_indices, ct_indices)]
        _, labels = connected_components(sub_conn, directed=False)
        component_map = {idx: labels[i] for i, idx in enumerate(ct_indices)}
        for cluster in clusters:
            cluster_indices = np.where((adata.obs["leiden"] == cluster).values)[0]
            if len(cluster_indices) == 0: continue
            cluster_components = [component_map.get(idx, -1) for idx in cluster_indices]
            main_component = max(set(cluster_components), key=cluster_components.count)
            merge_key = f"{ct}_{main_component}"
            if merge_key not in merge_map:
                merge_map[merge_key] = merged_id; merged_id += 1
            merge_map[cluster] = merge_map[merge_key]
    if merge_map:
        adata.obs["leiden_merged"] = adata.obs["leiden"].map(merge_map).astype("category")
        logger.info("Merged %d clusters into %d groups", len(cluster_anno), merged_id)


def step_annotate(adata, marker_file, plot_dir=""):
    """Annotate clusters using marker genes with scoring and merging."""
    logger.info("=== Step 5: Annotation ===")
    marker_dict = {}
    with open(marker_file, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            genes = [g.strip() for g in row.get("markers", "").split(",") if g.strip() and g.strip() in adata.var_names]
            if genes:
                marker_dict[row["cell_type"]] = genes
    for ct, genes in marker_dict.items():
        sc.tl.score_genes(adata, gene_list=genes, score_name=f"score_{ct}", ctrl_size=min(50, len(genes)))
    score_cols = [c for c in adata.obs.columns if c.startswith("score_")]
    if score_cols:
        scores_df = adata.obs[score_cols].copy()
        scores_df.columns = [c.replace("score_", "") for c in scores_df.columns]
        cluster_anno = {}
        for cluster in adata.obs["leiden"].cat.categories:
            mask = adata.obs["leiden"] == cluster
            cluster_scores = scores_df[mask].mean()
            best_ct = cluster_scores.idxmax()
            best_score = cluster_scores.max()
            second_best = cluster_scores.nlargest(2).iloc[1] if len(cluster_scores) >= 2 else 0.0
            confidence = "high" if best_score > 0.1 and (best_score - second_best) > 0.05 else "medium" if best_score > 0.05 else "low"
            cluster_anno[cluster] = {"cell_type": best_ct, "score": float(best_score), "confidence": confidence}
        adata.obs["cell_type"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["cell_type"]).astype("category")
        adata.obs["annotation_confidence"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["confidence"]).astype("category")
        adata.uns["cluster_annotation"] = cluster_anno
        _merge_fragmented_clusters(adata, cluster_anno)
        for cluster, info in cluster_anno.items():
            n = (adata.obs["leiden"] == cluster).sum()
            logger.info("  Cluster %s (%d cells): %s (score=%.3f, %s)", cluster, n, info["cell_type"], info["score"], info["confidence"])

    if plot_dir:
        if marker_dict:
            save_fig(sc.pl.dotplot(adata, var_names=marker_dict, groupby="leiden", standard_scale="var", show=False, return_fig=True), os.path.join(plot_dir, "marker_dotplot.png"))
            save_fig(sc.pl.dotplot(adata, var_names=marker_dict, groupby="cell_type", standard_scale="var", show=False, return_fig=True), os.path.join(plot_dir, "marker_dotplot_celltype.png"))
        fig, ax = plt.subplots(figsize=(12, 10))
        sc.pl.umap(adata, color="cell_type", legend_loc="on data", legend_fontsize=8, ax=ax, show=False, title="Cell Types")
        save_fig(fig, os.path.join(plot_dir, "umap_celltype.png"))
        if "leiden_merged" in adata.obs.columns:
            fig, ax = plt.subplots(figsize=(12, 10))
            sc.pl.umap(adata, color="leiden_merged", legend_loc="on data", legend_fontsize=8, ax=ax, show=False, title="Merged Clusters")
            save_fig(fig, os.path.join(plot_dir, "umap_merged_clusters.png"))
        fig, ax = plt.subplots(figsize=(10, 8))
        sc.pl.umap(adata, color="annotation_confidence", ax=ax, show=False, title="Annotation Confidence")
        save_fig(fig, os.path.join(plot_dir, "umap_confidence.png"))
        sc.pl.rank_genes_groups_dotplot(adata, n_genes=3, show=False)
        plt.savefig(os.path.join(plot_dir, "deg_dotplot.png"), dpi=300, bbox_inches="tight")
        plt.close("all")
    return adata


def main():
    parser = argparse.ArgumentParser(description="Nature-standard scRNA-seq re-clustering pipeline")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--marker-file", required=True)
    parser.add_argument("--plot-dir", required=True)
    parser.add_argument("--n-top-genes", type=int, default=2000)
    parser.add_argument("--n-pcs", type=int, default=50)
    parser.add_argument("--n-neighbors", type=int, default=50)
    parser.add_argument("--resolution", type=float, default=0.6)
    args = parser.parse_args()
    os.makedirs(args.plot_dir, exist_ok=True)
    adata = ad.read_h5ad(args.input)
    logger.info("Loaded: %d cells x %d genes", adata.n_obs, adata.n_vars)
    adata = step_qc(adata, args.plot_dir)
    adata = step_normalize(adata, args.n_top_genes)
    adata = step_batch_correct(adata, args.n_pcs)
    adata = step_cluster(adata, args.n_neighbors, args.resolution, args.plot_dir)
    adata = step_annotate(adata, args.marker_file, args.plot_dir)
    adata.write_h5ad(args.output)
    logger.info("Done!")


if __name__ == "__main__":
    main()
