---
name: resume-writing
description: "Create/review resumes with interviewer critique."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [resume, career, job-search, editing]
    category: productivity
---

# Resume Writing & Review

Write, review, and iteratively refine technical resumes. Emphasizes interviewer-perspective critique, source-grounded content enrichment, and Chinese-language tech resume conventions.

## When to Use

- User asks to create, review, or improve a resume/CV
- User asks to tailor a resume for a specific role
- User provides an existing resume PDF/doc and asks to update it
- User asks "如果你是面试官你会问什么" (if you were the interviewer...)

## Core Workflow

### Step 1: Extract & Understand Current Resume

```bash
# PDF extraction
python3 -c "import pymupdf; doc = pymupdf.open('resume.pdf'); [print(page.get_text()) for page in doc]"
```

Parse into sections: header, summary, education, skills, experience, projects, research.

### Step 2: Source Enrichment (before writing, gather REAL content)

**From work wiki/notes**: Read project documentation, work logs, technical docs to extract actual work content — tools used, data scale, specific contributions, outcomes.

**From GitHub repos**: Clone or browse (use browser if git clone fails due to network) to understand:
- Repo structure (directories, entry points)
- README content (workflows supported, architecture)
- Commit history (activity level, scope)

```bash
# Try clone first
git clone --depth 1 https://github.com/user/repo.git

# If network fails, use browser
browser_navigate(url="https://github.com/user/repo")
```

**From project codebases**: Read config files, Dockerfiles, READMEs to accurately describe tech stack.

### Step 3: Interviewer-Perspective Review

After drafting, review as an interviewer. Ask yourself:

1. **Internal jargon**: Are there internal codes, project names, team-specific terms an outsider wouldn't understand? (e.g., GI3103, 瑞宏迪稽查, D2R1/D1R2)
2. **Daily-task listing**: Does the description read like a work log or handover doc rather than a resume? "Fixed 6 bugs" → merge into one result-oriented statement.
3. **Unrelated content**: Does every item support the target role? Remove blog projects from bioinformatics resumes, remove unrelated research papers.
4. **Skill-project consistency**: Do listed skills match what's actually used in projects/experience? (e.g., don't list Seurat if projects use Scanpy)
5. **Digging holes**: Does listing too many topics invite questions you can't answer deeply? (e.g., listing 15 omics types when only 3 were done in depth)
6. **Quantification**: Can any claims be backed by numbers? (sample count, commit count, efficiency improvement, documents delivered)

### Step 4: Iterate

Present changes with rationale. User will correct — apply immediately without debate.

### Step 5: Self-Verify Before Presenting

NEVER present markdown-only resume changes and wait for user feedback on layout. Before delivering:

1. Generate a PDF preview (see layout approach selection below)
2. Convert to PNG via pymupdf: `page.get_pixmap(dpi=200).save('preview.png')`
3. Use `vision_analyze` on the PNG to check:
   - Does it fit in one page?
   - Is the density appropriate (not too sparse, not too cramped)?
   - Are section titles visually distinct?
   - Is the spacing balanced?
4. Fix issues found, regenerate, re-verify
5. Only present to user after visual verification passes

### Layout Approach Selection

**Use HTML+CSS two-column layout** (see `references/html-two-column-layout.md`) when:
- Single-page density requires visual polish
- User wants a modern, professional look
- Content is dense (skills + experience + projects)

**Use reportlab** (see `references/pdf-generation.md`) when:
- Quick single-column layout is sufficient
- Chrome is not available
- Simple formatting needs only

The HTML+CSS approach produces significantly better visual results. Prefer it for resume work.

## Resume Section Patterns

### Experience Section (实习/工作经历)
- **Structure by project/responsibility**, not by chronological task list
- Each block: context → approach → outcome
- Merge minor fixes into summary statements
- Highlight methodology (e.g., "二项分布模型") not document names

### Project Section (项目经历)
- For open-source: include GitHub link + commit count
- List supported workflows/capabilities in a table if >5 items
- Describe architecture briefly (entry → subworkflow → modules)
- Don't duplicate skills already listed in skills section

### Skills Section (专业技能)
- Group by category in a table
- Only list tools actually used in projects/experience
- Match naming conventions to what's in the projects
- Don't list more tools than you can explain in an interview

## Reference Files

- `references/pdf-generation.md` — reportlab PDF generation template for Chinese resumes, layout parameters, and verification workflow.

## Pitfalls

- **Don't guess project content** — always read the actual repo/wiki/codebase first
- **Don't keep internal identifiers** — scrub ALL internal codes, project IDs, product model numbers, internal team names
- **Don't over-list** — a long list of omics/technologies invites "tell me about X" questions; only list what you can defend
- **Don't mix unrelated research** — an entomology paper on a bioinformatics resume creates confusion
- **Don't describe maintenance as achievement** — "fixed cnvloh bug" is daily work, not a resume bullet; reframe as "ensured CNV detection module reliability across chromosome types"
- **Don't over-compress** — when fitting to one page, removing whitespace and structure makes content feel hollow. Better to cut entire sections/subsections than to squeeze everything into dense blobs. If a project has 4 sub-modules, keep them as bullet points but shorten each, rather than merging into one unreadable paragraph.
- **Don't just compress text when layout is the problem** — if user says "still two pages", fix the layout (columns, spacing, font sizes) first, not just cut words. Switching from single-column reportlab to two-column HTML+CSS often solves the problem without cutting content.
- **User wants editability** — keep markdown (.md) as the editing surface. Generate HTML+PDF from it via script. Don't hand the user a complex HTML file to edit.
- **PDF output**: Use HTML+CSS two-column layout (Chrome headless) for best visual results. Fall back to reportlab with Noto Sans CJK SC font for simpler cases; fonts at `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`

## Chinese Tech Resume Conventions

- One page preferred for campus recruitment (校招)
- CET-6 is expected to be listed
- 排名 (ranking) is common and valued
- Skills table format is standard
- Personal summary (个人总结) should be 2-3 sentences, not a paragraph
- GitHub links on projects is increasingly expected
