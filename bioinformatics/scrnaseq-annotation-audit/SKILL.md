---
name: scrnaseq-annotation-audit
description: "Audit cell type annotations against h5ad expression data."
tags: [bioinformatics, scrnaseq, annotation, audit, llm, single-cell]
version: "1.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [bioinformatics, scrnaseq, annotation, audit, llm, single-cell]
    related_skills: [scrnaseq-auto-annotation, scrnaseq-clustering-quality-diagnosis, single-cell-annotation-guide]
---

# scRNA-seq Annotation Audit & Correction

## When to Use

- After `mode_auto` finishes, to independently verify cell_type assignments
- When reviewing any annotated h5ad for misannotation patterns
- When other AI needs structured audit output to decide corrections
- When constructing `cluster_annotations.json` for `mode_annotate --cluster-annotations`

## Purpose

Independent, expression-based verification of cell type labels. Reads ONLY the
h5ad's actual state (`adata.obs["leiden"]`, `adata.obs["cell_type"]`, `adata.X`,
`adata.uns["rank_genes_groups"]`) — no LLM trust, no annotation_report bias.

Produces structured JSON for downstream AI review and correction.

## Architecture

```
mode_auto → writes h5ad + audit_report.json
                   ↓
        _audit_annotations(adata, report_dir, tissue)
                   ↓
        annotation_audit.json       ← per-cluster verdicts (KEEP/RENAME/REVIEW/DROP)
        cluster_annotations_draft.json  ← actionable corrections (corrected_cell_type=placeholder)
                   ↓
        Other AI reviews draft → fills corrected_cell_type
                   ↓
        mode_annotate --cluster-annotations draft.json → corrected h5ad
```

### Key Design Decision

`_audit_annotations` is **NOT part of mode_auto's iteration loop**. It is a
standalone verification step that runs once after mode_auto completes. Its
output is for **other AI to review**, not for mode_auto to self-correct.

## Verdict Logic

Each cluster gets one verdict based on **structural checks only** (no hardcoded
marker panels):

| Verdict | Condition | Action |
|---------|-----------|--------|
| KEEP | No structural issues detected | No correction needed |
| REVIEW | n_cells < 20 (tiny cluster) OR Jaccard > 0.3 with same cell_type cluster (possible over-split) | AI decides if merge/rename needed |
| DROP_ARTIFACT | `audit_report.json` flagged this cluster during mode_auto iterations | Likely ambient RNA artifact |

### Why no marker-based verdicts

Earlier versions used `_LINEAGE_MARKER_PANELS` (hardcoded canonical markers)
to verify annotations. This was removed because:
- A general-purpose tool should not contain tissue-specific marker lists
- Marker panels bias the audit toward tissues the developer anticipated
- LLM annotation already uses DEG-based and PubMed-verified reasoning
- Structural checks (cluster size, Jaccard overlap, iterative QC flags)
  catch the real problems without domain-specific assumptions

### Stale flag detection

`mode_auto` sometimes re-annotates a cluster on a later iteration, leaving the
`audit_report.json` flag stale. The audit flags the cluster as DROP_ARTIFACT
if it appears in the misannotated set — downstream AI should verify whether
the flag is still valid by checking the cluster's current DEGs.

## Pitfalls

### ❌ Trusting annotation_report.tsv cluster list without checking h5ad

`annotation_report.tsv` is a cumulative report from ALL mode_auto iterations,
including clusters that were later dropped by `whole_cluster_filter`. The final
h5ad may lack clusters 1, 11, 17 (Uterus_scTE) or cluster 4 (ovaries_cellranger).

**Always load the actual h5ad and check `adata.obs["leiden"].unique()` before
creating cluster_annotations.json.** User correction: "为什么你检查是否注释正确的
时候没有用h5ad,凭空猜测吗" — if you had loaded the h5ad, you would not have
included non-existent clusters in the JSON.

