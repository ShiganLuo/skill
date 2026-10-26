---
name: scrnaseq-cross-group-ppt
description: "Use for scRNAseq cross-group PPTs with DA/DEG/GO/TE data."
tags:
  - pptx
  - scRNAseq
  - report
  - bioinformatics
triggers:
  - scRNAseq report PPT
  - cross-group analysis presentation
  - pseudobulk DEG report
---

# scRNAseq Cross-Group Analysis PPT

## When to Use

When generating a scientific report PPT from scRNAseq pseudobulk DEG analysis integrating DA (scCODA), gene DEG, GO/KEGG enrichment, and TE fraction analysis.

## Directory Structure

```
results/DEG/
├── deg_pseudobulk_gene/{tissue}_{comparison}/{cell_type}/
│   ├── *_DEG.csv, *_volcano.png
│   └── go_kegg/ (go_up.csv, go_back_to_back.png, kegg_*)
└── deg_pseudobulk_te/{tissue}_{comparison}/{cell_type}/
    └── *_volcano.png
```

**Note**: path = `results/DEG/deg_pseudobulk_gene/` (extra DEG level).

## Multi-Slide Pattern Per Scientific Question

NEVER cram everything on one slide. Split into 2-4 slides:

**Slide A: DA + Gene DEG** — DA barplot + volcano + Top DEGs + GO table + conclusion

**Slide B: GO/KEGG Figures** — go_back_to_back.png + kegg_back_to_back.png + top terms + conclusion

**Slide C: TE Volcano** — TE volcano from deg_pseudobulk_te + TE evidence + conclusion

## EVERY Slide Needs a Conclusion

User explicitly required: every slide must have `结论：...` with biological interpretation. Data points alone (①②③) are NOT conclusions.

## Helper Functions

```python
def _go_dir(tissue, comparison, cell_type):
    return DEG / f"deg_{tissue}" / comparison / cell_type / "go_kegg"

def _te_dir(tissue, comparison, cell_type):
    return BASE / "DEG" / "deg_pseudobulk_te" / f"deg_{tissue}" / comparison / cell_type

def _enrichment_slide(prs, title, ct_tissue, ct_comparison, ct_name, conclusion=None):
    slide = make_slide(prs, title)
    go_dir = _go_dir(ct_tissue, ct_comparison, ct_name)
    for name, x in [("go_back_to_back.png", MARGIN_L), ("kegg_back_to_back.png", 6.8)]:
        p = go_dir / name
        if p.exists(): _add_picture(slide, str(p), x, 0.9, 6.2, 5.0)
    go_up = load_go_terms(go_dir, "up", n=3)
    go_dn = load_go_terms(go_dir, "down", n=3)
    summary = []
    if go_up: summary.append(f"GO ↑: {', '.join([t['term'][:30] for t in go_up[:2]])}")
    if go_dn: summary.append(f"GO ↓: {', '.join([t['term'][:30] for t in go_dn[:2]])}")
    if conclusion: summary.append(f"结论：{conclusion}")
    if summary: _bullets(slide, MARGIN_L, 6.0, 12.4, 1.3, summary, 10)

def load_go_terms(go_dir, direction="up", n=5):
    csv_path = Path(go_dir) / f"go_{direction}.csv"
    if not csv_path.exists(): return []
    df = pd.read_csv(csv_path)
    return [{"term": str(r.get("Description",""))[:50], "padj": float(r.get("p.adjust",1)),
             "genes": str(r.get("geneID",""))[:60]} for _, r in df.head(n).iterrows()]
```

## Pitfalls

- **One slide cannot hold everything** — user: "一个slide明显放不下,就不会拆开来吗"
- **Every slide needs conclusion** — user: "每张slide怎么都没有结论"
- **DEG path**: `results/DEG/deg_pseudobulk_gene/` not `results/deg_pseudobulk_gene/`
- **GO dir name**: `go_kegg` not `go_macaque` — no species in name
- **DA filename**: no tissue prefix. `da_sccoda_{comp}_effects_barplot.png`
- **pval_adj NaN**: do NOT fillna with pval — mark with asterisk on plot
- **Apptainer --no-home**: prevents host R library leaking (GOSemSim conflict)
- **go-kegg.r empty input**: early return in run_pipeline when 0 genes
- **Volcano for all cell types**: remove `.head(3)` limit in pseudobulk.py
- **TE images must match conclusions**: if conclusion says "LTR family主导", use family-level bar chart (from `te/*_family_top_changes.png`), NOT gene-level TE volcano. Generate family plots with `mean > 0.01` filter to exclude artifact genes (IAPP, L1TD1) with near-zero expression
- **go-kegg.r bitr crash**: wrap `bitr()` in `tryCatch` — returns empty df when no valid SYMBOL keys. Also check `nrow == 0` BEFORE dplyr operations in `plot_back_to_back`
- **go-kegg.r separator**: use `data.table::fread()` for auto CSV/TSV detection instead of `read.csv(sep="\t")`
- **Natural language**: use clear Chinese, not jargon. ❌ "padj 未校正" ✓ "表达量过低，统计检验未检出"
- **Enrichment script**: use `enrichment.py` (in `utils/`) instead of bash loop for GO/KEGG + TE subfamily. It handles skip-existing, Apptainer isolation, and TE family aggregation in one pass. Run: `python enrichment.py --deg-dir ... --te-dir ... --te-bed ... --skip-existing`
- **TE subfamily aggregation**: `enrichment.py` generates `te_subfamily/te_subfamily_summary.csv` + `te_subfamily_log2FC.png` per cell type. Filter `mean_baseMean > 0.01` to exclude artifact genes (IAPP, L1TD1) with near-zero expression but inflated log2FC
- **h5ad annotation**: `annotate_gene_type.py` adds `gene_type`/`family_id`/`class_id` to both `.var` and `.raw.var`. Requires `ad.settings.allow_write_nullable_strings = True` for anndata write. Use `--replace` to overwrite (creates .bak backup)
- **Apptainer isolation**: use `--cleanenv --no-home -B $(pwd):$(pwd)` not `--home /tmp/sandbox`. The `-B` bind mount is needed because `--no-home` disables automatic home mount
