# Canonical Marker Panel Redraw (literature panels + tiered specificity)

**Context**: when `rank_genes_groups` top-10 DEG produces noisy markers on scTE
data (TE / repeat / rRNA / MT dominating), or when the user audits PNG subplot
titles against a hand-curated marker file and wants a 1:1 match between the
table and the PNG, replace the LLM/DEG marker list with a literature-canonical
panel + tiered specificity filter.

## When to use

- DEG-top-N markers include TE / rRNA / MT / IG / RPS / RPL / HSP / repeat
  entries (`Harlequin-int`, `HERVE_a-int`, `LSU_rRNA_eukarya`, etc.)
- A cell type has <10 markers that pass a strict specificity cutoff
  (e.g. luminal vs glandular epithelium share KRT/EPCAM/CLDN markers)
- User says "marker 图上写的 marker 和我审核的文件不一一对应" — the audit
  file must match the rendered PNG exactly

## Panel sources (literature-canonical)

Authoritative reviews/atlases per tissue:

- **Human uterus / endometrium**: Garcia-Alonso 2021 (endometrial atlas),
  HECA (Nature Genetics 2024), Wang 2020 (menstrual cycle scRNA-seq)
- **Macaque ovary**: Fan 2019 (PMID 31606144), Richards 2018 (PMID 29352662)
- **VSMC contractile vs synthetic**: Yap 2021 PMC8545254, Rensen 2007
- **Endothelial subtypes**: Travaglino 2022, Garlanda 2024
- **Macrophage**: Davies 2013, Van Gorp 2010

Build a Python dict per cell type with 15-30 candidate markers per panel
(some will be filtered out by the data; some will overlap with related
panels — overlap is fine, the specificity filter resolves it).

## Tiered specificity filter (always get 10 markers)

Three-tier filter so each cluster gets a full panel even when many
literature candidates are shared with neighbors:

```python
def pick_top10(cluster_id, pool, X_raw, gene_to_idx, EXCLUDE_PREFIX,
               EXCLUDE_PATTERN):
    cm = (adata.obs['leiden'] == cluster_id).values
    other = ~cm
    # Tier 1: strong specificity
    candidates = []
    for g in pool:
        if g not in gene_to_idx or any(g.startswith(p) for p in EXCLUDE_PREFIX):
            continue
        if EXCLUDE_PATTERN.search(g):
            continue
        target_mean = X_raw[cm, gene_to_idx[g]].mean()
        other_mean = X_raw[other, gene_to_idx[g]].mean()
        target_pct = (X_raw[cm, gene_to_idx[g]] > 0).mean()
        ratio = (target_mean + 0.1) / (other_mean + 0.1)
        if target_pct > 0.3 and ratio > 2.0:
            candidates.append((g, target_pct, ratio, target_mean))
    candidates.sort(key=lambda x: -x[2])
    seen = set(); top10 = []
    for c in candidates:
        if c[0] in seen: continue
        seen.add(c[0]); top10.append(c[0])
        if len(top10) >= 10: break
    # Tier 2: relax to ratio > 1.0 (acceptable for related-but-distinct types)
    if len(top10) < 10:
        for g in pool:
            if g in seen or g not in gene_to_idx: continue
            target_mean = X_raw[cm, gene_to_idx[g]].mean()
            other_mean = X_raw[other, gene_to_idx[g]].mean()
            target_pct = (X_raw[cm, gene_to_idx[g]] > 0).mean()
            ratio = (target_mean + 0.1) / (other_mean + 0.1)
            if target_pct > 0.1 and ratio > 1.0:
                top10.append(g); seen.add(g)
                if len(top10) >= 10: break
    # Tier 3: in-cluster pct > 20%, drop specificity (lineage-shared marker fallback)
    if len(top10) < 10:
        for g in pool:
            if g in seen or g not in gene_to_idx: continue
            target_pct = (X_raw[cm, gene_to_idx[g]] > 0).mean()
            if target_pct > 0.2:
                top10.append(g); seen.add(g)
                if len(top10) >= 10: break
    return top10
```