Detection:
```python
import anndata as ad
a = ad.read_h5ad("<auto>.h5ad")
print(sorted(a.obs["leiden"].astype(str).unique(), key=int))
```

Cross-reference with `audit_report.json` `misannotated` field to see WHY
clusters were dropped:
```python
import json
audit = json.load(open("<reports>/audit_report.json"))
for it in audit.get("iterations", []):
    for ma in it.get("misannotated", []):
        print(ma["flagged_cluster"], ma["cell_type"],
              "jaccard=", ma["marker_jaccard"])
```

### ❌ Pandas Categorical: `add_categories(inplace=True)` broken on newer pandas

When `mode_annotate` assigns a new cell_type value not in the existing
categories, pandas raises `TypeError: Cannot setitem on a Categorical with
a new category`. The fix uses `set_categories` (not `add_categories`):

```python
col = adata.obs["cell_type"]
if isinstance(col.dtype, pd.CategoricalDtype):
    if corrected not in col.cat.categories:
        new_cats = col.cat.categories.tolist() + [corrected]
        adata.obs["cell_type"] = col.cat.set_categories(new_cats)
adata.obs.loc[mask, "cell_type"] = corrected
```

`add_categories(inplace=True)` raises `TypeError: got an unexpected keyword
argument 'inplace'` on pandas 2.x. Always use `set_categories` which returns
a new Categorical.

### ❌ Hardcoding marker panels in audit scripts

General-purpose tools must NOT contain tissue-specific marker lists. Marker
panels embedded in code bias the audit toward tissues the developer anticipated
and break when users run different tissue types. Use structural checks
(cluster size, Jaccard overlap, iterative QC flags) instead. If marker-based
verification is needed, it should come from external user-provided files or
LLM-generated canonical_markers (which are data-driven, not hardcoded).

### ❌ OPENBLAS segfault on k-NN with many threads

`NearestNeighbors` computation in `_audit_annotations` can segfault when
OPENBLAS tries to allocate too many thread-local arrays. Fix:

```bash
export OPENBLAS_NUM_THREADS=1
```

Set this in any script that calls `_audit_annotations` or any function that
uses sklearn k-NN on high-core machines.

### ❌ references.tsv empty rows = LLM couldn't verify

Clusters with 0 rows in `references.tsv` are LLM annotations where PubMed
verification failed. This is a strong signal that the label is speculative.
Combined with expression checks, empty-references clusters should be reviewed.

## Output Files

| File | Content | Consumer |
|------|---------|----------|
| `annotation_audit.json` | Per-cluster verdict + expression data | Other AI |
| `cluster_annotations_draft.json` | Correction draft (corrected_cell_type=placeholder) | Other AI → mode_annotate |
| `h5ad_path` field in audit JSON | Source h5ad path (stamped by mode_auto) | Other AI for data loading |

## Usage

### From mode_auto (automatic)

mode_auto calls `_audit_annotations` at the end. No user action needed.
Output goes to `<output>_reports/annotation_audit.json` and
`<output>_reports/cluster_annotations_draft.json`.

### Standalone on any h5ad

```python
import anndata as ad
import sys; sys.path.insert(0, ".../scanpy/bin")
import scRNAseq as S

a = ad.read_h5ad("<auto>.h5ad")
a._h5ad_source = "<auto>.h5ad"  # stamped into audit JSON
S._audit_annotations(a, report_dir="<auto>_reports", tissue="Uterus")
```

### Applying corrections

After reviewing `cluster_annotations_draft.json` and filling in
`corrected_cell_type`:

```bash
python scRNAseq.py --mode annotate \
    --input <auto>.h5ad --output <annotated>.h5ad \
    --cluster-annotations <draft>.json
```

## Rules

- **No fallback logic** — if a value is wrong, fail loudly
- **Always verify h5ad state** — load actual adata, don't trust report files alone
- **Audit is standalone** — it verifies, it does not self-correct mode_auto output
- **Draft is for AI review** — corrected_cell_type is a placeholder until AI fills it