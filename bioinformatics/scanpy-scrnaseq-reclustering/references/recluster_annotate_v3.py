#!/usr/bin/env python3
"""Nature-standard scRNA-seq pipeline v3 — all reviewer issues fixed.

Fixes:
1. Missing cell types (Oocyte/B_cell/Luteal) — documented as rare
2. UMAP legend added
3. Doublet verification (CD79A in Macrophage)
4. Colorblind-friendly palette
5. Sample UMAP (post-Harmony)
6. Better Smooth_muscle/Pericyte markers
7. Proliferating labeled as "Proliferating (mixed)"
"""
import argparse
import csv
import logging
import os
import warnings
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

# Colorblind-friendly palette (Okabe-Ito + extended)
CB_PALETTE = {
    "Endothelial":       "#0072B2",  # blue
    "Granulosa":         "#E69F00",  # orange
    "Macrophage":        "#009E73",  # green
    "OSE":               "#CC79A7",  # pink (not red)
    "Pericyte":          "#56B4E9",  # light blue
    "Proliferating (mixed)": "#F0E442",  # yellow
    "Smooth_muscle":     "#D55E00",  # vermillion
    "Stromal":           "#999999",  # grey
    "T_NK_cell":         "#000000",  # black
    "Theca":             "#882255",  # dark purple-brown
}

def save_fig(fig_or_plotter, path: str, dpi: int = 300):
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
    logger.info("=== Step 1: QC ===")
    n_before = adata.n_obs
    adata.var["mt"] = np.array(adata.var_names.str.upper().str.startswith("MT-") | adata.var_names.str.startswith("mt"))
    adata.var["ribo"] = np.array(adata.var_names.str.startswith(("RPS", "RPL")))
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo"], inplace=True)
    adata = adata[adata.obs.n_genes_by_counts >= 200].copy()
    adata = adata[adata.obs.n_genes_by_counts <= 6000].copy()
    adata = adata[adata.obs.pct_counts_mt <= 20].copy()
    logger.info("QC: %d -> %d cells", n_before, adata.n_obs)
    return adata


def step_normalize(adata: ad.AnnData, n_top_genes: int = 2000) -> ad.AnnData:
    logger.info("=== Step 2: Normalize + HVG ===")
    if "counts" not in adata.layers:
        adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes,
                                 batch_key="sample_id" if "sample_id" in adata.obs else None,
                                 flavor="seurat")
    logger.info("Selected %d HVGs", adata.var.highly_variable.sum())
    return adata


def step_batch_correct(adata: ad.AnnData, n_pcs: int = 50) -> ad.AnnData:
    logger.info("=== Step 3: Harmony ===")
    hvg_mask = adata.var.highly_variable.values
    adata_hvg = adata[:, hvg_mask].copy()
    sc.pp.scale(adata_hvg, max_value=10)
    n_comps = min(n_pcs, max(2, adata_hvg.n_obs - 1), adata_hvg.n_vars)
    sc.tl.pca(adata_hvg, n_comps=n_comps, svd_solver="arpack")
    adata.obsm["X_pca"] = adata_hvg.obsm["X_pca"]
    adata.uns["pca"] = adata_hvg.uns["pca"]

    batch_key = "sample_id" if "sample_id" in adata.obs else "batch"
    if batch_key in adata.obs:
        from harmonypy import run_harmony
        meta = pd.DataFrame({batch_key: adata.obs[batch_key].values})
        ho = run_harmony(adata.obsm["X_pca"], meta, vars_use=[batch_key], max_iter_harmony=20)
        corrected = ho.Z_corr.T
        if corrected.shape[0] != adata.n_obs:
            corrected = corrected.T
        adata.obsm["X_pca_harmony"] = np.ascontiguousarray(corrected)
        logger.info("Harmony done (key=%s)", batch_key)
    else:
        adata.obsm["X_pca_harmony"] = adata.obsm["X_pca"].copy()
    return adata


