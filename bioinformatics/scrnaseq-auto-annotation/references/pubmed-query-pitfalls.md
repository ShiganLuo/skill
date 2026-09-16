# PubMed Query Pitfalls for scRNAseq Auto Mode

## Critical: Verification Query Must NOT Include Tissue

When verifying tissue markers (Step 0.5 `_verify_tissue_markers`), the PubMed
query MUST use `{gene} AND {cell_type}` only. Do NOT include tissue context.

### Why
`_search_pubmed(gene, cell_type, tissue)` constructs: `{gene} AND {cell_type} AND {tissue}`

For verification, this is too specific:
- `CD68 AND Macrophage AND macaque (Macaca mulatta) ovaries` → 0 results
- `PECAM1 AND Endothelial AND macaque (Macaca mulatta) ovaries` → 0 results
- `FOXL2 AND Granulosa AND macaque (Macaca mulatta) ovaries` → 0 result

These are well-known canonical markers that fail because the tissue string
is too specific for PubMed's search index.

### Fix
In `_verify_tissue_markers`, call with `tissue=""`:
```python
refs = _search_pubmed(gene, ct, tissue="", max_results=1)
```

This gives `{gene} AND {cell_type}` which returns real results for canonical markers.

### When to use tissue in the query
The full 3-part query `{gene} AND {cell_type} AND {tissue}` is appropriate for
the per-cluster annotation PMID gate (Step 2 / `_run_one_annotation_pass`), where
the goal is to find literature specifically supporting the marker in that tissue
context. The verification step's goal is different — just confirm the marker gene
is real.

## Verification Results (ovary test run)
With `tissue=""`: 10/45 verified, 35/45 unverified → expected (PubMed search
for gene+cell_type still misses some due to naming variations)
With `tissue="macaque ovaries"`: 0/45 verified → broken

## LLM Provider Notes
- Xiaomi mimo-v2.5-pro via `https://token-plan-cn.xiaomimimo.com/v1` (OpenAI-compatible)
- Uses `openai` library internally (httpx2 logger shows the requests)
- Model name must be exact: `mimo-v2.5-pro` (not `MiniMax-M3`)
- `response_format=json_object` may be rejected — code has fallback

## ❌ PubMed XML Parsing NoneType Bug

`_search_pubmed` crashes on some genes (observed: TAGLN) with:
```
'NoneType' object is not subscriptable
```

Root cause: `ET.fromstring(xml_text)` succeeds but some `<PubmedArticle>`
elements have missing `<PMID>` or `<ArticleTitle>` sub-elements. The code
does `pmid_el.text` which returns None, then tries to subscript it.

The function has a `try/except` around the whole search, so it doesn't crash
the pipeline — it just returns empty results and logs a warning. But the
warning message is misleading (looks like a real error).

Fix needed: add null checks in the XML parsing loop:
```python
pmid_el = article.find(".//PMID")
if pmid_el is None or pmid_el.text is None:
    continue
```
