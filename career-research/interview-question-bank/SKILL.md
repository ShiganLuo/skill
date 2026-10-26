---
name: interview-question-bank
description: "Compile 面试题/面经 into cited question-bank markdown docs."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [career, interview, 面试题, markdown, research]
    related_skills: [career-research, grounded-citations, browser-use]
---

# Interview Question Bank Documents (面试题汇编)

Deliverable class: a cited markdown doc of interview questions for a company
or role, compiled from public sources. Trigger: user asks to 搜索/整理/汇总
面试题、面经 for a company or role. Output location convention for this
user: `Wiki/职业发展/面试题/` (cross-link company notes via `[[公司名]]`).

## When to Use

- User asks to 搜索/整理/汇总 interview questions (面试题、面经、题库) for a
  company, role, or industry — e.g. "搜索镁伽产品应用岗面试题", "整理生信面试题".
- Also when extending an existing bank doc with newly scraped sources.
- Not for spoken self-introductions (see `interview-self-introduction`) or
  resumes (`career-research` → resume workflow).

## Format rule (explicit user correction — non-negotiable)

> "每个面试题尽量单独占据一行，编号好，现在看起来太乱了"

- **One question per line, numbered**, sequential across category headings.
- Rejected layouts: questions packed into table cells, comma-run lists,
  multiple questions in one bullet — all read as "太乱".
- Category headings are Chinese-numeric sections (一、二、…); numbering does
  NOT restart per section — keep counting so the doc can be referenced as
  "第 47 题".

## Document structure (template)

1. Frontmatter + 用途 line + top blockquote stating the honest conclusion
   (e.g. "该岗位目前没有公开真题，以下题单为同岗位迁移")
2. **岗位要求（JD 实录）** — verbatim duties/qualifications from real postings, sourced
3. **真实渠道盘点** — which channels were checked (牛客/应届生/知乎/小红书/贴吧),
   what each returned, and *why* no direct 真题 exists; keep failure evidence
   (e.g. "牛客企业页明示'暂无面试经验'")
4. **依据 JD 的推测题** — explicitly labeled 推断/非真题, each mapped to its JD basis
5. **题库分节** — numbered questions from scraped 题单/面经 (see vetting below)
6. **抓取方法** — reusable acquisition notes (see `browser-use` → xiaohongshu reference)
7. **参考来源** — one link per source; verify with `grounded-citations`
   (`sources.py add` → `render --replace-in` → `verify`) for shared/long-lived
   docs, inline links for single-company notes

## Content vetting (learned the hard way)

- **公司真题 vs 通用题库帖** must be labeled separately: study-material posts
  ("资料见主页店铺" watermark) are generic banks, not any company's real questions.
- **同名公司 traps**: 镁伽科技 ≠ 镁佳科技 (automotive); mis-attributed 面经 is
  worse than none. Filter scraped notes by exact company string in the body.
- **"面经" may be an AI bot reply** (nowcoder AI客服 threads) — read the body
  before counting it as an interview record.
- **Caption ≠ content on image-carousel platforms**: a note with an 18-char
  caption can hold its entire interview report in slide images. Always
  enumerate `.swiper-slide:not(.swiper-slide-duplicate) img` and OCR
  (`tesseract -l chi_sim --psm 6`) before concluding "no content".
- When native vision attachments can't be read, say so and fall back to OCR —
  never fabricate transcriptions.

## Sourcing breadth (user expectation)

**Channel priority (explicit user correction, 2026-10): 小红书 FIRST** — "尤其是小红书".
Reason: XHS notes are essentially invisible to web search engines (web_search
returns almost nothing from xiaohongshu.com), so logged-in scraping via
`browser-use` (see its xiaohongshu-scraping reference) is the *only* path —
don't conclude "no XHS content" from web_search results alone.

Search widely in one pass: company-name queries + role-name queries across
小红书 (browser + login; see `browser-use`), 知乎 (question pages readable
anonymously; in-site search needs login; find entry points via
`site:zhihu.com` web search), 牛客/应届生 (company pages), 贴吧 (usually
behind Baidu captcha — record as gap, don't auto-solve). End with an honest
gap statement listing channels that failed and why.

## JD-screenshot intake (common opening move)

Task often starts with a phone long-screenshot of a job posting (BOSS直聘 etc.)
to be OCR'd into the company note before the question-bank research. Use a
vision model (GLM `glm-4.5v` one-shot works on 4000px+ long images; tesseract
garbles them — see `browser-use` xiaohongshu reference §5), append verbatim JD
to `Wiki/行业/公司/<公司>.md`, then run the sourcing pass above.

## Self-intro supplementary materials (course/GPA/competition blocks)

Openers for 面试自我介绍 often need verifiable "教育背景" blocks: GPA/加权平均分,
course lists, competition awards. Sourcing rules:

- **GPA/成绩单**: always recompute from the transcript screenshot with code — do NOT
  trust numbers previously written into the user's notes (found 89.10/16门/24学分 in
  the user's 自我介绍.md vs. actual 88.56/17门/26学分 from the grade screenshot).
  State both stats only after code-verified agreement with the transcript's own
  自报值 (e.g. 平均学分绩 84.57); small deltas (±0.1) from vision OCR error are OK,
  note them.
- **Competition awards**: read the certificate image itself (vision_analyze) for the
  verbatim 课题名称, team size, award level, date, 证书号 — never reconstruct from
  memory. If the user ranked mid-team (e.g. 4th of 5), proactively suggest framing:
  state "5人团队、我负责X模块" and prepare for the "你具体做了什么" follow-up.
- **课程列表输出格式 (explicit user correction)**: when the user asks "列出课程",
  output course NAMES ONLY, comma-separated — no grades, no credits, no commentary,
  no "加戏". The structured grade+credit tables go into the notes document, not into
  chat replies. Contrast: "直接输出课程名称即可，别加戏".
- **网申开放题 (对公司的看法/自我评价/职业规划)**: three-part structure — 看法 (3 reasons
  anchored to company's REAL public strategy, verify via web_search of official
  site/news), 自我评价 ("生物科班+工程交付" composite formula), 规划 (短/中/长期 with
  role progression). Always ALSO provide a ~100字 精简版 per section for word-limited
  网申框. Write to `Privacy/研究生/求职/基本材料/网申/<公司>_<岗位>_开放题.md`.

## Evidence-strength labeling (2026-10 爱迪特 round, worked well)

When the target role has NO public 真题 (common for niche roles), organize the
doc as three labeled tiers instead of one mixed list — 【迁移】(real 面经 from the
SAME company, other roles — flow/style transfers), 【通用】(same-role generic bank
from comparable companies), 【推测】(inferred from each JD clause, cite the clause).
Number continuously across all tiers so "第N题" stays referenceable. State the
"no public 真题" conclusion honestly in the top blockquote.

Cross-check salary/process intel from offer-贴 and 面经帖 (e.g. 单休/薪资/试用期
from a posted offer letter) — often more valuable to the user than the question
list itself. Keep it in a "真实情报" section with per-claim note links.
