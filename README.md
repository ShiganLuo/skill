# Hermes Agent Skills

Skills 是 Hermes Agent 的程序化记忆——针对特定任务类型的最佳实践、命令、陷阱和工作流。每次对话开始时，相关 skill 会自动注入到 agent 的上下文中。

目录结构：`<category>/<skill-name>/SKILL.md`，每个 skill 可附带 `references/`、`scripts/`、`templates/` 等子目录。

---

## 目录

- [apple](#apple) — Apple / macOS 桌面工具
- [autonomous-ai-agents](#autonomous-ai-agents) — AI agent 编排与任务委派
- [bioinformatics](#bioinformatics) — 生物信息学流程与工具
- [computer-use](#computer-use) — 桌面自动化操控
- [creative](#creative) — 创意内容生成
- [data-science](#data-science) — 数据科学与可视化
- [devops](#devops) — DevOps、Docker、部署
- [domain](#domain) — 域名侦察
- [email](#email) — 邮件收发与管理
- [gaming](#gaming) — 游戏服务器与模拟器
- [gifs](#gifs) — GIF 搜索与下载
- [github](#github) — GitHub 工作流
- [inference-sh](#inference-sh) — inference.sh 云端 AI 平台
- [linux](#linux) — Linux 系统管理
- [mcp](#mcp) — Model Context Protocol
- [media](#media) — 音视频与流媒体
- [mlops](#mlops) — 机器学习运维
- [note-taking](#note-taking) — 笔记管理
- [productivity](#productivity) — 办公与文档
- [red-teaming](#red-teaming) — LLM 红队测试
- [research](#research) — 学术研究与论文
- [single-cell-annotation-guide](#single-cell-annotation-guide) — 单细胞注释指南
- [smart-home](#smart-home) — 智能家居
- [snakemake-config-modification](#snakemake-config-modification) — Snakemake 配置修改
- [social-media](#social-media) — 社交媒体
- [software-development](#software-development) — 软件开发全流程
- [standalone](#standalone) — 独立 skill（不属于子目录）
- [yuanbao](#yuanbao) — 元宝群交互

---

## apple

Apple / macOS 桌面工具链，需要 macOS 环境。

| Skill | 说明 |
|-------|------|
| apple-notes | 通过 `memo` CLI 管理 Apple Notes，iCloud 同步 |
| apple-reminders | 通过 `remindctl` 管理 Apple Reminders，iCloud 同步 |
| findmy | 追踪 Apple 设备和 AirTag 位置 |
| imessage | 通过 `imsg` 读取和发送 iMessage/SMS |
| macos-computer-use | Mac 后台桌面自动化（`computer_use` 工具） |

## autonomous-ai-agents

AI coding agent 的编排与委派，多 agent 并行工作流。

| Skill | 说明 |
|-------|------|
| claude-code | 委派任务给 Anthropic Claude Code CLI |
| codex | 委派任务给 OpenAI Codex CLI |
| coding-agent-delegation | 统一委派接口：Claude Code / Codex / OpenCode |
| computer-use | 后台桌面自动化（跨平台） |
| hermes-agent | Hermes Agent 自身的配置、扩展、贡献指南 |
| kanban-codex-lane | Kanban worker 中运行 Codex 的轻量约定 |
| merge-reconciler | Git 合并冲突的第三方中立仲裁 |
| opencode | 委派任务给 OpenCode CLI |

## bioinformatics

生物信息学流程——从数据下载到分析到可视化，基于 Snakemake 框架。

| Skill | 说明 |
|-------|------|
| apptainer-container-build | 从 conda YAML 构建 Apptainer/SIF 容器 |
| bioinformatics-coverage-analysis | 基因体/转录本覆盖度计算 |
| bioinformatics-sv-frequency-correction | SV 突变频率校正（ddPCR ground truth） |
| bioinformatics-tool-summary | 生信工具输出汇总脚本（TSV/VCF/BED） |
| bioinformatics-visualization | 基因组 SV 数据的出版级可视化 |
| chipseq-peak-calling-workflow | ChIP-seq peak calling 子流程 |
| cnc-sta-report-merger | 多样本基因检测报告合并 |
| msi-detection | 微卫星不稳定性 (MSI) 检测 |
| msi-detection-analysis | MSI 检测端到端分析流程 |
| msi-detection-pipeline | MSI 检测工作流构建、评估、部署 |
| ngs-data-download | 从 ENA/SRA/GEO 下载测序数据 |
| omics-workflow-data-prep | Omics Snakemake 工作流的数据与配置准备 |
| omics-workflow-test | 工作流 dry-run 测试 |
| python-scientific-plotting-scripts | 出版级 Python 绑图脚本编写与重构 |
| scanpy-scrnaseq-reclustering | Scanpy scRNA-seq 重聚类（Nature 标准） |
| snakemake-module-config | Snakemake 配置流转机制 |
| snakemake-omics-workflow | Omics Snakemake 工作流的模块添加与维护 |
| telomere-centromere-longread | PacBio HiFi/Nanopore 端粒着丝粒长度分析 |

## computer-use

后台桌面自动化——点击、打字、截图、读屏。跨平台。

## creative

创意内容生成——图、视频、设计、音乐。

| Skill | 说明 |
|-------|------|
| architecture-diagram | 暗色主题 SVG 架构图（HTML 内联） |
| ascii-art | ASCII art：pyfiglet、cowsay、boxes、图片转 ASCII |
| ascii-video | 视频/音频转彩色 ASCII MP4/GIF |
| baoyu-article-illustrator | 文章插画：类型 × 风格 × 配色一致性 |
| baoyu-comic | 知识漫画（教育、传记、教程） |
| baoyu-infographic | 信息图：21 布局 × 21 风格 |
| claude-design | 一次性 HTML 设计原型 |
| comfyui | ComfyUI 扩散模型工作流（图、视频、音频） |
| creative-ideation | 创意项目点子生成 |
| design-md | Google DESIGN.md 规范文件编写 |
| diagramming | 图表创建总览（架构图、手绘图、序列图） |
| excalidraw | Excalidraw 手绘风格 JSON 图表 |
| generative-visual-art | 代码生成艺术（p5.js、Manim、ASCII video） |
| html-design | HTML 设计原型：从快速草图到精细原型 |
| humanizer | 去除 AI 痕迹，让文本更自然 |
| manim-video | Manim CE 数学/算法动画（3Blue1Brown 风格） |
| p5js | p5.js 草图：生成艺术、着色器、交互、3D |
| pixel-art | 像素艺术（NES、Game Boy、PICO-8 调色板） |
| popular-web-designs | 54 个真实设计系统模板（Stripe、Linear、Vercel…） |
| pretext | DOM-free 文本布局的浏览器 demo |
| sketch | 快速 HTML 模拟：2-3 个设计方案对比 |
| songwriting-and-ai-music | 歌曲创作技巧与 Suno AI 音乐提示词 |
| touchdesigner-mcp | 通过 MCP 控制 TouchDesigner |

## data-science

数据科学工作流——Jupyter、统计分析、可视化。

| Skill | 说明 |
|-------|------|
| bioinformatics | RNA-seq 分析、定量、后处理的常见模式 |
| gene-body-coverage | BAM 文件基因体覆盖度曲线计算 |
| jupyter-live-kernel | 有状态 Python REPL（Jupyter 内核） |
| statistical-comparison | 两组数据的自动统计检验与可视化 |

## devops

DevOps 工具——Docker、部署、CI/CD、服务器管理。

| Skill | 说明 |
|-------|------|
| apptainer-sif-build-pitfalls | Apptainer SIF 构建陷阱与修复 |
| automated-git-push | Python 脚本定时 git add/commit/push |
| docker-networking-on-cloud | 云服务器 Docker 容器无法联网的排查 |
| gateway-troubleshooting | Hermes gateway 连接问题诊断 |
| hermes-multi-server | 多服务器 Hermes 部署（共享 memory/skills） |
| kanban-orchestrator | Kanban 看板编排器：任务分解与工作流 |
| kanban-worker | Kanban worker 行为规范 |
| sdlc-review | Kanban 实现到 review 阶段的独立验证 |
| webhook-subscriptions | Webhook 订阅：事件驱动的 agent 触发 |

## domain

被动域名侦察——Python stdlib，零依赖，零 API key。

功能：子域名发现（crt.sh）、SSL 证书检查、WHOIS、DNS 记录、域名可用性、批量分析。

## email

邮件收发与管理。

| Skill | 说明 |
|-------|------|
| email-inbox-triage | 收件箱分流：优先级排序、草稿回复策略 |
| himalaya | Himalaya CLI：IMAP/SMTP 邮件终端管理 |

## gaming

游戏服务器与模拟器。

| Skill | 说明 |
|-------|------|
| minecraft-modpack-server | 模组包 Minecraft 服务器搭建（CurseForge、Modrinth） |
| pokemon-player | 无头模拟器玩 Pokemon + RAM 读取 |

## gifs

GIF 搜索与下载（Tenor API，curl + jq）。

## github

GitHub 工作流——PR、Issue、Code Review、CI/CD。

| Skill | 说明 |
|-------|------|
| codebase-inspection | pygount 代码量、语言占比、注释比分析 |
| github | GitHub 全流程指南（gh CLI + REST API） |
| github-auth | GitHub 认证配置（HTTPS token、SSH key、gh login） |
| github-code-review | PR review：diff、inline comment |
| github-issues | Issue 创建、分类、标签、分配 |
| github-issue-to-pr | 从 Issue 到已验证 PR 的端到端流程 |
| github-pr-workflow | PR 生命周期：分支、提交、开 PR、CI、合并 |
| github-repo-management | 仓库 clone/create/fork、remote 管理、release |

## inference-sh

inference.sh 云端 AI 平台——150+ 应用，一个 API key。

涵盖：图生成（FLUX、Gemini）、视频生成（Veo、Wan）、LLM（Claude、Gemini）、搜索（Tavily、Exa）、3D、音频 TTS。

## linux

Linux 系统管理。

| Skill | 说明 |
|-------|------|
| linux-font-installation | 安装微软核心字体和中文字体（WPS/LibreOffice） |
| linux-hardware-troubleshooting | Linux 硬件诊断（音频 ALSA/PipeWire、WiFi） |
| printer-troubleshooting | Linux 打印机配置与故障排查 |
| matplotlib-significance-brackets | matplotlib 柱状图统计显著性标注（宝盖头风格） |

## mcp

Model Context Protocol——Hermes 内置 MCP 客户端。

| Skill | 说明 |
|-------|------|
| native-mcp | MCP server 配置、工具发现、stdio/HTTP 连接 |

## media

音视频与流媒体。

| Skill | 说明 |
|-------|------|
| audio-music | 音乐与音频：创作、分析、可视化 |
| gif-search | Tenor GIF 搜索与下载 |
| heartmula | HeartMuLa：歌词+标签生成音乐（开源） |
| songsee | 音频频谱图/特征可视化（mel、chroma、MFCC） |
| spotify | Spotify 控制：播放、搜索、队列、设备管理 |
| youtube-content | YouTube 转录提取、摘要、帖子、博客 |

## mlops

机器学习运维——训练、微调、推理、评估。

| 子目录 | Skill | 说明 |
|--------|-------|------|
| training | axolotl | YAML 驱动 LLM 微调（LoRA、DPO、GRPO） |
| training | fine-tuning-with-trl | TRL：SFT、DPO、PPO、GRPO、reward model |
| training | unsloth | 2-5x 加速 LoRA/QLoRA 微调，省显存 |
| inference | llama-cpp | llama.cpp 本地 GGUF 推理 + HF 模型发现 |
| inference | obliteratus | abliterate LLM 拒绝（diff-in-means） |
| inference | outlines | 结构化 JSON/regex/Pydantic LLM 生成 |
| inference | serving-llms-vllm | vLLM 高吞吐推理、OpenAI API、量化 |
| evaluation | evaluating-llms-harness | lm-eval-harness：MMLU、GSM8K 等基准测试 |
| evaluation | weights-and-biases | W&B：实验日志、sweep、模型注册 |
| models | audiocraft-audio-generation | AudioCraft：MusicGen 文生音乐、AudioGen 文生音效 |
| models | segment-anything-model | SAM：零样本图像分割 |
| research | dspy | DSPy：声明式 LM 程序、自动提示优化 |
| vector-databases | *(子目录)* | 向量相似度搜索与嵌入数据库 |

| Skill | 说明 |
|-------|------|
| huggingface-hub | `hf` CLI：搜索/下载/上传模型和数据集 |

## note-taking

笔记管理。

| Skill | 说明 |
|-------|------|
| obsidian | Obsidian vault 的文件系统操作：读、搜、创建、编辑 |

## productivity

办公与文档——创建、编辑、模板化。

| Skill | 说明 |
|-------|------|
| airtable | Airtable REST API（curl，无需 SDK） |
| box | Box 云文件系统操作 |
| career-research | 中国公司职位搜索（官网直链） |
| document-to-action-items | 文档义务/截止日期/任务提取 |
| docx | Word .docx 创建、读取、编辑、模板 |
| google-workspace | Gmail、Calendar、Drive、Docs、Sheets（gws CLI） |
| linear | Linear issue/project/team 管理（GraphQL + curl） |
| maps | 地理编码、POI、路线、时区（OSM/OSRM） |
| meeting-action-items | 会议记录转决策、负责人、工单 |
| nano-pdf | 自然语言编辑 PDF 文本 |
| notion | Notion API + ntn CLI：页面、数据库、Markdown |
| ocr-and-documents | PDF/扫描件/图片文字提取（pymupdf、marker-pdf） |
| pdf | PDF 创建、读取、合并、表单、加密 |
| petdex | 安装和选择动画宠物吉祥物 |
| powerpoint | .pptx 创建、读取、编辑、模板 |
| presentation-qa | 演示文稿质量审查（程序化检查） |
| product-price-monitor | 产品/航班/商品价格监控与提醒 |
| resume-building | 简历创建/改进（结合现有简历+补充材料） |
| resume-writing | 技术简历编写、面试官视角审阅 |
| session-librarian | 会话管理：查找、重命名、归档 |
| teams-meeting-pipeline | Teams 会议摘要、转录、Graph 订阅 |
| trip-planning | 旅行行程规划（Obsidian 存储） |
| vision-ocr-fallback | 视觉模型 OCR 兜底（扫描件） |
| weekly-review-planning | 每周复盘：承诺、停滞工作、下周计划 |
| xlsx | Excel .xlsx 工作簿操作（openpyxl） |

## red-teaming

LLM 红队测试。

| Skill | 说明 |
|-------|------|
| godmode | 绕过 API LLM 安全过滤（Parseltongue、GODMODE） |

## research

学术研究与论文。

| Skill | 说明 |
|-------|------|
| academic-paper-translation | 学术 PDF 翻译为中文 Markdown（Obsidian 存储） |
| arxiv | arXiv 论文搜索（免费 REST API） |
| bioinformatics-wiki | Obsidian 组学 wiki 页面（ATAC-seq、RNA-seq 等） |
| blocked-page-recovery | 被封锁/付费墙页面的恢复策略 |
| blogwatcher | 博客和 RSS/Atom 订阅更新追踪 |
| competitor-news-monitor | 公司动态监控（仅重要新闻） |
| grounded-citations | 基于引用的事实陈述（可溯源） |
| llm-wiki | Karpathy 风格 LLM 知识库（互链 Markdown） |
| polymarket | Polymarket 预测市场数据查询 |
| research-paper-writing | 端到端论文写作流程（NeurIPS/ICML/ICLR/ACL/AAAI） |

## single-cell-annotation-guide

单细胞注释指南——从聚类到细胞类型鉴定的完整流程。

## smart-home

智能家居。

| Skill | 说明 |
|-------|------|
| openhue | Philips Hue 灯光、场景、房间控制（OpenHue CLI） |

## snakemake-config-modification

Snakemake 管道配置修改——硬编码值替换为配置驱动，附基因组稳定性分析流程参考。

## social-media

社交媒体。

| Skill | 说明 |
|-------|------|
| xurl | X/Twitter 操作：搜索、发帖、DM、媒体（xurl CLI） |

## software-development

软件开发全流程——从计划到调试到重构。

| Skill | 说明 |
|-------|------|
| ai-agent-skill-architecture | AI agent 工具自描述架构设计 |
| blog-project | Spring Boot + Vue3 + Docker + MinIO 博客系统 |
| code-review | 代码审查工作流（提交前验证） |
| codebase-management | 代码库检查、分析、重构（LOC、语言分布） |
| codebase-refactoring | Python 项目重构工作流 |
| debugging | 调试方法论（系统化根因分析） |
| debugging-hermes-tui-commands | Hermes TUI 斜杠命令调试 |
| development-runtime-orchestration | 本地调试时 Docker 托管基础设施 |
| docker-container-host-access | 容器内访问宿主机文件系统 |
| docker-vite-frontend-debugging | Docker 中 Vite 前端白屏排查 |
| dogfood | Web 应用探索性 QA 测试 |
| full-stack-model-migration | 全栈数据模型变更（Spring Boot + MyBatis + Vue） |
| full-stack-project-scaffolding | 全栈项目脚手架（参考代码库分析） |
| hermes-agent-skill-authoring | SKILL.md 编写规范（frontmatter + 结构） |
| inspecting-hermes-desktop-dom | Hermes Desktop DOM/CSS 检查（CDP） |
| node-inspect-debugger | Node.js --inspect + Chrome DevTools 调试 |
| plan | 写 Markdown 计划到 .hermes/plans/（不执行） |
| python-debugpy | Python 调试：pdb REPL + debugpy 远程 DAP |
| requesting-code-review | 提交前自动验证流水线 |
| safe-file-editing | Hermes 工具安全文件编辑 |
| simplify-code | 并行 4 agent 代码清理 |
| spike | 抛弃实验：可行性验证 |
| spring-vue-admin-crud-alignment | Spring/Vue 后台 CRUD 接口对齐 |
| spring-vue-fullstack-patterns | Spring Boot + Vue3 全栈模式与陷阱 |
| subagent-driven-development | 子 agent 驱动开发（2 阶段审查） |
| systematic-debugging | 4 阶段根因调试 |
| test-driven-development | TDD：RED-GREEN-REFACTOR |
| vue3-deployment | Vue3 多项目部署（Docker、favicon、资源） |
| vue3-element-plus-integration | Element Plus 集成（CSS、upload auth、dialog） |
| vue3-frontend-debugging | Vue3 组件交互 bug 诊断 |
| writing-plans | 实现计划编写（零上下文假设） |

## standalone

不属于任何子目录的独立 skill。

| Skill | 说明 |
|-------|------|
| computer-use | 桌面后台自动化 |
| dogfood | Web 应用探索性 QA |
| linux-hardware-troubleshooting | Linux 硬件诊断（音频、WiFi） |
| matplotlib-significance-brackets | matplotlib 显著性标注 |
| meta-tsv-filling | 从 run.tsv 和 fastq 路径生成 meta.tsv |
| single-cell-annotation-guide | 单细胞注释指南 |
| snakemake-config-modification | Snakemake 配置修改 |

## yuanbao

元宝（腾讯）群交互——@提及用户、查询群信息/成员。
