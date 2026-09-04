# Interviewer Review Checklist

After drafting the resume, apply this checklist line-by-line. Fix ALL issues before delivering.

## Red Flags to Scan For

### Internal identifiers
- Project codes: GI3103, GI3106, GIN96, D2R1, D1R2, etc.
- Internal company names that aren't public (e.g., 瑞宏迪 = a partner company name)
- Internal tool names that sound cryptic to outsiders (OncoTOP/OncoWES are OK if they're public product lines)
- Database paths, server names, mount points

### "Maintenance trap"
Resumes that list bug fixes as separate achievements:
```
BAD:
- 修复 cnvloh 染色体类型不一致 bug
- SomVAS/anno_ensemble.py phgvs 解析报错修复
- somvas_merge.panel.py 合并逻辑 bug
- filter_aduc_top.py KeyError 修复
- R_X11.so 加载失败修复

GOOD:
- 负责多个肿瘤检测产品流程的模块优化与 bug 修复，包括 CNV 检测模块兼容性修复、变异注释模块异常处理等
```
Consolidate into 1-2 lines. Pick ONE representative example only.

### Skills-evidence mismatch
If skills table lists a tool but no project/experience mentions it:
- Either add it to a relevant project description
- Or remove from skills table
- Example: listing "Seurat" when all scRNAseq work uses "Scanpy"

### "挖坑" descriptions
Listing many capabilities without depth invites追问:
```
BAD: "具备 RNA-seq、scRNA-seq、WGS/WES、Panel、ATAC-seq、ChIP-seq、MeRIP-seq、MS 等多种组学数据分析经验"
→ Interviewer will ask about each one

GOOD: Only list what appears in your projects/experience with specifics
```

### Unrelated projects
Blog systems, generic web apps, portfolio sites → remove unless the target role is full-stack web dev. They dilute the bioinformatics positioning.

## Positive Patterns

### Outcome-oriented descriptions
```
GOOD: "从测序错误率出发建立二项分布模型，通过3860例临床样本的统计分析确定各变异类型的最小支持reads数阈值"
→ Shows methodology + scale + deliverable

GOOD: "通过循环→向量式操作、单线程→多线程等策略提升运行效率"
→ Shows problem-solving approach

GOOD: "支持14个工作流，覆盖转录组、表观遗传、蛋白质组、空间转录组"
→ Shows breadth through concrete numbers
```

### GitHub repo as evidence
When a project has a GitHub link, the interviewer WILL check it. Make sure:
- Repo name matches the actual `git remote -v` output
- README content aligns with what the resume says
- Commit count is accurate (use actual number from GitHub)
- The repo description matches the resume title

## Read actual repo content
Before writing project descriptions, ALWAYS read the actual repo:
1. `git remote -v` in project directories to get real repo names
2. `browser_navigate` to the GitHub page to read README and directory structure
3. Extract real workflow names, tool names, architecture details from the repo
4. Don't guess or use previous session's memory — repos evolve (288 commits!)
