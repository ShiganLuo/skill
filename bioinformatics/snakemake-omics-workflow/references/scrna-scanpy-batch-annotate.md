# Scanpy scRNA-seq Pipeline Architecture (2026-09)

## Pipeline order

```
qc (per sample) → merge (+ gene_type annotation) → auto → advanced → de
```

- `scanpy_cluster` and `scanpy_annotate` rules were REMOVED
- `scanpy_auto` replaces them — calls `mode_auto` which iterates: cluster → AI annotate → QC → filter → re-cluster
- `mode_merge` now calls `annotate_gene_type()` to add `adata.var['gene_type']` (TE/protein_coding/lncRNA/etc.)

## mode_auto: iterative autonomous pipeline

Each iteration:
1. Normalize → HVG → PCA → Harmony → UMAP → Leiden clustering
2. LLM annotates each cluster (prompt includes top DEGs, tissue, QC metrics, UMAP distances)
3. Quality analysis: flag clusters with low genes/counts or TE dominance
4. Cell type separation check (same-type clusters too far in UMAP → adjust resolution)
5. If flagged: filter cells (not clusters), re-cluster from raw counts
6. If clean: save final h5ad + reports

Resolution auto-adapts between iterations (e.g., 0.8 → 0.2 if over-clustered).

## LLM-generated audit reports

Instead of hardcoded audit points, mode_auto collects iteration context into a `ctx` dict:
```python
ctx = {
    "params": {...},
    "initial_cells": N,
    "iterations": [{
        "resolution": 0.8,
        "n_clusters": 22,
        "annotations": {cluster_id: {cell_type, confidence, reasoning, markers}},
        "quality_reports": [{cluster, should_filter, flags}],
        "filter_n_removed": N,
        "outcome": "clean" | "filter" | "max_iterations"
    }, ...]
}
```

At the end, `_generate_audit_report()` calls the LLM with the full context to produce:
- `audit_report.md` — structured report with per-iteration summaries, decisions, rationale
- `run.sh` — reproducible bash script

**Pitfall**: LLM-generated run.sh may use wrong module name (e.g., `python -m scrna_auto_mode` instead of `python scRNAseq.py --mode auto`) or wrong arg format (underscores vs hyphens). The prompt should explicitly specify the actual CLI command format.

## gene_type annotation

`annotate_gene_type(adata, te_bed, gene_tsv)` labels genes in `adata.var['gene_type']`:
- Genes in te_bed → `"TE"`
- Genes in gene_tsv → their gene_type (protein_coding, lncRNA, etc.)
- Unmatched → `"unknown"`

Reference files flow: `genome.references.<species>.te_bed` / `.geneIDAnno` → subworkflow config → module config → CLI args `--te-bed` / `--gene-tsv` → mode_merge.

## Conditional DAG via node.py (NOT smk conditionals)

**Rule**: Rules define static inputs/outputs. Control logic (which rules to run) belongs in `node.py`'s `runscRNAseq()`, NOT in `if has_llm:` blocks in .smk.

```python
# node.py — controls which outfiles are requested
for tissue in tissue_samples.keys():
    for counter in counters:
        ann = datajson["Params"].get(counter, {}).get("annotate", {})
        if ann.get("llm_method"):
            outfiles.append(f".../{tissue}_{counter}_advanced.h5ad")
        else:
            outfiles.append(f".../{tissue}_{counter}_merged.h5ad")
```

Snakemake builds DAG from outfiles → only rules whose outputs are transitive dependencies run. No LLM config → merge is the terminal node → auto/advanced/de rules are never in the DAG.

## Key files

- `modules/scanpy/bin/scRNAseq.py` — all mode functions (qc, merge, auto, advanced, de)
- `modules/scanpy/scanpy.smk` — rule definitions (static inputs/outputs)
- `subworkflow/scRNAseq.smk` — subworkflow orchestration, config passthrough
- `node.py::runscRNAseq()` — outfiles control, LLM env injection
- `config/scRNAseq.json` — defaults for all counters (scTE, cellranger)
