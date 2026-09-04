---
name: resume-building
description: "Build/improve resumes from wiki, work docs, and repos."
version: 1.0.0
author: Hermes Agent
tags: [resume, CV, job-application, career]
---

# Resume Building from Existing Materials

Use when the user wants to create, improve, or tailor a resume/CV by combining an existing resume with supplementary sources (wiki notes, work documentation, project repositories, job descriptions).

## Workflow

### Step 1: Extract current resume content

Read the existing resume (PDF, DOCX, or MD). For PDFs, use pymupdf:
```python
import pymupdf
doc = pymupdf.open("resume.pdf")
text = "\n".join(page.get_text() for page in doc)
```

Parse into structured sections: personal info, summary, education, skills, experience, projects.

### Step 2: Identify enrichment sources

Ask or discover:
- **Knowledge base / wiki**: domain notes that reveal depth of expertise (e.g., omics techniques, pipeline tools, analysis methods)
- **Work documentation**: internship/company docs, project handoff docs, research reports
- **Project repos**: GitHub links, README files, docker-compose configs
- **Job description**: target role requirements (if provided)

Use `search_files` to find relevant content in the user's wiki/work notes directories.

### Step 3: Gap analysis

Compare resume content against enrichment sources:
- Missing work experience (e.g., internship not listed)
- Undersold skills (wiki shows deep knowledge not reflected in resume)
- Missing projects (code repos not mentioned)
- Weak descriptions (could add specific tools, metrics, scale)

### Step 4: Draft improved resume

Structure as markdown with clear sections. Key principles:
- **Be specific**: tools, data scales, sample counts, metrics (e.g., "3860例临床样本", "500GB原始数据")
- **Extract from sources, don't invent**: pull real details from work docs, wiki, and repos
- **Match target role**: emphasize relevant experience and skills
- **Keep descriptions action-oriented**: "负责X" / "优化Y" / "开发Z", not "了解X"

### Step 5: Interviewer review pass

Before delivering the resume, do a self-review AS AN INTERVIEWER. Read every line and ask:
- "Would I ask a question the candidate can't answer?"
- "Does this description tell me what the candidate DID or what they ACHIEVED?"
- "Are there internal jargon / codes / abbreviations I wouldn't understand?"

Common catches and fixes:
- **Internal codes (GI3103, D2R1, etc.)** → remove or replace with generic description
- **Internal product names** → keep only if publicly known; otherwise generalize
- **Bug-fix lists** → consolidate into "负责X流程的模块优化与bug修复" with ONE example, not 6 items
- **Skills listed but not evidenced** → remove skills that don't appear in any project/experience
- **Unrelated projects** → blog/portfolio projects that don't serve the target role → remove
- **挖坑 descriptions** → listing many omics types "具备X/Y/Z经验" invites追问; only list what you can defend

Then rewrite based on the review. The user asked "加入你是面试官" = they want this step built in.

### Step 6: Output format

Save as `.md` first for easy iteration. For PDF conversion, prefer HTML+CSS two-column layout via Chrome headless (see `resume-writing` skill's `references/html-two-column-layout.md`). Fall back to reportlab for simpler cases.

**Self-verify before presenting**: Generate PDF, convert to PNG via pymupdf, use `vision_analyze` to check layout (page count, density, spacing). Fix issues before delivering to user.

## Resume Section Conventions (Chinese job market)

- **个人总结**: 2-3 sentences, front-load degree + key capabilities
- **教育背景**: reverse chronological, include ranking/awards
- **专业技能**: table format by category (编程语言/流程开发/组学分析/临床生信/生信工具/全栈开发)
- **实习经历**: company + role + location + dates, then bullet points with specifics
- **项目经历**: project name + date + GitHub link, then description with technical details
- **科研与竞赛**: awards, publications, knowledge system building

## Pitfalls

- **Don't fabricate details**: if work docs are missing, leave a placeholder with guidance for the user to fill in (e.g., "⚠️ 请补充具体工作内容")
- **GitHub links**: verify actual repo names from `git remote -v` in project directories, don't guess. User will correct wrong repo names.
- **User said "去除X"**: remove immediately, don't ask why or suggest keeping it
- **PDF output**: user may change their mind mid-session (asked for PDF then said "先不转成pdf"). Don't pre-emptively start heavy operations
- **Sensitive identifiers**: scan for internal project codes (GI3103, D2R1, D1R2, etc.), internal company names (瑞宏迪), and internal tool names before delivery. Remove or generalize.
- **Don't copy work docs verbatim**: 交接文档 is written for the next person taking over, not for a resume. Synthesize into achievement-oriented descriptions. "SomVAS/anno_ensemble.py phgvs解析报错修复" → "变异注释模块解析异常处理"
- **Skills-evidence alignment**: if the resume lists "Seurat" in skills but all projects use "Scanpy", it's a red flag. Skills must match what appears in projects/experience.
- **Don't list maintenance as a highlight**: "修了6个bug" as separate bullet points screams junior. Consolidate into one line about "流程模块优化与bug修复"
- **Don't over-compress for one page**: Removing whitespace/structure makes content feel hollow. Better to cut entire sections than to squeeze into dense blobs. Keep bullet points but shorten each, rather than merging into unreadable paragraphs. If content still overflows, fix the LAYOUT (switch to two-column HTML+CSS) rather than just cutting words.
- **PDF visual quality matters**: reportlab output often looks "ugly" to users. HTML+CSS two-column layout via Chrome headless produces significantly better visual results. See `resume-writing` skill's `references/html-two-column-layout.md` for the template.
- **Always verify visually**: Generate PDF → convert to PNG → use `vision_analyze` before presenting. Never assume markdown renders well in PDF without checking.

## Reference materials from past sessions

See `references/work-doc-extraction.md` for the pattern of extracting internship details from structured work documentation (交接文档, 调研文档, 工作日志).

See `references/interviewer-review-checklist.md` for the interviewer-review pass checklist and common red flags.
