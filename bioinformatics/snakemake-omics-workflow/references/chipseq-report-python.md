# ChIP-seq Report Module (Python-based)

Python-based report generator using `python-pptx` + `matplotlib`. Preferred over PptxGenJS when the workflow already uses Python/conda.

## Module Structure

```
modules/PeakCalling_report/
├── report.smk          # Snakemake rules
├── report.yaml         # Conda env (python-pptx, matplotlib, openpyxl, numpy, pillow)
└── bin/
    └── generate_report.py  # Main script with data loading + plotting + PPT generation
```

## report.yaml

```yaml
name: report
channels:
  - conda-forge
  - defaults
dependencies:
  - python>=3.9
  - python-pptx>=0.6.21
  - matplotlib>=3.5.0
  - openpyxl>=3.0.0
  - numpy>=1.21.0
  - pillow>=9.0.0
```

`pillow` is required for `_add_picture()` aspect ratio calculation.

## report.smk Pattern

The rule collects inputs from all upstream steps (peaks, FRiP, annotation, bowtie2 logs, markdup metrics) and runs the Python script:

```python
include: "../common/common.smk"
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
samples = config.get("samples", [])
input_samples = config.get("input_samples", [])

# Locate script relative to this snakefile (NOT workflow.modules["name"])
REPORT_SCRIPT = os.path.join(os.path.dirname(workflow.snakefile), "bin", "generate_report.py")

rule generate_report:
    input:
        peaks = expand(outdir + "/peaks/{sample}/{sample}_peaks.narrowPeak", sample=samples),
        frip = expand(outdir + "/QC/3_frip_score/{sample}/{sample}.FRiP.txt", sample=samples),
        annotations = expand(outdir + "/annotation/{sample}/{sample}_peaks.annotatePeaks.txt", sample=samples),
        bowtie2_logs = expand(outdir + "/log/{sample}/bowtie2_align.log", sample=samples + input_samples),
        markdup_metrics = expand(outdir + "/common/4_markdup_bam/{sample}/{sample}.Markdup-metrics.txt", sample=samples + input_samples),
    output:
        report = outdir + "/PeakCalling_report.pptx"
    log:
        logdir + "/report.log"
    threads: 1
    conda:
        "report.yaml"
    params:
        samples = " ".join(samples),
        input_samples = " ".join(input_samples),
        peaks_dir = outdir + "/peaks",
        annotation_dir = outdir + "/annotation",
        qc_dir = outdir + "/QC/3_frip_score",
        log_dir = outdir + "/log",
        markdup_dir = outdir + "/common/4_markdup_bam",
        title = config.get("Params", {}).get("report", {}).get("title") or "",
        subtitle = config.get("Params", {}).get("report", {}).get("subtitle") or "",
        pipeline = config.get("Params", {}).get("report", {}).get("pipeline") or "",
        genome = config.get("Params", {}).get("report", {}).get("genome") or "",
        date = config.get("Params", {}).get("report", {}).get("date") or "",
        top_n = config.get("Params", {}).get("report", {}).get("top_n") or 5,
        lang = config.get("Params", {}).get("report", {}).get("lang") or "zh",
        script = REPORT_SCRIPT,
    shell:
        """
        python3 {params.script} \
            --samples {params.samples} \
            --input-samples {params.input_samples} \
            --peaks-dir {params.peaks_dir} \
            --annotation-dir {params.annotation_dir} \
            --qc-dir {params.qc_dir} \
            --log-dir {params.log_dir} \
            --markdup-dir {params.markdup_dir} \
            --output {output.report} \
            --title "{params.title}" \
            --subtitle "{params.subtitle}" \
            --pipeline "{params.pipeline}" \
            --genome "{params.genome}" \
            --date "{params.date}" \
            --top-n {params.top_n} \
            --lang {params.lang} \
            > {log} 2>&1
        """
```

