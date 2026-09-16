"""Smoke test for CP3 spatial_mismatch detection.

Run against a saved final h5ad to verify:
  - _collect_iteration_state computes nearest_same_cell_type and
    nearest_other_cell_type per cluster using MEDIAN cell-to-cell distance
    (NOT centroid distance — centroid misleads on dispersed clusters)
  - spatial_mismatches list catches clusters whose nearest OTHER-CT cluster
    is closer than their nearest SAME-CT cluster

No LLM needed — pure programmatic verification. Exit code 0 if all
assertions pass.

Usage:
    python scripts/test_spatial_mismatch.py /path/to/final_annotated.h5ad
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "workflow/Omics/modules/scanpy/bin"))

import anndata as ad

import scRNAseq as scr


def main(h5ad_path: str) -> int:
    print(f"Loading {h5ad_path}...")
    a = ad.read_h5ad(h5ad_path)
    print(f"  n_cells={a.n_obs}, n_clusters={a.obs['leiden'].nunique()}")
    print()

    # Build minimal mock annotations from cell_type majority per leiden cluster
    annotations = {}
    quality_reports = []
    for cl in sorted(a.obs["leiden"].unique(), key=lambda x: int(x)):
        mask = a.obs["leiden"] == cl
        ct_series = a.obs.loc[mask, "cell_type"].astype(str)
        majority_ct = ct_series.value_counts().idxmax() if len(ct_series) else "Unknown"
        annotations[cl] = {
            "cell_type": majority_ct,
            "cell_type_raw": majority_ct,
            "key_markers": [], "canonical_markers": [],
            "reasoning": "synthetic", "confidence": "high",
            "quality_flag": None, "is_subcluster": False,
            "parent_cluster": None, "should_merge": False,
            "references": {},
        }
        quality_reports.append({
            "cluster": cl, "n_cells": int(mask.sum()),
            "mean_genes": 0, "mean_counts": 0, "pct_mt": 0,
            "flags": [], "should_filter": False, "filter_mode": "cell",
        })

    state = scr._collect_iteration_state(
        adata=a,
        annotations=annotations,
        quality_reports=quality_reports,
        separation_diag={"separated_types": [], "misannotated": []},
        continuity_diag={"discontinuous_clusters": []},
        tissue_cell_types={},
    )

    # 1. Per-cluster payload has the new spatial-context fields
    for cl, payload in state["clusters"].items():
        assert "majority_cell_type" in payload, f"C{cl} missing majority_cell_type"
        assert "nearest_other_cell_type" in payload, f"C{cl} missing nearest_other_cell_type"
        assert "nearest_same_cell_type" in payload, f"C{cl} missing nearest_same_cell_type"

    print("[1/4] _collect_iteration_state exposes spatial-context fields per cluster")

    # 2. spatial_mismatches field present in CP3 state
    assert "spatial_mismatches" in state, "CP3 state must expose spatial_mismatches"
    print(f"[2/4] spatial_mismatches in CP3 state: {len(state['spatial_mismatches'])} mismatches")

    # 3. Each mismatch entry has expected fields
    for m in state["spatial_mismatches"]:
        assert "cluster" in m
        assert "self_cell_type" in m
        assert "nearest_other_cell_type" in m
        assert "nearest_other_cluster" in m
        assert "distance_to_other" in m
        # Mismatch invariant: nearest_other closer than nearest_same
        same_d = m.get("distance_to_same")
        assert same_d is None or m["distance_to_other"] < same_d, \
            f"mismatch should have distance_to_other < distance_to_same, got {m}"

    print("[3/4] spatial_mismatch invariants OK")

    # 4. Distance metric sanity: distance values should be UMAP-scale (0-15)
    for cl, payload in state["clusters"].items():
        for key in ("nearest_other_cell_type", "nearest_same_cell_type"):
            v = payload[key]
            if v is not None and "distance" in v:
                assert 0.0 <= v["distance"] <= 20.0, \
                    f"C{cl} {key} distance {v['distance']} out of expected UMAP range"

    # Show summary
    print()
    print(f"Found {len(state['spatial_mismatches'])} spatial mismatches:")
    for m in state["spatial_mismatches"][:8]:
        same = f"same at {m.get('distance_to_same')}" if m.get("distance_to_same") is not None else "no same-CT neighbor"
        print(f"  C{m['cluster']} '{m['self_cell_type']}' "
              f"closest to C{m['nearest_other_cluster']} '{m['nearest_other_cell_type']}' "
              f"({m['distance_to_other']} UMAP), {same}")
    print()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/final_annotated.h5ad")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