Tier 1 catches truly specific markers; tier 2 catches marker rows where
related panels overlap (e.g. luminal and glandular epithelium share KRT/EPCAM);
tier 3 catches pan-lineage markers that the user will still see on the PNG.

## Exclude-list (canonical scTE/MT/repeat noise)

```python
EXCLUDE_PREFIX = ('MT-', 'MT.', 'RPS', 'RPL', 'HSP', 'IGKC', 'IGLC',
                  'IGHG', 'IGHA', 'IGHM', '5S_rRNA', '5_8S_rRNA',
                  'LSU_rRNA', 'SSU_rRNA')
EXCLUDE_PATTERN = re.compile(
    r'(LTR|ERV|HARLEQUIN|HERVE|MER|MST|MLT|THE|ORR|INT|RTL|MMERVK|RLTR|'
    r'Alu|HERV|HERVK|SINE|LINE|-int|_int|retrotransposon|transposon)',
    re.IGNORECASE)
```

## Verification (proves the redraw is correct)

After redrawing, every PNG subplot title should map to one row in the
marker TSV. User audits by checking the PNG visually against the table.
**Mismatch is a bug**, not a content preference.

```python
# Self-check: PNG titles (from raw counts file or plot_data) == TSV markers
# Equivalent: annotations[cid]['key_markers'] is exactly what plot_markers
# drew into the PNG. Both come from the same source dict in this script.
```

## Use adata.raw for gene presence (do NOT use adata.var)

Critical: `plot_markers` reads expression from `adata.raw`, not from
`adata.X` (which is the HVG subset). When building the marker pool
filter, check `adata.raw.var_names`:

```python
# wrong — only checks HVG subset (3000 genes)
if gene in adata.var_names: ...

# right — full count matrix (~19k genes)
if gene in adata.raw.var_names: ...
```

This is the difference between "PAEP/ENPP3/SLPI are not in this dataset"
(false) and "PAEP/ENPP3/SLPI are in raw at pct 60% in C15 glandular".

## Worked example: Uterus Epithelial_glandular (C15)

Cell type from h5ad: `Epithelial_glandular` (n=1816, leiden='15').

**DEG top-10 (mode_auto output)**: `LSU_rRNA_eukarya, SSU_rRNA_eukarya,
Harlequin-int, WFDC2, 5_8S_rRNA, MT-ND2, HERVE_a-int, ENPP3, GSTA4, CLU`.
7/10 are scTE/repeat/MT noise. User-visible failure: PNG shows rRNA
expression on UMAP, not glandular identity.

**Canonical panel (HECA / Wang 2020)**: `EPCAM, KRT8, KRT18, KRT19,
WFDC2, SLPI, SPINT2, AGR2, PAEP, BPIFB1, BPIFA1, ENPP3, CXCL8, CLU,
MUC5B, SCGB2A1, SCGB2A2, CXCL1, CXCL3, CXCL5, GCDFP15, PIP, LTF, LYZ,
DPP4, MME, GPX2, MT1G, MT1X`.

**After tiered specificity filter** (using raw, including MUC5B, PAEP,
etc. all present): `WFDC2, EPCAM, KRT18, KRT19, SLPI, AGR2, ENPP3, CLU,
LYZ, SPINT2`. 10 markers, all visible on C15 in PNG.

**Verified** (Uterus_scTE, 2026-09-20): every PNG subplot title in
`Epithelial_glandular.png` matches a row in the marker file.

## Use case: h5ad replaced mid-session, reports stale

If `annotation_report.tsv` and `auto.h5ad` disagree on cluster count or
cell_type mapping, **the h5ad wins**. Delete stale sidecars
(`annotation_report.tsv`, `audit_report.json`, `decision_log.md`,
`references.tsv`) to avoid misleading downstream reviewers. The
override+redraw script then sources everything from the h5ad directly.

```bash
rm -rf <tissue>_scTE_auto_reports/
```

Confirmed 2026-09-20 (Uterus_scTE): TSV had 22 clusters (0-21) but h5ad
had 19 (0-18) after user replaced the h5ad. After deletion, the override
script read cluster count and cell_type directly from the h5ad.