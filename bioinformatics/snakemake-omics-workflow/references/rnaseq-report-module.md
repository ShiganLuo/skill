# RNAseq report module (session note)

Use this when adding an RNAseq PPT report to Omics Snakemake, or extending an existing report with new analysis sections.

Key shape:
- `modules/RNAseq_report/RNAseq_report.smk`
- `modules/RNAseq_report/RNAseq_report.json`
- `modules/RNAseq_report/RNAseq_report.yaml`
- `modules/RNAseq_report/bin/generate_report.py`

Subworkflow wiring:
- `subworkflow/RNAseq.smk` builds `RNAseq_report_config`
- `use rule generate_report from RNAseq_report as RNAseq_generate_report`
- final target: `outdir + "/RNAseq_report.pptx"`

Report script notes:
- `python-pptx` for slides, `matplotlib` for charts, `PIL` for aspect-ratio-safe image sizing
- generate from existing workflow outputs; do not recompute upstream analysis
- accept `--analysis-dir`, `--output`, `--samples`, `--paired-samples`, `--single-samples`, `--contrasts`, `--lang`, `--img-dir`

## Architecture of generate_report.py

The script follows a consistent 5-layer pattern:
1. **I18N dict** (zh/en) with `t(key, lang)` helper — all user-facing strings
2. **Data loaders** — one function per analysis type, returns DataFrame/dict with safe fallbacks for missing files (`safe_read_tsv`, `safe_read_csv`)
3. **Plot functions** — matplotlib figures saved as temp PNG via `TempImageStore.save_fig()`
4. **Slide builders** — each takes `prs: Presentation` + data + `lang`, uses `_header()`, `_textbox()`, `_bullets()`, `_table()`, `_add_picture()` helpers
5. **main()** — argparse CLI, auto-discovers contrast dirs, conditionally builds slides based on file existence

Layout constants (module-level):
```python
SLIDE_W = 10.0; SLIDE_H = 5.625  # 16:9
HEADER_H = 0.65; MARGIN_L = 0.45; MARGIN_R = 0.45
CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R
CONTENT_TOP = HEADER_H + 0.18
```

## Extending the report with new analysis sections (function/GO/KEGG/GSEA pattern)

When adding a new downstream analysis (e.g. function enrichment) to the existing report, touch these layers in order:

1. **i18n keys** (zh + en) — add all user-facing strings for the new section (slide titles, column headers, notes).
2. **Data loaders** — one function per analysis type, returns dict/DataFrame with safe fallbacks for missing files. Use `safe_read_csv()` (pd.read_csv) for CSV outputs from R scripts (not read_csv with sep="\t"). Use `_count_lines()` for plain-text gene lists (up_genes.txt etc).
3. **Slide builders** — typically 3 types per new analysis:
   - Summary slide (one row per contrast, counts only)
   - Per-contrast detail slides (images + top-N tables)
   - Conclusion bullet additions (stats summary)
4. **main()** — auto-discover contrast subdirs under `{analysis_dir}/{analysis_name}/`, load summaries, conditionally build slides based on file existence.
5. **.smk inputs** — add all new output files as named inputs in `expand()` so Snakemake tracks dependencies.
6. **collect_conclusion_bullets** — extend signature to accept the new summaries list and append stats bullets.

### Function module output file inventory

Per-contrast directory `{analysis_dir}/function/{contrast}/`:
- `go_back_to_back.png`, `kegg_back_to_back.png` — back-to-back bar plots
- `go_up.csv`, `go_down.csv`, `kegg_up.csv`, `kegg_down.csv` — enrichment result tables (columns: Description, Count, pvalue, p.adjust, geneID, ...)
- `up_genes.txt`, `down_genes.txt` — one gene symbol per line
- `GSEA/TEcount_Gene_GSEA.jpeg` — waterfall NES plot
- `GSEA/TEcount_Gene_GSEA.csv` — fgsea result (columns: pathway, pval, padj, NES, ES, size, leadingEdge)
- `GSEA/enrichment_plots/*.jpeg` — per-pathway gseapy-style plots (optional, not in report)

### load_function_summary() pattern

Returns a dict with paths + loaded DataFrames + pre-computed counts:
```python
result = {
    "contrast": name,
    "go_plot": ..., "kegg_plot": ..., "gsea_plot": ...,
    "go_up_df": df, "go_up_n": len(df),
    "up_count": _count_lines(up_genes_path),
    "down_count": _count_lines(down_genes_path),
    "gsea_df": df, "gsea_n": len(df),
}
```

### Table overflow when adding picture+table slides

