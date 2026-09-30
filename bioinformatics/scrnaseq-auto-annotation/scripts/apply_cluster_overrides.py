#!/usr/bin/env python3
"""Apply cluster_annotations.json overrides to an h5ad and write a corrected copy.

This is the post-mode_auto correction step. After mode_auto writes
``<output>_auto.h5ad`` and the reviewer produces
``<output>/plots/<pipeline>/auto/cluster_annotations.json``, this
script applies the corrections to a new h5ad without re-running the
LLM annotation.

Usage:
    python scripts/apply_cluster_overrides.py \
        --input  output/<tissue>_cellranger_auto.h5ad \
        --json   output/<tissue>/plots/cellranger/auto/cluster_annotations.json \
        --output output/<tissue>_cellranger_corrected.h5ad

The script invokes ``mode_annotate`` with ``--cluster-annotations``,
which:
  1. Reads the JSON schema {cluster_id: {original, corrected, reasoning}}
  2. Validates: file exists, valid JSON, top-level dict, every value
     is a dict with non-empty ``corrected_cell_type``, every cluster
     id is present in adata.obs[annotate_group] (default: leiden),
     and ``adata.obs["cell_type"]`` already exists
  3. Overwrites cell_type for the listed clusters (handles pandas
     Categorical dtype via set_categories so new labels don't crash)
  4. Stores audit trail as DataFrame in
     ``adata.uns["cluster_annotation_overrides"]`` (round-trips
     through h5ad)

Any validation failure raises (no silent skip). JSON-level duplicate
cluster ids are merged by Python's json.loads (last value wins) —
defensive design note in case a future stricter parser is desired.

The original cell_type label for each affected cluster is captured
from adata.obs BEFORE mutation and stored in the audit, so reviewers
can trace original -> corrected -> reasoning.

Exit codes:
    0 = all overrides applied, h5ad written
    non-zero = validation or runtime error (stderr message explains)

Pitfalls covered:
    - pandas Categorical refuses setitem with new category -> extended
      via set_categories before assignment
    - anndata uns requires homogeneous types -> list of mixed dicts
      fails; we wrap as DataFrame so it persists through h5ad
    - cluster id may be int in leiden column but str in JSON -> both
      compared via astype(str)
"""
import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

# Path setup so this works from any cwd. The script sits in
# skills/bioinformatics/scrnaseq-auto-annotation/scripts/; the
# scRNAseq module lives at <Omics-repo>/modules/scanpy/bin/scRNAseq.py.
# Default to the well-known repo path, allow override via env.
DEFAULT_SC_PATH = "/home/<USER>/Data/genomeStability/workflow/Omics/modules/scanpy/bin"
SC_PATH = os.environ.get("SCRNASEQ_BIN_PATH", DEFAULT_SC_PATH)
sys.path.insert(0, SC_PATH)


def main():
    ap = argparse.ArgumentParser(
        description="Apply cluster_annotations.json overrides to h5ad"
    )
    ap.add_argument("--input", required=True, help="Input h5ad (post mode_auto)")
    ap.add_argument("--json", required=True,
                    help="Path to cluster_annotations.json")
    ap.add_argument("--output", required=True,
                    help="Path to write the corrected h5ad")
    ap.add_argument("--annotate-group", default="leiden",
                    help="Obs column defining clusters (default: leiden)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        raise SystemExit(f"input h5ad not found: {args.input}")
    if not os.path.isfile(args.json):
        raise SystemExit(f"cluster_annotations JSON not found: {args.json}")

    # Lazy import scRNAseq to avoid pulling scanpy when --help
    import anndata as ad  # noqa: F401
    try:
        from scRNAseq import mode_annotate
    except ImportError as exc:
        raise SystemExit(
            f"could not import scRNAseq from {SC_PATH}: {exc}\n"
            f"set SCRNASEQ_BIN_PATH env var to the directory containing "
            f"scRNAseq.py if it is not at the default location"
        ) from exc

    a = ad.read_h5ad(args.input)
    print(f"[apply_cluster_overrides] loaded {args.input}", flush=True)
    print(f"  shape={a.shape} cell_type={'cell_type' in a.obs.columns}",
          flush=True)

    mode_annotate(
        a,
        output=args.output,
        marker_file="",
        celltypist_model="",
        annotate_group=args.annotate_group,
        plot_dir="",
        cluster_annotations=args.json,
    )
    print(f"[apply_cluster_overrides] wrote {args.output}", flush=True)

    # Show audit
    audit = a.uns.get("cluster_annotation_overrides")
    if audit is not None and len(audit) > 0:
        print(f"\nAudit ({len(audit)} overrides):", flush=True)
        for _, row in audit.iterrows():
            print(f"  cluster {row['cluster_id']} ({row['n_cells']} cells): "
                  f"{row['original_cell_type']} -> {row['corrected_cell_type']}",
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())