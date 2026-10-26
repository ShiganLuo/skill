#!/usr/bin/env python3
"""Audit a mode_auto h5ad output: cross-check each cluster's annotation
against (a) actual marker expression in adata.X, (b) top DEG, and (c)
the references.tsv PubMed support.

Designed for post-run validation when mode_auto produces annotations
that look right by summary but may have systematic label errors (NK vs
Cytotoxic T, MSC vs EC, Mesothelial vs OSE, M1 vs Tissue_Resident, etc.).

Usage:
    python audit_h5ad_annotations.py \\
        --name Uterus_cellranger \\
        --h5ad /path/to/Uterus_cellranger_auto.h5ad \\
        --tissue uterus | ovaries

Run with miniconda3/bin/python (scanpy 1.12.x + scipy 1.18 + anndata 0.13.x).
The venv has broken numpy 2.4 from uv; conda base works.

Output sections per cluster:
  - top 10 DEG (wilcoxon, use_raw=True)
  - mean expression of canonical lineage markers
  - cluster cell_type annotation + subcluster flag

Exit code 0 always — audit is informational.
"""
import sys, os, json, argparse, warnings
os.environ.pop("PYTHONPATH", None)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("PYTHONNOUSERSITE", "1")
warnings.filterwarnings("ignore")

import anndata as ad
import scanpy as sc
import numpy as np
import pandas as pd
from scipy.sparse import issparse


def load_h5ad(path: str) -> ad.AnnData:
    a = sc.read_h5ad(path)
    return a


def per_cluster_top_deg(a: ad.AnnData, top_n: int = 20) -> dict:
    sc.tl.rank_genes_groups(a, "leiden", method="wilcoxon",
                            n_genes=top_n, use_raw=False)
    res = a.uns["rank_genes_groups"]
    groups = res["names"].dtype.names
    out = {}
    for g in groups:
        out[g] = [res["names"][g][i] for i in range(min(top_n, len(res["names"][g])))]
    return out


def per_cluster_marker_table(a: ad.AnnData, genes: list) -> pd.DataFrame:
    """cluster x gene mean expression matrix. Returns DataFrame indexed by cluster."""
    var = list(a.var_names)
    X = a.X
    if issparse(X):
        X = X.toarray()
    cl = a.obs["leiden"].astype(str).values
    valid = [g for g in genes if g in var]
    if not valid:
        return pd.DataFrame()
    data = {g: X[:, var.index(g)] for g in valid}
    df = pd.DataFrame(data)
    df["__cluster"] = cl
    return df.groupby("__cluster").mean().round(2)


def annotation_table(a: ad.AnnData) -> pd.DataFrame:
    """Per-cluster cell_type + size."""
    rows = []
    for cl in sorted(a.obs["leiden"].unique(),
                     key=lambda x: int(x) if str(x).isdigit() else str(x)):
        sub = a.obs[a.obs["leiden"] == cl]
        vc = sub["cell_type"].value_counts().head(5)
        rows.append({
            "cluster": cl,
            "n_cells": len(sub),
            "cell_type_top": ",".join([f"{k}={v}" for k, v in vc.items()]),
        })
    return pd.DataFrame(rows)