When a slide has pictures at top and tables at bottom, the initial layout often overflows the 5.625" slide height. Pattern to avoid:
- Pictures: max height 2.5" (not 3.0") when tables follow below
- Tables: start at y=3.55" (not 4.05"), use row height 0.22" per row (not 0.30")
- Limit table rows: top_n=2 for up + separator row + top_n=2 for down = 5 rows max per table
- Always verify with programmatic overflow check (shape bottom > slide_h)

### GSEA table: top positive + top negative pathways

The GSEA detail slide shows top pathways by NES (both positive and negative):
```python
sig = gsea_df.dropna(subset=["NES"]).sort_values("NES", ascending=False)
top_positive = sig.head(4)
top_negative = sig.sort_values("NES", ascending=True).head(4)
combined = pd.concat([top_positive, top_negative]).drop_duplicates(subset=["pathway"])
```

### .smk input additions for function

```python
func_go_plot = expand(outdir + "/function/{contrast}/go_back_to_back.png", contrast=contrasts),
func_kegg_plot = expand(outdir + "/function/{contrast}/kegg_back_to_back.png", contrast=contrasts),
func_go_up = expand(outdir + "/function/{contrast}/go_up.csv", contrast=contrasts),
func_go_down = expand(outdir + "/function/{contrast}/go_down.csv", contrast=contrasts),
func_kegg_up = expand(outdir + "/function/{contrast}/kegg_up.csv", contrast=contrasts),
func_kegg_down = expand(outdir + "/function/{contrast}/kegg_down.csv", contrast=contrasts),
func_up_genes = expand(outdir + "/function/{contrast}/up_genes.txt", contrast=contrasts),
func_down_genes = expand(outdir + "/function/{contrast}/down_genes.txt", contrast=contrasts),
func_gsea_plot = expand(outdir + "/function/{contrast}/GSEA/TEcount_Gene_GSEA.jpeg", contrast=contrasts),
func_gsea_csv = expand(outdir + "/function/{contrast}/GSEA/TEcount_Gene_GSEA.csv", contrast=contrasts),
```

## Ad-hoc verification recipe

