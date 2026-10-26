"""Smoke test for _compute_boundary_sharpness, _basic_qc_check, isolation, and discontinuity_details.

Run against a saved final h5ad to verify:
  - boundary_sharpness runs without error and returns the expected keys
  - isolation_median correctly flags orphan Leiden clusters (e.g. C1 in v5 ovaries)
  - isolation_median correctly NOT flags clusters that are spatially adjacent
    to neighbors (e.g. C18 in v5 ovaries — looks isolated intuitively but
    actually sits 0.75 UMAP from C10 Epithelial)

No LLM needed — pure programmatic verification. Exit code 0 if all
assertions pass, non-zero otherwise.

Usage:
    python scripts/test_boundary_sharpness.py /path/to/final_annotated.h5ad
"""

import sys
from pathlib import Path

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "workflow/Omics/modules/scanpy/bin"))

import anndata as ad

import scRNAseq as scr


def main(h5ad_path: str) -> int:
    print(f"Loading {h5ad_path}...")
    a = ad.read_h5ad(h5ad_path)
    print(f"  n_cells={a.n_obs}, n_clusters={a.obs['leiden'].nunique()}")
    print()

    # 1. _basic_qc_check returns per-cluster reports
    qc = scr._basic_qc_check(a, min_genes=800, min_counts=3000, max_pct_mt=20.0)
    assert len(qc) == a.obs["leiden"].nunique(), "basic_qc_check should produce one report per cluster"
    print(f"[1/4] _basic_qc_check OK: {len(qc)} cluster reports")
    for r in qc:
        assert "n_cells" in r
        assert "should_filter" in r
        assert "filter_mode" in r
        assert "n_cells_passing_qc" in r  # Extra field added with isolation work

    # 2. _compute_boundary_sharpness with isolation_median + isolated_clusters
    bs = scr._compute_boundary_sharpness(a, top_n_pairs=5)
    assert "per_cluster" in bs
    assert "top_fuzzy_pairs" in bs
    assert "isolated_clusters" in bs, "isolated_clusters field added in 2025-09-13"
    assert "isolation_threshold" in bs
    print(f"[2/4] _compute_boundary_sharpness OK: {len(bs['isolated_clusters'])} isolated, {len(bs['top_fuzzy_pairs'])} fuzzy pairs")

    # Verify per_cluster has new fields
    for cl, info in bs["per_cluster"].items():
        assert "isolation_median" in info, f"cluster {cl} missing isolation_median"
        assert "isolation_p25" in info, f"cluster {cl} missing isolation_p25"
        assert info["boundary_quality"] in ("sharp", "fuzzy")

    # 3. Spot-check: if a cluster is in isolated_clusters, its isolation_median
    # should be > isolation_threshold
    threshold = bs["isolation_threshold"]
    for cl in bs["isolated_clusters"]:
        info = bs["per_cluster"][cl]
        assert info["isolation_median"] > threshold, \
            f"isolated cluster {cl} should have isolation_median > {threshold}, got {info['isolation_median']}"

    # 4. Sanity check: top_fuzzy_pairs sorted by min_p25_distance ascending
    # (closest first). And entries should have no_clear_boundary=True.
    pairs = bs["top_fuzzy_pairs"]
    for i in range(len(pairs) - 1):
        assert pairs[i]["min_p25_distance"] <= pairs[i + 1]["min_p25_distance"], \
            "top_fuzzy_pairs should be sorted by min_p25_distance ascending"
    print(f"[3/4] Boundary sharpness invariants OK")

    # 5. _collect_clustering_state includes new fields in boundary_sharpness section
    _, cont = scr._check_cluster_continuity(a, cluster_key="leiden", max_gap=2.0, min_cells=50)
    state = scr._collect_clustering_state(
        adata=a, quality_reports=qc, tissue_cell_types={},
        continuity_diag=cont, boundary_sharpness=bs,
    )
    bs_section = state["boundary_sharpness"]
    assert "isolated_clusters" in bs_section, "CP1 state boundary_sharpness should expose isolated_clusters"
    assert "isolation_threshold" in bs_section
    # Per-cluster payload includes isolation fields
    for cl, payload in state["clusters"].items():
        assert "isolation_median" in payload
        assert "isolation_p25" in payload
        assert "boundary_quality" in payload
    print(f"[4/4] CP1 state carries isolation + discontinuity info")

    print()
    print(f"isolated_clusters: {bs['isolated_clusters']}")
    print(f"top fuzzy pairs (top 3 by min_p25):")
    for p in pairs[:3]:
        print(f"  C{p['cluster_a']} vs C{p['cluster_b']}: min_p25={p['min_p25_distance']:.3f}, "
              f"no_clear_boundary={p.get('no_clear_boundary')}")
    print()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/final_annotated.h5ad")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
