---
name: bioinformatics-wiki
description: "Obsidian omics wiki pages: ATAC-seq, MS, RNA-seq style."
---

# Bioinformatics Wiki Documentation

Use when creating or editing omics/bioinformatics technique wiki pages in the user's Obsidian vault. These live under `Wiki/ScienceEngineering/DataScience/Bioinformatics/Omics/`.

## Reference Style

The best template is `ATAC-seq.md` in the Omics directory — read it before writing any new doc. `MS.md` is another good example (larger, covers qualitative + quantitative + PTM + clinical).

## Content Philosophy

User explicitly corrected twice: **拒绝教科书式写法**. Rules:
- Do NOT list every technical parameter exhaustively
- Organize by practical scenario / clinical application, not by encyclopedia structure
- Emphasize feasibility (可行性) and real-world applicability (落地性)
- Include workflow diagrams, comparison tables, and tool recommendations — not dry definitions

## Document Structure

### Frontmatter
```yaml
---
title: 技术名称（中文全称+英文缩写）
tags: [大类, 子类, 组学]
wiki: https://en.wikipedia.org/wiki/Article
---
```

### Standard Sections (adapt as needed)
1. **一、概述** — Definition, inventor/year, position in omics landscape
2. **二、基本原理** — Core concepts, ASCII art diagrams, technology comparison table
3. **三、样品前处理/实验流程** — Step-by-step ASCII tree (`│ ├── └──`)
4. **四、数据采集模式** — Mode comparison table (if applicable)
5. **五、数据分析流程** — Standard pipeline flowchart + QC metrics table
6. **六、下游分析** — Differential analysis, enrichment, visualization
7. **七、工具与平台** — Tool table (tool | purpose | notes)
8. **八、应用领域** — Organized by scenario/disease
9. **九、参考资源** — Original papers + tutorial links

### Formatting Conventions
- Chinese prose, English technical terms kept as-is
- Flow diagrams: ASCII art with `│ ├── └──` and `→` for outputs
- Comparisons: Markdown tables
- Tool lists: tables (Tool | Use | Notes)
- QC metrics: tables (Metric | Expected | Description)

## Renumbering Pitfall

When inserting a new section mid-document, ALL subsequent section numbers (e.g. 七→八→九) AND sub-section numbers (e.g. 7.1→8.1) must cascade-update. 

**Safe approach**: use `execute_code` with `hermes_tools.patch()` in a loop. Build the mapping first (old→new for both sections and sub-sections), then apply. Change sub-section numbers before section headers to avoid conflicts.

## Sample Metadata Descriptions

When user pastes a GEO/SRA sample table and asks for a description ("添加描述"), see `references/sample-metadata-descriptions.md` for conventions. Key rules:
- Always explain relationships between experimental factors, not just list them (user corrected: "PKR和Dicer的关系没有交代")
- When user asks to verify design ("确保真实设计"), check SRA pages (accessible, rich metadata) before GEO (reCAPTCHA blocked). CNGB metadata (CNP/CNS accessions) provides project-level context if user supplies it.
- When multiple datasets are in conversation, "上面的样本" likely means the most recent one unless explicitly stated otherwise.

## Result Directory Scanning

When analyzing a research group's results folder structure (not writing wiki pages, but constructing research narratives from existing data), see `references/result-directory-conventions.md` for:
- Directory name → analysis type mapping (GSEA, TE, DDR, SNP, etc.)
- How to extract experimental conditions from folder/file names
- How to cluster projects into a coherent thesis narrative
- Common pitfalls (typos in gene names, lock files, compressed archives)

## Existing Documents

| File | Topic | Richness |
|------|-------|----------|
| ATAC-seq.md | Chromatin accessibility | ★★★ Best template |
| ChiPseq.md | Protein-DNA interaction | ★★ |
| MS.md | Mass spectrometry / proteomics | ★★★ Qual+Quant+PTM+Clinical |
| WES.md | Exome sequencing | ★★ |
| scRNAseq/ | Single-cell RNA-seq | ★★★ Directory-level |
| RNAseq/ | Transcriptomics | ★★ Directory-level |
