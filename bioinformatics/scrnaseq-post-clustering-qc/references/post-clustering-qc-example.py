#!/usr/bin/env python3
"""Post-clustering cell-level QC filtering.

Workflow:
1. Use scRNAseq.py --mode cluster for clustering
2. Analyze cluster quality (markers, QC metrics)
3. For flagged clusters, filter individual cells (not remove entire cluster)
4. Re-cluster filtered data using scRNAseq.py
"""
import logging
import subprocess
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# Paths
BASE_DIR = Path("output/your_project")
INPUT_FILE = BASE_DIR / "merged.h5ad"
CLUSTERED_FILE = BASE_DIR / "clustered.h5ad"
FILTERED_FILE = BASE_DIR / "filtered.h5ad"
RECLUSTERED_FILE = BASE_DIR / "reclustered.h5ad"
REPORT_FILE = BASE_DIR / "cluster_qc_report.tsv"

# QC thresholds
CLUSTER_THRESHOLDS = {
    "min_genes": 800.0,
    "min_counts": 3000.0,
    "max_pct_unannotated": 50.0,
    "max_pct_mt_genes": 30.0,
    "top_n_markers": 20,
}
CELL_THRESHOLDS = {
    "min_genes": 800,
    "min_counts": 3000,
    "max_pct_mt": 20.0,
}


def analyze_cluster_quality(adata, cluster_key="leiden", top_n=20):
    """Analyze quality metrics for each cluster."""
    results = []
    for cluster in sorted(adata.obs[cluster_key].unique(), key=lambda x: int(x)):
        mask = adata.obs[cluster_key] == cluster
        cluster_data = adata.obs[mask]
        mean_genes = cluster_data["n_genes_by_counts"].mean()
        mean_counts = cluster_data["total_counts"].mean()
        mean_mt_pct = cluster_data["pct_counts_mt"].mean()

        marker_df = sc.get.rank_genes_groups_df(adata, group=cluster)
        top_markers = marker_df.head(top_n)["names"].tolist()
        pct_unannotated = sum(1 for g in top_markers if g.startswith("ENSMMUG")) / max(len(top_markers), 1) * 100
        pct_mt_genes = sum(1 for g in top_markers if g.upper().startswith("MT-")) / max(len(top_markers), 1) * 100

        flag_reasons = []
        if mean_genes < CLUSTER_THRESHOLDS["min_genes"]:
            flag_reasons.append(f"low_genes({mean_genes:.0f})")
        if mean_counts < CLUSTER_THRESHOLDS["min_counts"]:
            flag_reasons.append(f"low_counts({mean_counts:.0f})")
        if pct_unannotated > CLUSTER_THRESHOLDS["max_pct_unannotated"]:
            flag_reasons.append(f"high_unannotated({pct_unannotated:.0f}%)")
        if pct_mt_genes > CLUSTER_THRESHOLDS["max_pct_mt_genes"]:
            flag_reasons.append(f"high_mt_genes({pct_mt_genes:.0f}%)")

        results.append({
            "cluster_id": cluster, "cell_count": mask.sum(),
            "mean_genes": round(mean_genes, 1), "mean_counts": round(mean_counts, 1),
            "mean_mt_pct": round(mean_mt_pct, 3),
            "pct_unannotated": round(pct_unannotated, 1), "pct_mt_genes": round(pct_mt_genes, 1),
            "flagged": len(flag_reasons) > 0,
            "flag_reasons": "; ".join(flag_reasons) if flag_reasons else "",
        })
    return pd.DataFrame(results)


def filter_cells_in_flagged_clusters(adata, cluster_report, cluster_key="leiden"):
    """Filter individual cells within flagged clusters (NOT remove entire clusters)."""
    flagged_clusters = cluster_report[cluster_report["flagged"]]["cluster_id"].tolist()
    if not flagged_clusters:
        return adata, pd.DataFrame()

    keep_mask = pd.Series(True, index=adata.obs.index)
    removed_cells = []

    for cluster in flagged_clusters:
        cluster_mask = adata.obs[cluster_key] == cluster
        cluster_cells = adata.obs[cluster_mask]
        cell_qc_mask = (
            (cluster_cells["n_genes_by_counts"] >= CELL_THRESHOLDS["min_genes"])
            & (cluster_cells["total_counts"] >= CELL_THRESHOLDS["min_counts"])
            & (cluster_cells["pct_counts_mt"] <= CELL_THRESHOLDS["max_pct_mt"])
        )
        cells_to_remove = cluster_cells[~cell_qc_mask].index
        keep_mask[cells_to_remove] = False
        log.info("  Cluster %s: removing %d/%d cells", cluster, len(cells_to_remove), len(cluster_cells))

    return adata[keep_mask].copy(), pd.DataFrame(removed_cells)


def main():
    # 1. Cluster
    subprocess.run([sys.executable, "scRNAseq.py", "--mode", "cluster", "--input", str(INPUT_FILE), "--output", str(CLUSTERED_FILE), ...], check=True)

    # 2. Analyze
    adata = ad.read_h5ad(str(CLUSTERED_FILE))
    report = analyze_cluster_quality(adata)
    report.to_csv(str(REPORT_FILE), sep="\t", index=False)

    # 3. Filter cells in flagged clusters
    adata_filtered, _ = filter_cells_in_flagged_clusters(adata, report)

    # 4. Save RAW counts (not processed data!)
    adata_raw = ad.read_h5ad(str(INPUT_FILE))
    adata_raw_filtered = adata_raw[adata_filtered.obs.index].copy()
    adata_raw_filtered.write_h5ad(str(FILTERED_FILE))

    # 5. Re-cluster
    subprocess.run([sys.executable, "scRNAseq.py", "--mode", "cluster", "--input", str(FILTERED_FILE), "--output", str(RECLUSTERED_FILE), ...], check=True)


if __name__ == "__main__":
    main()