1. `python -m py_compile modules/RNAseq_report/bin/generate_report.py`
2. Run the script against existing `output/RNAseq`
3. Confirm `Presentation(...).slides` count is expected
4. Programmatic overflow check: iterate all shapes on all slides, verify `shape.left + width <= slide_w` and `shape.top + height <= slide_h` (with ~0.01" tolerance)
5. Extract table cell text to verify data correctness (counts, pathway names, p-values)
6. Test both zh and en languages
7. For visual QA, convert PPTX -> PDF via `libreoffice --headless --convert-to pdf`, then rasterize with `pdftoppm -png -r 150` and inspect

## Venn diagrams + Excel file inventory (XLSX)

### Two outputs from generate_report

1. **PPTX** (`--output`): now also includes Venn diagram slides when >= 2 contrasts.
2. **XLSX** (`--file-inventory`): Excel workbook with:
   - `Overview` sheet: analysis metadata
   - `InputFiles` sheet: all input file paths with existence check
   - One sheet per Venn intersection (e.g. `Venn_gene_up`): feature IDs shared across all contrasts

### Venn diagram via venn.py

Uses `src/common/plot/Python/venn.py` (imported via sys.path, see `references/run-block-script-extraction.md`).

- 2-6 contrasts: `venn_lib.get_labels(sets, fill=["number"])` + `venn_lib.vennN(labels_dict, names=labels)`
- 7+ contrasts: UpSet-style bar chart fallback (pairwise intersection sizes)
- Titles: English by default ("Gene Up", "Gene Down", "TE Up", "TE Down")
- `build_venn_slides()` returns `Dict[str, List[str]]` mapping sheet_name -> sorted shared feature IDs (gene symbols)

### Gene source: .name.tsv (gene symbols), NOT updown.tsv (Ensembl IDs)

Gene/TE sets for Venn diagrams come from `TEcount_Gene.name.tsv` and `TEcount_TE.name.tsv` (NOT `TEcount_*_updown.tsv`). The `.name.tsv` files use gene symbols (first column `gene_name`) instead of Ensembl IDs, and do NOT have a `sig` column. Filter by significance using the SAME thresholds as `DESeq2.r ScreenFeature` (default `lfc_cut=0.58`, `padj_cut=0.05`):

```python
lfc = pd.to_numeric(df["log2FoldChange"], errors="coerce")
padj = pd.to_numeric(df["padj"], errors="coerce")
sig = (padj < 0.05) & (lfc.abs() >= 0.58)
result["up"] = set(df.loc[sig & (lfc > 0), name_col].astype(str))
result["down"] = set(df.loc[sig & (lfc < 0), name_col].astype(str))
```

**Critical**: `padj < 0.05` (strict less-than, matching R's `<`), NOT `<=`. `lfc_cut=0.58` (not 1.0). Verified against real data: row-level counts match updown.tsv exactly (up=1825/1825, down=830/830). Set-level counts may differ by a few due to gene_name dedup (multiple Ensembl IDs mapping to same symbol).

Some genes may lack symbol mapping and retain ENSMUSG IDs in `.name.tsv` - this is expected.

### .smk additions for .name.tsv inputs

```python
contrast_gene_name = expand(outdir + "/diff_expression/{contrast}/TEcount_Gene.name.tsv", contrast=contrasts),
contrast_te_name = expand(outdir + "/diff_expression/{contrast}/TEcount_TE.name.tsv", contrast=contrasts),
```

### Excel writes actual result DATA, not file paths

`write_file_inventory()` writes the full contents of result TSV/CSV files into Excel sheets. Each result file becomes a sheet with its data. It does NOT write file path inventories.

- `_write_tsv_sheet(sheet_name, tsv_path)`: reads TSV via pandas, writes header + all rows to a new sheet
- `_write_csv_sheet(sheet_name, csv_path)`: same for CSV files
- `_write_text_sheet(sheet_name, txt_path)`: one-column sheet for gene list txt files
- `_safe_sheet_name(name)`: truncate to 31 chars, replace `:\\/?*[]` with `_`
- `_MAX_ROWS = 5000`: cap per sheet to prevent Excel/memory issues
- Large files (>10MB, e.g. TEcount matrix) are skipped
- Venn intersection sheets use `Feature_Name` column header (gene symbols, not IDs)
- No `InputFiles` sheet (old path-based approach removed)

### .smk output additions

```python
output:
    report = outdir + "/RNAseq_report.pptx",
    file_inventory = outdir + "/RNAseq_report_files.xlsx",
```
CMD includes `--file-inventory str(output.file_inventory)`.

### Python 3.9 + typing module

All annotations use `typing` (Dict, List, Optional, Set). No PEP 604 `X | None` syntax.

### openpyxl in yaml

```yaml
  - openpyxl>=3.1.0
```

### Excel sheet naming: avoid Recovered_Sheet and >31 char warnings

**Pitfall**: When multiple contrasts generate similarly-named sheets (e.g. `Scramble_vs_Rn7sk_sh1_TEcount_Gene_name`), truncating to 31 chars produces identical names. openpyxl auto-appends `1`, `2` suffixes (generating `UserWarning: Title is more than 31 characters`) and in extreme collisions creates `Recovered_Sheet1` etc., making sheets indistinguishable.

**Fix**: Two-layer approach:

1. `_contrast_tag(contrast)`: shorten contrast name by removing `_vs_` and capping at 20 chars (`"Scramble_vs_Rn7sk_sh1"` -> `"Scramble_Rn7sk_sh1"`).
2. Use short explicit tags instead of deriving from filenames (`"Gene_name"` not `"TEcount_Gene_name"`).
3. `_unique_sheet_name(name)`: before calling `wb.create_sheet()`, check against a `_used_names` set. If the name (after 31-char truncation and illegal-char replacement) already exists, append a numeric suffix with room reserved: `base[:31-len(suffix)] + suffix`. This prevents openpyxl from ever auto-renaming.

```python
_used_names: set = set()

def _unique_sheet_name(name: str) -> str:
    base = _safe_sheet_name(name)  # truncate to 31, replace illegal chars
    if base not in _used_names:
        _used_names.add(base)
        return base
    for i in range(1, 100):
        suffix = str(i)
        candidate = base[: 31 - len(suffix)] + suffix
        if candidate not in _used_names:
            _used_names.add(candidate)
            return candidate
    return base
```

All `_write_tsv_sheet`, `_write_csv_sheet`, `_write_text_sheet` calls must use `_unique_sheet_name()` instead of `_safe_sheet_name()` directly. Verify with `warnings.catch_warnings(record=True)` in tests - zero warnings means no openpyxl auto-rename happened.

## Layout lessons

- slide 5/table areas can become cramped when many sample labels and numeric columns share a narrow table
- slide 8 note text should not sit under or beside the table body; remove or move it if overlap appears
- when adding new sections, always run the overflow check - the 5.625" height is tight for picture+table slides

## Pitfall: contrast-prefixed output filenames

DESeq2 outputs in `diff_expression/{contrast}/` use a `{contrast}.` prefix on filenames:
- `Scramble_vs_Rn7sk_sh1.TEcount_Gene.name.tsv` (NOT `TEcount_Gene.name.tsv`)
- `Scramble_vs_Rn7sk_sh1.cpmPCA.png` (NOT `cpmPCA.png`)
- `Scramble_vs_Rn7sk_sh1.TEcount_Gene_volcano.png` (NOT `TEcount_Gene_volcano.png`)
- `Scramble_vs_Rn7sk_sh1.TEcount_Gene_updown.png` (NOT `TEcount_Gene_updown.png`)
- Same for upDown/*.tsv, volcano/*.png, heatmap/*.png

**Symptom**: PPT slides have 0 pictures (PCA, volcano, heatmap all missing), Venn diagrams have empty gene sets, but no error is raised because `_add_picture` silently skips non-existent files.

**Fix**: In `load_diff_summary()`, build all per-contrast paths with `prefix = "{}.".format(name)`:
```python
prefix = "{}.".format(name)
"pca": os.path.join(contrast_dir, "PCA", "{}cpmPCA.png".format(prefix)),
"gene_volcano": os.path.join(contrast_dir, "volcano", "{}TEcount_Gene_volcano.png".format(prefix)),
```

**Note**: Function module outputs (`function/{contrast}/`) do NOT use this prefix - their filenames are plain (`go_up.csv`, `go_back_to_back.png`, etc.).

## Pitfall: venn.py global matplotlib figure state

`venn.py` uses `plt.figure(0, ...)` with a fixed figure number 0 internally. When called multiple times in sequence (e.g. 4 Venn diagrams for gene_up, gene_down, te_up, te_down), the global figure state leaks between calls and can corrupt subsequent matplotlib figures.

**Fix**: Wrap every venn.py call with `plt.close("all")` before and after:
```python
plt.close("all")
fig, _ax = venn_func(labels_dict, names=labels, figsize=(8, 7), dpi=150)
path = img_store.save_fig(fig, stem)
plt.close("all")
return path
```

## Excel sheet naming: use smk input names, contrast in row 1

User preference: sheet names should match the smk `input:` named parameters exactly (e.g. `te_sample_summary`, `contrast_gene_name`, `func_go_up`). Do NOT concatenate contrast names into sheet names.

For per-contrast sheets sharing the same smk input name:
1. First contrast uses the name as-is (e.g. `contrast_gene_name`)
2. Subsequent ones auto-numbered: `contrast_gene_name1`, `contrast_gene_name2`
3. Contrast name written as row 1, header as row 2, data from row 3

Non-contrast sheets (e.g. `te_sample_summary`, `fusion_summary`) have no contrast row - header is row 1.

### Implementation

```python
_used_names: set = set()

def _unique_sheet_name(name: str) -> str:
    """Ensure sheet name is unique and <= 31 chars, auto-number on conflict."""
    base = _safe_sheet_name(name)  # truncate to 31, replace illegal chars
    if base not in _used_names:
        _used_names.add(base)
        return base
    for i in range(1, 100):
        suffix = str(i)
        candidate = base[: 31 - len(suffix)] + suffix
        if candidate not in _used_names:
            _used_names.add(candidate)
            return candidate
    return base
```

All `_write_tsv_sheet`, `_write_csv_sheet`, `_write_text_sheet` accept an optional `contrast: str = ""` parameter. When non-empty, the contrast name is written as the first row before the data header. This replaces the old `_contrast_tag()` approach which concatenated shortened contrast names into sheet names (causing collisions and `Recovered_Sheet` issues).

### Excel writes actual result DATA, not file paths

`write_file_inventory()` writes the full contents of result TSV/CSV files into Excel sheets. Each result file becomes a sheet with its data. It does NOT write file path inventories.

- `_write_tsv_sheet(sheet_name, tsv_path, contrast="")`: reads TSV via pandas, writes contrast (optional) + header + all rows
- `_write_csv_sheet(sheet_name, csv_path, contrast="")`: same for CSV files
- `_write_text_sheet(sheet_name, txt_path, contrast="")`: one-column sheet for gene list txt files
- `_safe_sheet_name(name)`: truncate to 31 chars, replace `:\\/?*[]` with `_`
- `_MAX_ROWS = 5000`: cap per sheet to prevent Excel/memory issues
- Large files (>10MB, e.g. TEcount matrix) are skipped
- Venn intersection sheets use `Feature_Name` column header (gene symbols, not IDs)
- No `InputFiles` sheet (old path-based approach removed)

### File path convention for per-contrast DE results

DESeq2 outputs use `{contrast}.` prefix on filenames:
- `Scramble_vs_Rn7sk_sh1.TEcount_Gene.name.tsv` (NOT `TEcount_Gene.name.tsv`)
- `Scramble_vs_Rn7sk_sh1.cpmPCA.png` (NOT `cpmPCA.png`)
- Same for volcano/, heatmap/, upDown/ subdirectories

Function module outputs (`function/{contrast}/`) do NOT use this prefix.
