# Worked Example: 未岚大陆 AI原生后端工程师 (2027届校招)

## Where the JD was found

1. University 就业平台 (浙江大学) had ONLY the job-title list — no JD bullets.
2. `web_search: "未岚大陆" "AI原生后端" 职位描述 岗位职责` → aggregator
   `shushuqiuzhi.com/position/453206` had the full JD.
3. First search attempt failed (keyless Exa backend error) → retried with a
   slightly different query and it worked. Retry before concluding "no JD".

## The JD (condensed)

- 岗位定位: 招"会用 AI 写代码、并敢对结果负责的人"；前后端不是边界，是工具。
- 职责: ① AI-First 全栈开发 (vibe coding with Cursor/Claude Code/Codex)
  ② 需求拆解 → AI 可理解的任务 + Prompt/上下文编排 ③ 对 AI 产出做架构/安全/性能
  review，识别幻觉和边界 case ④ 端到端交付负责，不甩锅给"AI 写的"
  ⑤ 探索新 AI 工具优化团队人效
- 要求: 2027届 CS相关硕士；全栈认知；日常用 AI 编程工具做过项目；有独立
  side project 完整闭环；对 AI 输出保持健康怀疑；2周上手新技术
- 加分: 个人博客+GitHub/开源、搭过 AI Agent 或自动化工作流、Docker/云部署、
  产品思维、IoT/机器人热情

## Keyword → 匹配点 mapping

| JD bullet | 匹配点 | Evidence used |
|---|---|---|
| 端到端交付负责 + 技术review兜底 | 匹配点一：端到端交付 | BioPlatform 一人交付（需求→开发→Docker→上线）；具体例子 = review 时发现 AI 代码异步拿不到登录用户 → SecurityContext 跨线程传播（正好演 JD 的"AI 说没问题之后再检查一遍"） |
| AI-First 开发 + Agent 编排 | 匹配点二：AI 工具链是日常工作方式 | 日常用 Claude Code/Cursor；实际搭过 Agent：BioPlatform 多智能体编排（意图识别→Agent路由→SSE→工具调用链）、Omics 的 LLM 自动注释模式 |
| 全栈认知 + 非CS专业顾虑 | 匹配点三：专业跨度反而转成优势 | 本科辅修数据科学与大数据技术排名 1/31；硕士计算方向；向量化/并行化性能优化经验 |

## Structural decisions worth reusing

- Open with 两个独立交付项目 before any 匹配点 — the JD's #1 signal is
  "side project 完整闭环", so lead with it.
- The major mismatch (biology → CS role) was folded into 匹配点三 as a
  strength, not mentioned as a caveat anywhere.
- 敏感词: internship internal tool names avoided entirely; internship omitted
  from this intro (projects hit harder for this role) — offered to add a
  one-line internship mention as follow-up instead of growing it unilaterally.
- Result: ~1.5 min spoken, file append created 模板2 in 自我介绍.md.