def step_cluster(adata: ad.AnnData, n_neighbors: int = 50, resolution: float = 0.6, plot_dir: str = "") -> ad.AnnData:
    logger.info("=== Step 4: Clustering (res=%.2f) ===", resolution)
    pca_key = "X_pca_harmony" if "X_pca_harmony" in adata.obsm else "X_pca"
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=50, use_rep=pca_key)
    sc.tl.umap(adata, min_dist=0.1, spread=0.8)
    sc.tl.leiden(adata, resolution=resolution, key_added="leiden", flavor="igraph", n_iterations=2, directed=False)
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon", n_genes=100)
    logger.info("Found %d clusters", adata.obs["leiden"].nunique())

    if plot_dir:
        # Sample UMAP
        fig, ax = plt.subplots(figsize=(10, 8))
        sc.pl.umap(adata, color="sample_id" if "sample_id" in adata.obs else "batch",
                   ax=ax, show=False, title="Samples (post-Harmony)", frameon=True)
        save_fig(fig, os.path.join(plot_dir, "umap_sample.png"))

        # Leiden UMAP
        fig, ax = plt.subplots(figsize=(10, 8))
        sc.pl.umap(adata, color="leiden", legend_loc="on data", legend_fontsize=8,
                   ax=ax, show=False, title="Leiden Clusters", frameon=True)
        save_fig(fig, os.path.join(plot_dir, "umap_leiden.png"))

        sc.pl.pca_variance_ratio(adata, n_pcs=50, show=False)
        plt.savefig(os.path.join(plot_dir, "pca_variance.png"), dpi=300, bbox_inches="tight")
        plt.close("all")
    return adata


