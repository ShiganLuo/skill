---
name: interview-self-introduction
description: "Use when tailoring a spoken 面试自我介绍 to a specific JD."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [career, interview, job-application, chinese-job-market]
    related_skills: [resume-building, resume-writing, career-research]
---

# Spoken Self-Introduction Tailoring (面试自我介绍)

Use when the user asks for a self-introduction for a specific company/role (口头自我介绍, not the written resume). The deliverable is a spoken-text template appended to the user's wiki file.

## When to Use

- User says "帮我做一个XX公司XX岗位的自我介绍" / "针对这个JD写自我介绍" / "面试自我介绍".
- User shares a job posting and wants interview talking points mapped to their background.
- NOT for the written resume itself → `resume-building` / `resume-writing`.
- NOT for researching which companies to apply to → `career-research`.

## Workflow

### Step 1: Locate the target file
`/home/<USER>/Work/<USER>/work/笔记/Wiki/职业发展/自我介绍.md` holds:
- `## 模板1` (generic) + a shared 教育背景 facts block (南开硕士 GPA 3.75/89.1; 南昌大学本科 生命科学 11/63 + 辅修数据科学与大数据技术 1/31)
- per-role sections headed `## <公司> <岗位>（<届别>校招）` with a `[[公司]]` wikilink (only 模板1 keeps a number) — **APPEND a new per-role section; never modify existing templates or the facts block.** Confirm the current numbering/heading convention by reading the file first — it has evolved.

Each template's structure:
```
## <公司> <岗位>（<届别>校招）

[[<公司>]]

岗位关键词：<JD 核心职责的压缩>
加分项：<JD 加分项里我们能兑现的；不可兑现的明确标注并说明为何未写入正文>

---

<spoken text>
```

### Step 2: Get the real JD before writing
**Never write from the job title alone** — you need the actual bullets (职责/要求/加分项).
- **User already supplied the JD** (screenshot, pasted text, attached file): use it as-is, no aggregator scraping needed. If it's an image, extract verbatim first: built-in vision read + tesseract OCR cross-checked across `--psm 4/6/11` (system tesseract ships eng/osd only — one-time bootstrap: download `chi_sim.traineddata` from the jsdelivr tessdata_fast mirror to `/tmp` and run with `TESSDATA_PREFIX=/tmp`; raw.githubusercontent.com may fail with SSL EOF), then write from the agreed text.
- Otherwise, campus postings on company/university pages often list only job titles; the full JD usually lives on aggregators: shushuqiuzhi.com, nowcoder.com, upcv.tech, university 就业平台 pages.
  - `web_search` = `"<公司名>" "<岗位名>" 职位描述 岗位职责`
  - `web_extract` the most specific hit; confirm you have the actual bullets.

### Step 3: Map JD bullets 1:1 to resume evidence
- Build exactly **3 匹配点**, each anchored to ONE JD bullet with ONE concrete example from the user's resume/projects (source: `罗时敢_简历.html` under `~/Work/<USER>/Privacy/研究生/求职/基本材料/`, or the education facts block).
- Strongest closed-loop side project first (BioPlatform / Omics framework are the usual anchors).
- Example mapping pattern (see `references/jd-mapping-example.md`): JD says "在 AI 说没问题之后再检查一遍" → cite the SecurityContext 跨线程鉴权 fix found during review.

### Step 4: Front-load the mismatch fix
If the user's major ≠ JD's required major (common: biology master's → CS roles), fold the rebuttal INTO a 匹配点 (辅修排名 1/31 / 计算方向 / 工程手段解决陌生领域), not into a closing disclaimer.

### Step 5: Format of the spoken text
- ≈ 1.5 minutes read aloud (~500-600 汉字).
- Plain first-person prose: 面试官您好 → "从X和Y两部分介绍" → 项目段 → 三个匹配点（第一/第二/第三） → 谢谢. No bullet walls in the spoken portion.
- 产出导向: every claim carries a concrete artifact or number.

### Step 6: Deliver + offer, don't grow unilaterally
State the JD keywords you targeted and the read-aloud length. Offer optional additions (e.g. compressing the internship into one line) as a next step — do not unilaterally lengthen it.

## Register corrections are LOCAL, not global (2026-10 镁伽 round — full rewrite rejected)

When the user flags the spoken text as "过于AI化", do **NOT** rewrite the whole piece into a colloquial register. The 报幕式开场 ("接下来我从教育背景和相关经历两部分展开") and the tidy 第一/第二/第三 structure ARE the user's preferred format. A full colloquial rewrite ("我的背景简单说就是生物科班+动手交付"…) was rejected outright ("还不如之前的"). What "AI化" meant in practice: individual sentences with 语病 or factual drift. So:

- Fix ONLY the specific sentence the user quotes; keep everything else verbatim.
- Typical real fixes: 语病 ("养成了定位可复现问题的习惯" → "养成了先把问题定位到可复现再动手的习惯"), and factual accuracy (see next pitfall).
- Keep info density (排名、例数、月份) — cutting numbers to "sound human" reads as a different kind of AI voice, not less of one.

## Verify internship claims against the actual work notes before writing

The 吉因加 internship claims must be checked against the user's real work notes at `Wiki/行业/工作/吉因加/` (`工作交接文档.md` is the index; `调研文档/` holds study write-ups) — invented or remembered-loosely phrasing got corrected twice in one session. Ground-truth example (过滤规则研究):

> 实习期间我负责过滤规则研究，基于 3860 例临床样本的测序错误数据建立统计模型，输出了过滤阈值的理论推导、灵敏度与假阳性率模拟和实验验证整套研究资料，用于 IVD 注册申报。

Wrong variants that were rejected: "输出了规范、可追溯的全套技术文档" (too vague), "IVD注册用的全套技术资料" (注册材料 is the PURPOSE, not the deliverable name), "IVD注册过滤规则的大部分技术资料" (修饰关系拧了 + "大部分"含糊).

## Pitfalls

- **Sensitive words**: the 吉因加实习 forbids internal tool names (CNC, OncoDR, Mutect2, STAR, RealDcaller, pVACtools, cnc_sta.py) — use generic terms. For non-生信 roles the internship often can be omitted entirely; projects hit harder.
- **Company full names** in prose; no 夸张 claims ("源码级", "精通" beyond what projects evidence).
- **Don't invent tools** the user hasn't used — pull only from the resume HTML and existing 模板 facts.
- **Project facts**: the Omics framework was **primarily hand-coded; AI tooling was adopted later** — never describe it as AI-developed (user corrected this). BioPlatform is the AI-assisted project. GitHub profile (ShiganLuo, 8 public repos, Python/Java/Vue/Shell, blog.shiganluo.top) can be cited as verifiable evidence for JD 加分项 "个人博客+GitHub/开源".
- **JD pages may be dead**: if aggregators 404, fall back to the company's 岗位列表 on nowcoder/BOSS; if still no JD, say so and ask which bullets to target instead of guessing.
- **Overlap note**: `resume-building` / `resume-writing` skills cover the written resume; this skill covers the spoken intro only.

## Reference

See `references/jd-mapping-example.md` for a worked example (未岚大陆 AI原生后端工程师: JD keyword → 匹配点 mapping and where the JD was found).
