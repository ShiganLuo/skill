# README prose style for Omics project

When writing or rewriting the human-facing sections of `workflow/Omics/README.md` — `## 真实场景`, `## pipeline 选型`, and any other "why this project exists" prose — apply the following style conventions. They were set by direct user correction after a flat, engineering-doc-style draft was rejected with "不是很吸引人" and "你自己尝试重构,不要问我".

## Voice and POV

- **First person, "I" / "我".** The Omics project is a personal tool, not a product. The README is the developer explaining to a future self (and any reader) why the project exists and how they came to the choices they made. Use "我" — not "本项目"/"Omics 提供了"/"我们".
- **Specific dates, named projects, named tools in the actual order they happened.** "2023 年 9 月,我给一个 WGS 项目交付了一份'全自动'脚本" beats "流程跑完三个月后,用户往往无法复现结果". Specificity is what makes it feel like a real person talking.
- **Emotions and stakes are allowed.** "我打开那份脚本:参数去了哪儿?env 被覆盖了..." The panic of finding your own project unreproducible is part of the truth.

## Structure conventions

- **真实场景: use 3–4 grouped narratives, not a flat numbered list of 6 bugs.** Group scenarios into bigger arcs (e.g., "流程能不能被信任", "流程能不能长大", "流程的本质是探索而不是执行"). The grouping itself carries meaning — each group ends with a one-line statement of what it asks of the project ("这一组对应的是——").
- **设计原则段: keep abstract.** Do not name Snakemake / Nextflow / Conda / SIF in this section. The principles describe a stance, not a tool choice. Tool names belong in `## pipeline 选型`.
- **pipeline 选型: write a decision narrative, not a comparison matrix.** Acknowledge that all three candidates (Snakemake, Nextflow, WDL) could pass a feature checklist. What actually decided it was structural — two specific things (output-as-first-class-citizen, LLM-as-Python-native) where one tool made them free and the others made them extra work. End by explicitly stating where the chosen tool is *not* the right answer ("如果你要 GCP / AWS 大规模调度,Nextflow 才是正确答案").

## What to avoid (anti-patterns the user rejected)

- **Third-person, neutral tone.** "项目上线后第一周一切正常..." is the tone of an incident report, not a developer's README.
- **Numbered bug lists.** Six parallel "场景 1...场景 6" with no grouping reads like a Stack Overflow answer.
- **Comparison tables for design decisions.** "Snakemake 6/6, Nextflow 4/6, WDL 3/6" gives the answer but kills the reasoning. Tables turn a decision into a verdict; narratives show why the verdict is right.
- **Asking the user how to restructure before writing.** For obvious "rewrite to be less flat" tasks, ship a draft and ask for revision afterward. The user explicitly said "不要问我" after I asked two rounds of clarifying questions on a structural choice. Default to acting; reserve questions for ambiguity that materially changes the tool call.
- **Padded design language.** "tapestry of", "underscoring", "key takeaway", "vital role" — see the `humanizer` skill for the full list. These are the AI tells that make prose feel assembled rather than written.

## Process

1. Read the current README section (targeted `read_file` with offset/limit, not full read).
2. Identify which arc/group the content belongs to. If the content is a numbered bug list, regroup into 2–4 narratives.
3. Rewrite. Use first person, concrete dates/projects, named tools and people only when they're part of the story.
4. Verify any cross-references (e.g., "对应痛点:场景 1" inside `## 设计原则`) still match the new grouping names — patch them in the same pass.
5. Show the user the diff (the `patch` tool returns one automatically). Do not silently overwrite.

## When this reference applies

- `## 真实场景` and `## pipeline 选型` sections of `workflow/Omics/README.md`.
- Any future README addition that explains *why* a design choice was made — module-level READMEs, the top-level project README, blog post drafts.
- This reference does **not** apply to in-code docstrings, Snakemake rule comments, or `config/*.json` schema docs. Those stay terse and objective.