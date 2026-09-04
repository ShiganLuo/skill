# Extracting Internship/Work Details from Documentation

When the user provides a path to company work documentation (e.g., `~/笔记/Wiki/行业/工作/公司名/`), use this pattern to extract resume-worthy details.

## Typical Chinese biotech/pharma company documentation structure

```
公司名/
├── 工作交接文档.md        ← PRIMARY SOURCE: lists all tasks, modules, status
├── 工作日志/
│   ├── 工作项目.md        ← project assignments by month
│   └── other/             ← weekly logs
├── 调研文档/              ← research docs = skills & depth evidence
│   ├── XX指标研发.md
│   ├── XX规则研究.md
│   └── XX优化.md
├── CNC/ or 流程/          ← workflow/pipeline tooling details
│   ├── WDL/
│   └── 容器化技术/
├── NGS/                   ← domain knowledge docs
│   └── 全流程简介.md
└── 产品.md or Onco*.md    ← product-specific analysis docs
```

## Extraction priority

1. **工作交接文档** → task list with status (✅/❌), bug fixes, module names
2. **调研文档** → research depth: statistical methods, sample sizes, algorithms
3. **CNC/流程目录** → technical stack: WDL, Cromwell, Singularity, scheduling
4. **产品文档** → product names (OncoTOP, OncoWES, etc.), clinical context
5. **工作日志** → timeline, project scope

## How to write resume bullet points from work docs

Don't copy work docs verbatim. Synthesize into achievement-oriented bullets:

**Bad** (copied from 交接文档):
> SomVAS/anno_ensemble.py phgvs解析报错修复

**Good** (synthesized for resume):
> 修复 SomVAS 注释模块 phgvs 解析报错，保障变异注释流程稳定性

**Bad** (vague):
> 负责流程开发

**Good** (specific, with scale):
> 负责体细胞突变过滤规则的理论推导与实验验证，基于 3860 例临床样本数据完成统计分析，输出 IVD 注册审评所需技术文档

## Reading actual GitHub repos for project descriptions

When the user provides GitHub links, ALWAYS read the actual repo before writing descriptions:
1. `git remote -v` in local project dirs to verify repo name
2. `browser_navigate` to the GitHub page to read README and directory structure
3. Extract real workflow names, tools, architecture from the repo
4. Repos evolve — a project with 288 commits today is very different from what it was 6 months ago
5. Don't use previous session's stale memory of a repo

## Template for internship section

```markdown
### 公司名 — 岗位名称（实习）
城市 | 起止时间

**一句话概述核心职责**

**项目/职责块A**（用粗体命名，不用列表）
描述做了什么、用了什么技术、产出是什么。一段话，不是bullet列表。

**项目/职责块B**
同上。

**流程性能优化**
简要说明优化策略和效果。
```

Note: consolidate bug-fix/maintenance work into ONE block, not individual bullets per bug.