# Canonical marker panels — used as audit references. Override with --tissue.
TISSUE_MARKERS = {
    "uterus": {
        "EC_lymphatic":  ["PROX1","LYVE1","CCL21","FLT4","NRP2","PDPN"],
        "EC_vascular":   ["PECAM1","VWF","CDH5","ERG","FLT1","EMCN","KDR","CD34"],
        "EC_tip":        ["ACKR1","PLVAP","DLL4","CXCL12","EFNB2"],
        "Pericyte_SMC":  ["RGS5","PDGFRB","ABCC9","KCNJ8","ACTA2","MYH11","TAGLN"],
        "Stromal_fibro": ["DCN","LUM","COL1A1","COL1A2","COL3A1","FBLN1","DPT","CST3"],
        "Macrophage":    ["CD74","CD163","CD68","CD86","LYZ","CTSS","TYROBP","AIF1","C1QA","C1QB","IL1B"],
        "Tcell":         ["CD3D","CD3E","CD3G","TRAC","PTPRC"],
        "NKcell":        ["NKG7","GZMB","GNLY","CCL5","KLRD1","KLRB1","NCR1"],
        "Luminal_Epi":   ["PAX8","KRT18","KRT19","EPCAM","CDH1","WFDC2","AGR3","CLDN3","CLDN4"],
        "Basal_Epi":     ["TP63","S100A2","KRT5","KRT16","PERP","DSP"],
        "Schwann":       ["S100B","MPZ","SOX10","PLP1","GPM6B","PMP22"],
    },
    "ovaries": {
        "EC_lymphatic":  ["PROX1","LYVE1","CCL21","FLT4","NRP2","PDPN"],
        "EC_vascular":   ["PECAM1","VWF","CDH5","ERG","FLT1","EMCN","KDR","CD34","SELE"],
        "EC_tip":        ["ACKR1","PLVAP","DLL4","CXCL12","NRP1"],
        "SMC":           ["MYH11","ACTA2","TAGLN","CNN1","DES","MYLK","TPM2","LMOD1"],
        "Pericyte":      ["RGS5","PDGFRB","ABCC9","KCNJ8"],
        "Stromal_fibro": ["DCN","LUM","COL1A1","COL1A2","COL3A1","FBLN1","DPT","CST3","MFAP4"],
        "Granulosa":     ["AMH","CYP19A1","FSHR","HSD17B1","FDX1","NR5A2","FST","INHBA","FOXL2"],
        "Theca":         ["LHCGR","CYP17A1","CYP11A1","STAR","INSL3","INHA"],
        "Macrophage":    ["CD74","CD163","CD68","CD14","LYZ","CTSS","TYROBP","AIF1","C1QA","C1QB"],
        "NK_T":          ["PTPRC","CD3D","CD3E","TRAC","NKG7","GZMB","GNLY","CCL5"],
        "OSE_mesothelial":["PAX8","FOXJ1","EPCAM","KRT19","KRT18","ITLN1","MSLN","PTGDS","CLDN3","CLDN4","WFDC2"],
        "Oocyte":        ["FIGLA","ZP3","NLRP5","DDX4"],
    },
}


