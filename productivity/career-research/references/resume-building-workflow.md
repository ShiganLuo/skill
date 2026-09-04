# Resume Building Workflow (简历优化)

## When to Use

User asks to create, improve, or update their resume/CV. Especially when they have existing wiki/documentation that contains additional skills, projects, and knowledge to incorporate.

## Workflow

### 1. Extract Existing Resume

```python
import pymupdf
doc = pymupdf.open("resume.pdf")
text = "\n".join(page.get_text() for page in doc)
```

### 2. Scan Wiki / Project Files for Gaps

Read the user's wiki, project directories, and code repos to find:
- **Missing projects** not on resume (e.g. full-stack platforms, analysis pipelines)
- **Undersold skills** (e.g. resume says "RNA-seq" but wiki shows deep knowledge of DESeq2/limma/edgeR, WGCNA, fusion genes, alternative splicing, TE quantification)
- **Missing work experience** (check memory for current employer/internship)
- **Tool proficiency depth** (wiki tool pages reveal actual hands-on experience)

### 3. Structure Improvements

| Section | Enhancement |
|---------|-------------|
| **个人总结** | Add specific omics types, pipeline tools, clinical bioinformatics keywords |
| **专业技能** | Use table format: 编程语言 / 流程开发 / 组学分析 / 临床生信 / 生信工具 / 全栈开发 |
| **实习经历** | MUST include all work/internship. If details unknown, provide template with ⚠️ marker |
| **项目经历** | Expand with specific analysis modules from wiki (not generic descriptions) |
| **科研与竞赛** | Separate section for awards, knowledge system building |

### 4. Output Format

- **Default**: Markdown (.md) — user reviews and edits first
- **PDF**: Only on explicit request. Use reportlab with Noto Sans CJK SC font:
  ```
  /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
  /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
  ```
- **Save to**: same directory as original resume with `_改进版` suffix

## Pitfalls

1. **Always check memory for current employer/internship** before writing. The user may have work experience not on the original resume.
2. **Don't auto-generate internship descriptions** — provide a template with ⚠️ and ask user to fill in specifics. You don't know their actual responsibilities.
3. **Don't convert to PDF without asking** — user may want to review/edit markdown first. (Session lesson: user said "先不转成pdf" mid-conversion.)
4. **Cross-reference wiki for depth** — if resume says "RNA-seq" but wiki has pages on WGCNA, alternative splicing, TE quantification, fusion genes → expand the project description with these modules.
5. **Chinese resume conventions**: keep it concise (1-2 pages equivalent), no photo placeholder, include 排名 if available, CET-6 for English proficiency.

## User Context (2027届)

- 南昌大学 生命科学 (本科) → 南开大学 生物技术与工程 (硕士, 2024-2027)
- Currently at 吉因加 (Geneseeq), Beijing
- Target: medical AI / LLM direction, bioinformatics engineer roles
- Has extensive wiki covering multi-omics, full-stack dev, pipeline engineering
