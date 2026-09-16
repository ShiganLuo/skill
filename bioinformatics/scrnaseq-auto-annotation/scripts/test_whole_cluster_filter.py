#!/usr/bin/env python3
"""Mock test for whole-cluster filter logic in mode_auto.

Validates the precision upgrade heuristic without burning LLM quota.
Loads a saved h5ad, builds mock annotations from real QC metrics,
and runs the same upgrade + filter pipeline that mode_auto uses.

Usage:
    python test_whole_cluster_filter.py <path_to_annotated_h5ad>

Exit codes:
    0 - all OK
    1 - unexpected exception
"""
import importlib
import sys
from pathlib import Path


def build_mock_annotations(adata, low_genes=1500, low_counts=4000):
    """Build per-cluster mock annotations based on real QC metrics.

    The mock mimics what the LLM is expected to say:
      - low quality (mean_genes<low_genes or mean_counts<low_counts)
        → confidence=low, quality_flag=low_quality
      - else → confidence=high, quality_flag=None
    """
    mock = {}
    for cl in adata.obs["leiden"].cat.categories:
        ct = adata.obs.loc[adata.obs["leiden"] == cl, "cell_type"].iloc[0]
        sub = adata[adata.obs["leiden"] == cl]
        mean_g = float(sub.obs["n_genes_by_counts"].mean())
        mean_c = float(sub.obs["total_counts"].mean())
        if mean_g < low_genes or mean_c < low_counts:
            conf, qf = "low", "low_quality"
        else:
            conf, qf = "high", None
        mock[cl] = {
            "cell_type": ct,
            "key_markers": ["a"],
            "canonical_markers": ["a"],
            "reasoning": "mock",
            "confidence": conf,
            "quality_flag": qf,
            "is_subcluster": False,
            "parent_cluster": None,
            "should_merge": False,
            "references": {},
        }
    return mock


def run_upgrade(quality_reports, separation_diag):
    """Replicate the mode_auto upgrade logic exactly."""
    separated_ct_to_clusters = {}
    for ct_info in separation_diag.get("separated_types", []):
        ct = ct_info["cell_type"]
        for d in separation_diag.get("cluster_distances", {}).get(ct, {}).get("pairs", []):
            separated_ct_to_clusters.setdefault(ct, set()).add(d["cluster_i"])
            separated_ct_to_clusters.setdefault(ct, set()).add(d["cluster_j"])

    upgraded, kept = [], []
    for r in quality_reports:
        if not r["should_filter"]:
            continue
        if r.get("filter_mode") == "whole_cluster":
            continue
        ct = r.get("ai_cell_type", "Unknown")
        low_q = any(f in r.get("flags", []) for f in ("low_genes", "low_counts", "high_mt", "low_quality"))
        if not (low_q and ct in separated_ct_to_clusters and r["cluster"] in separated_ct_to_clusters[ct]):
            continue

        ai_conf = r.get("ai_confidence", "low")
        ai_qf = r.get("ai_quality_flag", "")

        if ai_conf in ("low", "medium") and ai_qf == "low_quality":
            should = True
            reason = "LLM low conf + low_quality"
        elif ai_qf in ("unknown", "unannotated") and ai_conf == "low":
            should = True
            reason = "LLM unknown + low"
        else:
            should = False
            reason = f"AI conf={ai_conf}, qf={ai_qf} → keep cell-level"

        if should:
            r["filter_mode"] = "whole_cluster"
            r["flags"] = list(r["flags"]) + ["ambient_artifact"]
            upgraded.append((r["cluster"], ct, reason))
        else:
            kept.append((r["cluster"], ct, reason))
    return upgraded, kept


def main():
    if len(sys.argv) != 2:
        print("Usage: python test_whole_cluster_filter.py <annotated_h5ad>", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(Path("/home/luosg/Data/genomeStability/workflow/Omics/modules/scanpy/bin")))
    import logging
    import scanpy as sc
    import scRNAseq as scr  # noqa: F401

    importlib.reload(scr)  # pick up recent edits

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    adata = sc.read_h5ad(sys.argv[1])
    print(f"Loaded {adata.n_obs} cells, {adata.obs['leiden'].nunique()} clusters")
    print(f"Cell types: {adata.obs['cell_type'].value_counts().to_dict()}")

    mock = build_mock_annotations(adata)
    quality_reports = [
        scr._analyze_cluster_quality(adata, cl, mock[cl])
        for cl in sorted(adata.obs["leiden"].unique(), key=lambda x: int(x))
    ]
    _, diag = scr._check_cell_type_separation(adata, annotations=mock)

    upgraded, kept = run_upgrade(quality_reports, diag)
    print("\nUPGRADED to whole_cluster:")
    for cl, ct, r in upgraded:
        print(f"  cluster {cl} ({ct}): {r}")
    print("\nKEPT at cell-level (despite separation):")
    for cl, ct, r in kept:
        print(f"  cluster {cl} ({ct}): {r}")

    adata_filt, n_removed = scr._filter_flagged_cells(adata, quality_reports)
    print(f"\nFilter: {adata.n_obs} -> {adata_filt.n_obs} ({n_removed} removed)")
    print(f"Cell types after: {adata_filt.obs['cell_type'].value_counts().to_dict()}")
    sm_clusters = sorted(adata_filt.obs.loc[adata_filt.obs["cell_type"] == "Smooth_muscle_cells", "leiden"].unique())
    print(f"Smooth_muscle_clusters left: {sm_clusters}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