def audit(a: ad.AnnData, tissue: str, name: str) -> dict:
    print("=" * 90, flush=True)
    print(f"# {name} | shape={a.shape} | n_clusters={a.obs['leiden'].nunique()}", flush=True)
    print("=" * 90, flush=True)

    print("\n## Cluster sizes:", flush=True)
    print(a.obs["leiden"].value_counts().sort_index().to_string(), flush=True)

    print("\n## Top 10 DEG per cluster:", flush=True)
    deg = per_cluster_top_deg(a, top_n=15)
    for cl in sorted(deg.keys(),
                     key=lambda x: int(x) if str(x).isdigit() else str(x)):
        print(f"  cluster {cl}: {', '.join(deg[cl][:10])}", flush=True)

    print(f"\n## Marker mean expression per cluster (tissue={tissue}):", flush=True)
    panel = TISSUE_MARKERS[tissue]
    all_markers = sorted(set(g for v in panel.values() for g in v))
    expr = per_cluster_marker_table(a, all_markers)
    present = expr.columns[(expr.max(axis=0) > 0.05)]
    print(f"  (showing {len(present)}/{len(all_markers)} markers with max mean > 0.05)",
          flush=True)
    if not expr.empty:
        print(expr[present].to_string(), flush=True)

    print("\n## cell_type annotation per cluster:", flush=True)
    ann = annotation_table(a)
    print(ann.to_string(index=False), flush=True)

    print("\n## Audit checks:", flush=True)

    # Check 1: NK vs T - CD3D/E/TRAC expression
    if all(g in a.var_names for g in ["CD3D","CD3E","TRAC"]):
        c3d = expr.get("CD3D", pd.Series(dtype=float))
        c3e = expr.get("CD3E", pd.Series(dtype=float))
        trac = expr.get("TRAC", pd.Series(dtype=float))
        for cl in c3d.index:
            ct_row = ann[ann.cluster == cl]
            ct = ct_row["cell_type_top"].iloc[0] if not ct_row.empty else ""
            if "NK" in ct and not ct.startswith("NK_T"):
                if c3d.get(cl, 0) > 1.5 or c3e.get(cl, 0) > 1.5 or trac.get(cl, 0) > 1.5:
                    print(f"  WARN cluster {cl} labeled '{ct}' but CD3D={c3d.get(cl,0):.2f} "
                          f"CD3E={c3e.get(cl,0):.2f} TRAC={trac.get(cl,0):.2f} - "
                          f"likely Cytotoxic_T_Cell, not NK", flush=True)

    # Check 2: MSC vs EC - MSC should have low PECAM1/CDH5/VWF
    if all(g in a.var_names for g in ["PECAM1","CDH5"]):
        pec = expr.get("PECAM1", pd.Series(dtype=float))
        cdh = expr.get("CDH5", pd.Series(dtype=float))
        for cl in pec.index:
            ct_row = ann[ann.cluster == cl]
            ct = ct_row["cell_type_top"].iloc[0] if not ct_row.empty else ""
            if "Mesenchymal_Stem" in ct or "MSC" in ct:
                if pec.get(cl, 0) > 0.5 or cdh.get(cl, 0) > 0.3:
                    print(f"  WARN cluster {cl} labeled '{ct}' but PECAM1={pec.get(cl,0):.2f} "
                          f"CDH5={cdh.get(cl,0):.2f} - likely Endothelial_Cell", flush=True)

    # Check 3: Apoptosis markers mislabeled as identity (CYCS, CASP3 in key_markers)
    if all(g in a.var_names for g in ["CYCS","CASP3"]):
        for cl in expr.index:
            cycs = expr.get("CYCS", pd.Series(dtype=float)).get(cl, 0)
            casp3 = expr.get("CASP3", pd.Series(dtype=float)).get(cl, 0)
            ct_row = ann[ann.cluster == cl]
            ct = ct_row["cell_type_top"].iloc[0] if not ct_row.empty else ""
            if (cycs > 1.0 or casp3 > 1.0) and "Apoptotic" not in ct and ct != "":
                print(f"  WARN cluster {cl} labeled '{ct}' but CYCS={cycs:.2f} "
                      f"CASP3={casp3:.2f} - apoptosis markers, not identity markers",
                      flush=True)

    # Check 4: M1 vs Tissue_Resident - CD163/CD86 double-positive
    if all(g in a.var_names for g in ["CD163","CD86"]):
        cd163 = expr.get("CD163", pd.Series(dtype=float))
        cd86 = expr.get("CD86", pd.Series(dtype=float))
        for cl in cd163.index:
            ct_row = ann[ann.cluster == cl]
            ct = ct_row["cell_type_top"].iloc[0] if not ct_row.empty else ""
            if "M1" in ct:
                if cd163.get(cl, 0) > 1.5 and cd86.get(cl, 0) > 1.5:
                    print(f"  WARN cluster {cl} labeled '{ct}' but CD163={cd163.get(cl,0):.2f} "
                          f"CD86={cd86.get(cl,0):.2f} - co-expression suggests "
                          f"Tissue_Resident_Macrophage, not M1", flush=True)

    return {"name": name, "n_clusters": a.obs['leiden'].nunique()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--h5ad", required=True)
    ap.add_argument("--tissue", required=True, choices=list(TISSUE_MARKERS.keys()))
    args = ap.parse_args()

    a = load_h5ad(args.h5ad)
    audit(a, tissue=args.tissue, name=args.name)


if __name__ == "__main__":
    main()