**IMPORTANT:** Use `shell:` NOT `run:` when `conda:` is present (pitfall #19). Use `os.path.dirname(workflow.snakefile)` for script path — `workflow.modules["name"].snakefile` is unreliable when imported as a use-rule.

## Subworkflow Integration

Add as the LAST step in the subworkflow (after all QC/annotation steps):

```python
report_config = {
    "outdir": outdir,
    "logdir": logdir,
    "samples": ip_samples,
    "input_samples": input_samples,
    "Params": {
        "report": config.get("Params", {}).get("report", {})
    }
}
module report:
    snakefile: "../modules/PeakCalling_report/report.smk"
    config: report_config
use rule generate_report from report as PeakCalling_generate_report
```

## Config JSON Template

Add a `"report"` key under `"Params"` in the workflow config JSON:

```json
{
    "Params": {
        "report": {
            "title": "ChIP-seq Peak Calling Report",
            "subtitle": "Pop5 & Rpp14 & Rpp21 IP/Input — Mouse GRCm39 (mm39)",
            "pipeline": "TrimGalore → Bowtie2 → GATK MarkDuplicates → MACS3 → HOMER → bamCoverage → FRiP",
            "genome": "GRCm39 (mm39)",
            "date": "2026-07-14",
            "top_n": 5,
            "lang": "zh"
        }
    }
}
```

All fields are optional with sensible defaults. `subtitle` auto-generates from sample names + genome if omitted. `lang` defaults to `"zh"` (Chinese PPT text, English chart titles).

## generate_report.py Architecture

The script has 3 layers, all parameterized (no hardcoded sample names):

### 1. i18n (Internationalization)

Define an `I18N` dict with all user-facing strings keyed by language code. A `t(key, lang)` helper returns the translated string. All slide builders accept `lang` parameter.

```python
I18N = {
    "zh": {
        "report_title": "ChIP-seq Peak Calling 分析报告",
        "workflow_title": "分析流程概览",
        "alignment_title": "Bowtie2 比对统计",
        "summary_title": "总结与 QC 评估",
        "conclusions": "结论",
        # ... all strings
    },
    "en": {
        "report_title": "ChIP-seq Peak Calling Report",
        "workflow_title": "Workflow Overview",
        # ...
    },
}
def t(key, lang="zh"):
    return I18N.get(lang, I18N["zh"]).get(key, key)
```

**Chart titles are ALWAYS in English** (matplotlib CJK font issue). PPT text follows `--lang`.

### 2. Data Loading Functions

Parse logs/metrics files, each returns None/default on missing file:

- `load_bowtie2(log_dir, sample)` → `float|None` (alignment rate %)
- `load_markdup(metrics_dir, sample)` → `dict|None` (read_pairs, dup_rate, etc.)
- `load_macs3_params(log_dir, sample)` → `dict|None` (pvalue, bw, genome_size, fragment_length)
- `load_frip(qc_dir, sample)` → `float|None` (FRiP fraction)
- `load_peak_count(peaks_dir, sample)` → `int` (0 if missing)
- `load_cutoff(peaks_dir, sample)` → `dict|None` (pscore, npeaks lists)
- `load_annotation(annotation_dir, sample)` → `dict|None` (category→count)
- `load_top_genes(annotation_dir, sample, n=5)` → `list[(gene, pos, score)]`

### 3. Plotting Functions

All use **DPI 300** (publication quality), **English labels only**, each returns temp PNG path via `_save(fig)`:

- `plot_alignment(rates: {sample: float})` → path — bar chart with QC threshold line
- `plot_peak_and_frip(samples, peaks, frips)` → path — dual bar chart
- `plot_cutoff(cutoff_data)` → path — log + linear dual plot with threshold line
- `plot_annotation(ann_data, lang)` → path — pie charts with translated category labels
- `plot_tss_distance(annotation_dir, samples)` → path — histogram with 1kb/5kb markers

**DPI constant:** Set `DPI = 300` at module level. The `_save()` helper uses it:
```python
def _save(fig):
    tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="rpt_", delete=False)
    fig.savefig(tmp.name, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return tmp.name
```

### 4. PPT Layout Constants

Prevent element overlap with module-level constants:
```python
SLIDE_W = 10.0      # inches
SLIDE_H = 5.625     # 16:9 aspect ratio
MARGIN_L = 0.5
MARGIN_R = 0.5
CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R  # 9.0
HEADER_H = 0.7
CONTENT_TOP = HEADER_H + 0.2               # 0.9
CONTENT_MAX_H = SLIDE_H - CONTENT_TOP - 0.3  # bottom margin
```

All slide builders use these constants — never hardcoded pixel positions.

### 5. Aspect-Ratio-Preserving Image Insertion

**CRITICAL:** `add_picture(path, left, top, width, height)` with BOTH width and height **distorts images**. Use this helper instead:

```python
def _add_picture(slide, img_path, left, top, max_width, max_height):
    """Add picture preserving aspect ratio within bounds."""
    from PIL import Image as PILImage
    img = PILImage.open(img_path)
    img_w, img_h = img.size
    aspect = img_w / img_h
    w = max_width
    h = w / aspect
    if h > max_height:
        h = max_height
        w = h * aspect
    left_emu = left + (max_width - w) / 2  # center horizontally
    slide.shapes.add_picture(img_path, Inches(left_emu), Inches(top), Inches(w), Inches(h))
```

All image slides use `_add_picture(slide, img, MARGIN_L, CONTENT_TOP, CONTENT_W, CONTENT_MAX_H)`.

### 6. PPT Slide Builders

Fully decoupled, each takes only what it needs:

- `slide_title(prs, title, subtitle, date, pipeline, lang)` — dark background title
- `slide_workflow(prs, samples, input_samples, lang)` — flow diagram + sample table
- `slide_alignment(prs, alignment_data, img_path, lang)` — image + warning at bottom
- `slide_markdup(prs, markdup_data, all_samples, lang)` — table + notes
- `slide_peak_calling(prs, pf_img, lang)` — dual chart image
- `slide_cutoff(prs, cutoff_img, lang)` — image + note at bottom
- `slide_annotation(prs, ann_img, ann_data, lang)` — pie charts
- `slide_tss(prs, tss_img, lang)` — TSS distance histogram
- `slide_top_genes(prs, genes_data, lang)` — dual-column gene tables
- `slide_summary(prs, samples, aligns, markdups, peaks, frips, anns, lang)` — QC table + detailed per-sample analysis + recommendations

### 7. Detailed Summary Slide

The summary slide should contain:
1. **QC metrics table** (alignment rate, dup rate, peak count, FRiP)
2. **Per-sample analysis** with:
   - All metrics on one line: `Peak 数: 410 | 比对率: 52.9% | 重复率: 25.5% | FRiP: 24.00%`
   - Annotation summary: `注释: 启动子 9.4% | 基因间区 42.2% | 总注释 415`
   - Color-coded status: green (good), yellow (warning), red (critical)
3. **Specific recommendations** tied to actual issues found:
   - `FRiP 偏低: 建议优化 ChIP 抗体或增加测序深度`
   - `比对率偏低: 检查样本质量、接头污染或参考基因组`
   - `重复率偏高: 考虑增加起始量或优化文库构建`

## Pitfalls

1. **Matplotlib CJK fonts** — DejaVu Sans renders Chinese/Japanese as boxes. Use English labels for all matplotlib plot titles/axis labels. PPT text (python-pptx) renders correctly with CJK because it uses system fonts at display time.

2. **Examine existing outputs before creating new reports** — User will correct you if you create a PPT without first reading the existing one. Always `read_file` or `python-pptx` the existing report to understand its structure, then match or improve it.

3. **Save plotting scripts as reusable modules** — User explicitly requires all plotting scripts to be saved in the module's `bin/` directory, not as throwaway /tmp scripts. The report module must be a proper 3-file module (.smk + .yaml + bin/).

4. **Cleanup temp plot files** — Use `tempfile.mkdtemp()` for intermediate matplotlib outputs, then `shutil.rmtree()` after PPT is saved. Don't leave temp PNGs in the output directory.

5. **HOMER annotation column indices** — Gene Name is at column 16 (index 15), NOT column 10. Column 10 is "Distance to TSS". Always check the header row first.

6. **List params in shell: rules** — When using `shell:` (not `run:`), list-type params must be converted to space-joined strings: `params: samples = " ".join(samples)`. The `run:` block can handle raw Python lists, but `shell:` interpolates them as `[` `'a',` `'b'` `]` literal text.

7. **Standalone snakemake testing** — `common.smk` requires `ROOT_DIR` in config for importing `src.common.*`. When testing a module in isolation, pass `--configfile` with `"ROOT_DIR": "<project>/workflow/Omics"`. Without this, you get `ImportError: No module named 'common'`.

8. **Generic design — parameterize everything** — The report script should have NO hardcoded sample names, species, or thresholds. All content flows from CLI args (`--title`, `--subtitle`, `--pipeline`, `--genome`, `--date`, `--top-n`, `--lang`). QC thresholds (alignment rate 80%, FRiP 20%) should be module-level constants, not buried in slide logic.

9. **Data loaders must be resilient** — Every `load_*` function should return `None` or a sensible default when the input file is missing. The script should skip slides for missing data (e.g., no cutoff_analysis → skip cutoff slide). Never crash on a missing optional file.

10. **Scalar vs dict in summary tables** — When `slide_summary` receives alignment rates as `{sample: float}` (passed from `main`) but `_v()` helper expects `dict`, you get `AttributeError: 'float' object has no attribute 'get'`. Fix: make `_v()` handle both scalars and dicts:
    ```python
    def _v(d, k=None, fmt=".1f", unit="%", fallback="N/A"):
        if d is None: return fallback
        if k is None or isinstance(d, (int, float)): v = d
        else: v = d.get(k) if isinstance(d, dict) else None
        return f"{v:{fmt}}{unit}" if v is not None else fallback
    ```

11. **Output naming convention** — Use `PeakCalling_report.pptx` (lowercase `report`), not `PeakCalling_Report.pptx`. The output filename should match the module name pattern: `<WorkflowName>_<module>.<ext>`.

12. **Module directory renaming** — When the user says "rename the module", they mean the **directory name** under `modules/`, NOT the output file name. After renaming `modules/report/` → `modules/PeakCalling_report/`, you must:
    - Update the `snakefile:` path in the subworkflow's `module <name>:` block
    - Copy or symlink the `.yaml` file if the `conda:` directive references the old name
    - Update any `REPORT_SCRIPT` path references
    - The conda env `.yaml` filename inside the module directory can stay as-is (e.g. `report.yaml`) — only the directory changes

13. **Image distortion in PPT** — `add_picture()` with both width AND height specified stretches images to fit, destroying aspect ratio. Always use `_add_picture()` helper with PIL to calculate correct dimensions. The helper reads the image dimensions, computes aspect ratio, fits within max bounds, and centers horizontally.

14. **Element overlap in PPT** — Never hardcode pixel positions. Use layout constants (`SLIDE_W`, `SLIDE_H`, `MARGIN_L`, `CONTENT_TOP`, `CONTENT_MAX_H`) and calculate positions dynamically. For warnings/notes that appear below images, place them at `SLIDE_H - 0.4` (fixed bottom position) rather than `CONTENT_TOP + img_h` (which requires knowing the image height after aspect-ratio adjustment).

15. **DPI for publication figures** — Use `DPI = 300` for all matplotlib outputs. The default 100-150 DPI produces blurry figures when printed or zoomed. Set as a module-level constant and use in `_save()`.

16. **Full genomic coordinates** — When displaying positions in tables, use `chr:start-end` format (e.g. `chrX:105230252-105230912`). NEVER abbreviate to `chrX:105M` — users need exact coordinates for manual verification.

17. **--img-dir for plot image output** — Support `--img-dir` CLI parameter to save matplotlib images separately (for reuse in other reports or debugging). In Snakemake, pass `--img-dir {params.img_dir}` where `params.img_dir = outdir + "/ppt_results"`. Copy images after plotting, before cleanup.

18. **Layout class for overflow prevention** — Use a `Layout` class that tracks vertical position (`lay.allocate(h)` returns `(y, actual_h)` or `None` when full). Every multi-element slide builder creates `lay = Layout()` and calls `lay.allocate()` for each element. This permanently prevents overlap regardless of content size.

19. **TSS distance analysis** — Standard ChIP-seq report section: parse `annotatePeaks.txt` column 10 for distance to TSS, plot histogram with 1kb/5kb vertical lines. In the summary slide, include per-sample TSS stats: `{within_1kb} peaks 在 1kb 内 ({pct}%) | {within_5kb} peaks 在 5kb 内 ({pct}%)`.

20. **Gene coordinates in top genes table** — The `load_top_genes()` function should return 4-tuples: `(gene, chr:start-end, score, tss_dist)`. The `_` (tss_dist) is used in summary but not in the table itself. When unpacking in list comprehensions, use `for g, pos, s, _ in genes`.

21. **Every image slide needs data-driven conclusions** — Image slides should NOT just show a chart. Each must have a conclusion text area below the image with actual analysis results. Use `Layout` to reserve space (`img_h = lay.remaining - 1.0`), then add text after the image. Examples:
   - Alignment slide: "IP 样本平均比对率: 69.1%" + per-sample breakdown
   - Peak calling slide: "Rpp21IP 最多 (1,544 peaks), Pop5IP 最少 (410)"
   - Annotation slide: per-sample dominant category + percentage
   - TSS slide: per-sample "N peaks 在 1kb 内 (X%)" + biological interpretation

22. **Dual-column top genes layout** — Single-column wastes horizontal space and overflows with 3+ samples. Use dual-column: process samples in pairs, allocate header and table SEPARATELY (not as one combined row), then place both columns at the allocated position. The third sample (if odd) gets a full-width single column below. Shared genes text goes at the bottom via `lay.allocate()`.

    **IMPORTANT:** Do NOT use `row_h = 0.22 + 0.03 + max_tbl_rows * 0.23` to compute combined height — PowerPoint table cell padding makes rendered height differ from calculated, causing header↔table overlap. Allocate each element independently. See pitfall #29.

    ```python
    half_w = (CONTENT_W - 0.2) / 2
    col_x = [MARGIN_L, MARGIN_L + half_w + 0.2]
    sample_list = [(s, g) for s, g in genes_data.items() if g]
    pair_start = 0
    while pair_start < len(sample_list):
        pair = sample_list[pair_start:pair_start + 2]
        # Header — one allocate for the row
        hdr_alloc = lay.allocate(0.22)
        if hdr_alloc is None: break
        for ci, (sample, genes) in enumerate(pair):
            tx = slide.shapes.add_textbox(Inches(col_x[ci]), Inches(hdr_alloc[0]), ...)
        lay.gap(0.05)
        # Table — separate allocate
        max_rows = max(len(g) for _, g in pair) + 1
        tbl_h = min(max_rows * 0.22, lay.remaining - 0.4)
        tbl_alloc = lay.allocate(max(tbl_h, 0.4))
        if tbl_alloc is None: break
        for ci, (sample, genes) in enumerate(pair):
            _add_table(slide, tbl, Inches(col_x[ci]), Inches(tbl_alloc[0]), ...)
        lay.gap(0.15)
        pair_start += 2
    ```

23. **`allocate()` minimum height** — `allocate()` must enforce `min(h, 0.15)` to prevent zero or negative-height elements when remaining space is very small. Without this, the last element in a packed slide can get a negative height, causing it to render outside the slide bounds.

24. **NEVER bypass Layout for any element** — ALL elements on a multi-element slide MUST go through `lay.allocate()`. Do NOT use `if lay.remaining > X:` to check space then place directly — this bypasses Layout's Y tracking and can cause overlap with subsequent elements. The pattern `conc_alloc = lay.allocate(lay.remaining)` is correct; `if lay.remaining > 0.3: tx = slide.shapes.add_textbox(..., Inches(lay.y), ...)` is WRONG.

    Similarly, do NOT use `_bullet()` or `_note_list()` helper functions that accept raw `y` coordinates — they bypass Layout. Instead, always `lay.allocate()` first, then create the textbox at the returned position:
    ```python
    # WRONG — bypasses Layout
    if lay.remaining > 0.3:
        tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(lay.y), ...)
    
    # CORRECT — goes through Layout
    alloc = lay.allocate(lay.remaining)
    if alloc:
        tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(alloc[0]), Inches(CONTENT_W), Inches(alloc[1]))
    ```

25. **Text overflow inside textboxes** — A textbox shape can be within slide bounds, but the TEXT inside it overflows the box visually. python-pptx doesn't clip text; it renders beyond the box boundary. **Always estimate text height vs box height after building the PPT:**
    ```python
    for si, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_text_frame:
                box_h = shape.height / 914400
                total = 0
                for p in shape.text_frame.paragraphs:
                    text = p.text.strip()
                    if not text: continue
                    fs = p.font.size
                    font_pt = (fs / 12700) if fs else 10
                    sp = p.space_before
                    sp_pt = (sp / 12700) if sp else 0
                    chars_per_line = max(1, int(shape.width / 914400 / (font_pt / 72 * 0.55)))
                    n_lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
                    total += n_lines * font_pt * 1.3 / 72 + sp_pt / 72
                if total > box_h + 0.15:
                    print(f'Slide {si+1}: TEXT OVERFLOW {total-box_h:.2f}in')
    ```
    
    **Critical case:** Summary slides with 3+ samples, each having 5+ lines of text, easily overflow a 3-inch textbox. Fix: compress to 2 lines per sample (stats + annotation/TSS on one line each), reduce font sizes (9pt body, 8pt details).

26. **`tf.auto_size = None` prevents text box expansion** — By default, python-pptx text frames can auto-expand beyond their declared height when text is long. Set `tf.auto_size = None` on text frames that must stay within Layout-allocated bounds:
    ```python
    alloc = lay.allocate(lay.remaining)
    tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(alloc[0]), Inches(CONTENT_W), Inches(alloc[1]))
    tf = tx.text_frame
    tf.word_wrap = True
    tf.auto_size = None  # CRITICAL: prevents expansion beyond alloc[1]
    ```

27. **User expects actual visual verification, not just code checks** — After generating a PPT, programmatically inspect EVERY slide for: overflow (shape bottom > SLIDE_H), negative dimensions, text overflow (estimated text height > box height), and large gaps (> 0.15") between sequential elements. The user will catch issues you missed: "你确定没有溢出和重叠问题吗" means you must actually verify, not assume.

28. **`_add_picture` must return actual height; snap `lay.y` to image bottom** — After `_add_picture()` places an image, the actual rendered height may be LESS than `alloc[1]` (because aspect ratio scaling produces a shorter image). If you don't correct `lay.y`, there's a large gap between the image and the conclusion text. Fix:
    ```python
    def _add_picture(slide, img_path, left, top, max_width, max_height):
        # ... compute w, h preserving aspect ratio ...
        slide.shapes.add_picture(...)
        return h  # MUST return actual height
    # In slide builder:
    alloc = lay.allocate(img_h)
    if alloc:
        actual_h = _add_picture(slide, img, MARGIN_L, alloc[0], CONTENT_W, alloc[1])
        lay.y = alloc[0] + actual_h  # snap to actual bottom, NOT alloc[0]+alloc[1]
    lay.gap(0.05)
    ```
    Without this, slides 6 (Cutoff) and 8 (TSS) had 0.8-0.9" gaps between image and conclusion.

29. **Two-column layout: allocate header and table SEPARATELY** — The old pattern of computing `row_h = 0.22 + 0.03 + max_tbl_rows * 0.23` and allocating the whole row at once is FRAGILE. PowerPoint tables have internal cell padding that makes rendered height differ from the allocated height, causing header↔table overlap (0.03" gap looks like overlap). Fix: allocate header and table as separate elements:
    ```python
    # CORRECT — each element gets its own allocate
    hdr_alloc = lay.allocate(0.22)
    # place headers at hdr_alloc[0]
    lay.gap(0.05)
    tbl_h = min(max_rows * 0.22, lay.remaining - 0.4)
    tbl_alloc = lay.allocate(max(tbl_h, 0.4))
    # place tables at tbl_alloc[0]
    lay.gap(0.15)
    ```
    This ensures each element has its own tracked position, and gaps between elements are explicit (not implicit from formula differences). Also works correctly with different `--top-n` values (5, 10, etc.) because there's no hardcoded per-row formula.

30. **Test with different data sizes, not just the default** — When the script supports `--top-n`, test with BOTH the default (5) and a larger value (10). Hardcoded layouts that work for 5 genes may overflow with 10. The Layout class handles this automatically IF elements are allocated separately (not via formulas).

31. **`tf.auto_size = None` on conclusion textboxes** — Without this, python-pptx text frames auto-expand beyond their declared height when text is long, causing overlap with elements below. Always set it on textboxes that occupy `lay.remaining`:
    ```python
    alloc = lay.allocate(lay.remaining)
    tx = slide.shapes.add_textbox(Inches(MARGIN_L), Inches(alloc[0]), Inches(CONTENT_W), Inches(alloc[1]))
    tf = tx.text_frame
    tf.word_wrap = True
    tf.auto_size = None  # CRITICAL
    ```