def step_annotate(adata: ad.AnnData, marker_file: str, plot_dir: str = "") -> ad.AnnData:
    logger.info("=== Step 5: Annotation ===")

    marker_dict: Dict[str, List[str]] = {}
    with open(marker_file, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            ct = row["cell_type"]
            genes = [g.strip() for g in row.get("markers", "").split(",") if g.strip() and g.strip() in adata.var_names]
            if genes:
                marker_dict[ct] = genes
    logger.info("Loaded %d cell types", len(marker_dict))

    for ct, genes in marker_dict.items():
        sc.tl.score_genes(adata, gene_list=genes, score_name=f"score_{ct}", ctrl_size=min(50, len(genes)))

    score_cols = [c for c in adata.obs.columns if c.startswith("score_")]
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

    # Fix Proliferating label
    for cluster, info in cluster_anno.items():
        if info["cell_type"] == "Proliferating":
            info["cell_type"] = "Proliferating (mixed)"

    adata.obs["cell_type"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["cell_type"]).astype("category")
    adata.obs["annotation_confidence"] = adata.obs["leiden"].map(lambda x: cluster_anno[x]["confidence"]).astype("category")
    adata.uns["cluster_annotation"] = cluster_anno

    # Merge fragmented clusters
    _merge_fragmented_clusters(adata, cluster_anno)

    logger.info("Cluster annotation:")
    for cluster, info in cluster_anno.items():
        n = (adata.obs["leiden"] == cluster).sum()
        logger.info("  Cluster %s (%d cells): %s (score=%.3f, %s)", cluster, n, info["cell_type"], info["score"], info["confidence"])

    # Detect rare cell types
    _detect_rare_cell_types(adata, marker_dict)

    if plot_dir:
        _make_plots(adata, marker_dict, plot_dir)

    return adata


def _merge_fragmented_clusters(adata: ad.AnnData, cluster_anno: dict) -> None:
    from scipy.sparse.csgraph import connected_components
    if "connectivities" not in adata.obsp:
        return

    ct_clusters = {}
    for cluster, info in cluster_anno.items():
        ct = info["cell_type"]
        ct_clusters.setdefault(ct, []).append(cluster)

    merge_map = {}
    merged_id = 0
    for ct, clusters in ct_clusters.items():
        if len(clusters) == 1:
            merge_map[clusters[0]] = merged_id
            merged_id += 1
            continue
        ct_mask = adata.obs["leiden"].isin(clusters).values
        ct_indices = np.where(ct_mask)[0]
        if len(ct_indices) == 0:
            continue
        conn = adata.obsp["connectivities"]
        sub_conn = conn[np.ix_(ct_indices, ct_indices)]
        n_components, labels = connected_components(sub_conn, directed=False)
        component_map = {idx: labels[i] for i, idx in enumerate(ct_indices)}
        for cluster in clusters:
            cluster_mask = adata.obs["leiden"] == cluster
            cluster_indices = np.where(cluster_mask)[0]
            if len(cluster_indices) == 0:
                continue
            cluster_components = [component_map.get(idx, -1) for idx in cluster_indices]
            main_component = max(set(cluster_components), key=cluster_components.count)
            merge_key = f"{ct}_{main_component}"
            if merge_key not in merge_map:
                merge_map[merge_key] = merged_id
                merged_id += 1
            merge_map[cluster] = merge_map[merge_key]

    if merge_map:
        adata.obs["leiden_merged"] = adata.obs["leiden"].map(merge_map).astype("category")
        logger.info("Merged %d clusters -> %d groups", len(cluster_anno), merged_id)


def _detect_rare_cell_types(adata: ad.AnnData, marker_dict: dict) -> None:
    rare_types = {}
    for ct in ["Oocyte", "B_cell", "Luteal"]:
        if ct not in marker_dict:
            continue
        genes = marker_dict[ct]
        expr_matrix = np.zeros((adata.n_obs, len(genes)))
        for i, gene in enumerate(genes):
            if gene in adata.var_names:
                gexpr = adata[:, gene].X
                if hasattr(gexpr, 'toarray'):
                    gexpr = gexpr.toarray().flatten()
                expr_matrix[:, i] = gexpr
        co_expr = (expr_matrix > 0).sum(axis=1)
        n_multi = int((co_expr >= 2).sum())
        n_single = int((co_expr >= 1).sum())
        if n_multi > 0:
            rare_types[ct] = {"single_marker": n_single, "multi_marker": n_multi}
            adata.obs.loc[co_expr >= 2, "rare_cell_type"] = ct
            logger.info("Rare cell type %s: %d cells (single), %d cells (multi-marker)", ct, n_single, n_multi)
        else:
            logger.info("Rare cell type %s: not detected", ct)
    if rare_types:
        adata.uns["rare_cell_types"] = rare_types


def _make_plots(adata: ad.AnnData, marker_dict: dict, plot_dir: str) -> None:
    ct_categories = adata.obs["cell_type"].cat.categories.tolist()
    palette = [CB_PALETTE.get(ct, "#333333") for ct in ct_categories]

    # Cell type UMAP with LEGEND
    fig, ax = plt.subplots(figsize=(14, 10))
    sc.pl.umap(adata, color="cell_type", palette=palette, ax=ax, show=False,
               title="Cell Types", frameon=True, legend_loc="right margin",
               legend_fontsize=10, legend_fontoutline=2)
    save_fig(fig, os.path.join(plot_dir, "umap_celltype.png"))

    # Merged clusters
    if "leiden_merged" in adata.obs.columns:
        fig, ax = plt.subplots(figsize=(14, 10))
        sc.pl.umap(adata, color="leiden_merged", ax=ax, show=False,
                   title="Merged Clusters", frameon=True, legend_loc="on data", legend_fontsize=10)
        save_fig(fig, os.path.join(plot_dir, "umap_merged_clusters.png"))

    # Confidence
    fig, ax = plt.subplots(figsize=(10, 8))
    conf_palette = {"high": "#009E73", "medium": "#E69F00", "low": "#D55E00"}
    sc.pl.umap(adata, color="annotation_confidence", palette=conf_palette,
               ax=ax, show=False, title="Annotation Confidence", frameon=True, legend_loc="right margin")
    save_fig(fig, os.path.join(plot_dir, "umap_confidence.png"))

    # Marker dotplot
    if marker_dict:
        fig = sc.pl.dotplot(adata, var_names=marker_dict, groupby="cell_type",
                            standard_scale="var", show=False, return_fig=True)
        save_fig(fig, os.path.join(plot_dir, "marker_dotplot_celltype.png"))

    # DEG dotplot
    sc.pl.rank_genes_groups_dotplot(adata, n_genes=3, show=False)
    plt.savefig(os.path.join(plot_dir, "deg_dotplot.png"), dpi=300, bbox_inches="tight")
    plt.close("all")

    # Doublet check UMAPs
    for gene in ["CD79A", "STAR", "DDX4", "DAZL", "MS4A1", "HSD3B1"]:
        if gene in adata.var_names:
            fig, ax = plt.subplots(figsize=(10, 8))
            sc.pl.umap(adata, color=gene, ax=ax, show=False,
                       title=f"{gene} expression", frameon=True,
                       vmin=0, vmax="p99", color_map="Reds")
            save_fig(fig, os.path.join(plot_dir, f"umap_{gene.lower()}_marker.png"))


def main():
    parser = argparse.ArgumentParser(description="Nature-standard scRNA-seq v3")
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
    logger.info("Loaded: %s (%d cells x %d genes)", args.input, adata.n_obs, adata.n_vars)

    adata = step_qc(adata, args.plot_dir)
    adata = step_normalize(adata, n_top_genes=args.n_top_genes)
    adata = step_batch_correct(adata, n_pcs=args.n_pcs)
    adata = step_cluster(adata, n_neighbors=args.n_neighbors, resolution=args.resolution, plot_dir=args.plot_dir)
    adata = step_annotate(adata, args.marker_file, plot_dir=args.plot_dir)

    logger.info("Saving to %s", args.output)
    adata.write_h5ad(args.output)
    logger.info("Done!")


if __name__ == "__main__":
    main()
