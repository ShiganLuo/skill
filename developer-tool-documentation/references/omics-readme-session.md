# Session reference: Omics README rewrite

Session-specific notes from the 4-round rewrite of `/home/luosg/Data/genomeStability/workflow/Omics/README.md` opening sections. Kept under the skill as a worked example; not load-bearing for the skill itself.

## What was rewritten

Original opening had three sections that the user pushed back on across 4 rounds:
- `## 真实场景` — six numbered pain-point sub-sections in third-person ("项目上线后第一周...")
- `## 设计原则` — six numbered principles (参数版本化, 模块化共享, 声明式 DAG, etc.) with "对应痛点" back-references
- `## pipeline 选型` — narrative about choosing Snakemake over Nextflow/WDL, with a principles × tools comparison table

Final state: replaced all three with a single `## 解决什么问题` section. Six pain points, each formatted as a "**Pain sentence.** Solution description. ```bash command```" triplet. ~50 lines, no origin story, no principles, no competitor comparison.

## What the user actually pushed back on (in order)

1. Round 1: "不是很吸引人" — too neutral, didn't hook. User wanted more punch.
2. Round 2: "AI味道太浓了" — too many bold runs, too many "不是X而是Y" reversals, too many parallel section structures. User caught the "三个候选" / "结构问题" / "结构便宜" repetition and called it out as AI tells.
3. Round 3: "另个人想知道你怎么设计,用户只想知道你能否解决他的问题,而不是一堆原则,还有你自己的经历" — the decisive critique. The reader is not the author; delete personal stories, principles, design rationale.

## Key patterns observed

- The user's first two critiques were *prose*-level (could be fixed by humanizer). The third was *structural* (audience model was wrong). Recognizing when a critique is structural vs prose is the actual skill.
- The user accepted "Principle 5/6" framing in round 1, then rejected all principles in round 3. The thing they accepted was not the thing they actually wanted.
- The "principles × tools comparison table" looked like it answered a question, but it answered a question only the author was asking.
- "## 当前流程特点" and "## 计划" sections were kept untouched — these are forward-looking capability/roadmap lists that users actually want.

## Commands the user mentioned approving

Concrete CLI snippets that landed well in the final "解决什么问题" section:
- `python run.py --Params.trim_galore.quality 10` (parameter override)
- `python run.py --auto --tissue ovaries` (scRNAseq LLM mode)
- `python run.py --until mutation_markduplicates` (stop at intermediate)
- `python run.py --forcerun function_gsea --target-jobs function_gsea:sample=S1` (re-run specific wildcard)

These were drawn from the actual codebase at `/home/luosg/Data/genomeStability/workflow/Omics/run.py` and its subworkflows — not invented.