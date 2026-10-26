# Bioplatform 系统架构速查（2026-10 盘点，用于画图/改动前定位）

四模块：`bioplatform-springboot`(后端) + `bioplatform-vue3/{bioplatform-front,bioplatform-admin}`(双前端)
+ `bioplatform-worker`(独立计算节点) + `database/bioplatform.sql`(初始化)。

## 后端分层（com.bioplatform，Spring Boot 3.4.2 / Java 17）

- **安全层**：`filter/JwtAuthenticationFilter` + `config/SecurityConfig`
  （白名单：`/api/front/auth/*`、`/api/front/projects|pipelines/**`、`/api/front/site-config`、`/ws/**`、
  `/api/admin/auth/sendResetCode|resetPassword`，其余 authenticated）+ `config/OperLogAspect`(AOP 操作日志)。
- **Controller**（21 个）：
  - `controller/admin/` 15 个：auth, users, roles, projects, pipelines, executions, datafiles(+ChunkUpload),
    agent, system, logs, workers, templates, feedback, sample-meta —— 前缀 `/api/admin/**`
  - `controller/front/` 6 个：auth, projects, pipelines, agent(SSE 流式), feedback, config —— 前缀 `/api/front/**`
  - WebSocket：`websocket/FeedbackWebSocketHandler`（`/ws/feedback`）
- **Service**：`service/impl` 16 个。关键：`AgentServiceImpl`(SseEmitter 流式+持久化)、
  `PipelineExecutionServiceImpl`、`DataFileServiceImpl`(注入 StorageStrategy)、
  `SystemServiceImpl`(system_configs KV 读取+AES 解密)、`EmailCodeService`(验证码存 Redis)、
  `ChunkUploadServiceImpl`(分片上传 500MB)。
- **AI Agent**（`agent/`）：**线上实际链路** = Controller → `AgentServiceImpl.streamChat` →
  `processWithTools`：`SkillRegistry.buildSystemPrompt()`（6 代码 Skill + `system_configs` 的
  `skill:*` DB Skill + 全局规则 + 动态片段如数据库 schema）+ **全量工具** + 5 轮 tool-loop
  （SSE 断连即中断；轮次耗尽后强制一次无工具调用兜底出文本）+ SSE 事件
  (status/tool_call/tool_result/delta/done/error，15s keepalive 心跳)。
  **delta 不是真 token 流**：`LLMClient.chatWithTools` 一次性 HTTP 拿完整回复后按 20 字符切块模拟。
  非流式 `sendMessage` 走 `callLlmApi` 无工具。
  **`AgentOrchestrator`（正则意图路由：流水线→PipelineAgent、格式/质控→DataAnalysisAgent、
  兜底→QA；各 Agent 独立 system prompt + `getTools()` 工具白名单）与 `agents/` 三个 Agent
  已实现但无任何调用方**（2026-10-07 核实：全仓库搜 `processMessage(`/`orchestrator.` 只有定义，
  front/admin 两 Controller 只注入 AgentService）——问"多智能体编排"时如实说这是未接线的预留设计，
  要真多智能体应让 streamChat 走 detectAgent 选人格再进 tool-loop，而不是另起炉灶。
  `LLMClient`(OkHttp 调 OpenAI 兼容 `/chat/completions`，tool_calls 序列化/解析)；
  `tools/AgentToolExecutor` 6 工具 = ShellExecute(默认 chroot `/host` 宿主机执行，指定 worker_id
  转发 WorkerClient → `/worker/shell/execute`), DatabaseQuery, FileInfo, FormatInfo, PipelineSearch,
  CreateSkill(**写回 `system_configs` 的 `skill:<name>`，但 dbSkills 在构造器加载 → 重启才进提示词**)。
  对话持久化 `agent_conversations` / `agent_messages`。
- **Worker 调度**（`worker/`）：`PipelineTaskDispatcher`(提交→pollTaskStatus→输出→cancel)、
  `WorkerRegistry`(@Scheduled 30s 健康检查，写 `compute_nodes` 表)、`WorkerClient`、`HttpUtil`。
- **存储策略**（`storage/`）：`StorageStrategy` ← `SharedStorageStrategy` / `WorkerStorageStrategy`。
- **持久层**：MyBatis 3.0.4 + PageHelper；19 Mapper(+`resources/mapper/*.xml`)、19 entity。
- **公共层**：`dto/`(ApiResponse/PageResult)、`exception/`、`common/util/`(JWT、AES-GCM `ENC:`)。

## Worker 端 REST（bioplatform-worker，独立 Spring Boot）

`/worker/health`、`/worker/tasks/submit`、`/worker/tasks/{id}/status|output|cancel`、
`/worker/tasks`(列表)、`/worker/shell/execute`；另有 `WorkerStorageController`。

## 部署拓扑

- **本地** `docker-compose.yml`：mysql:3308 / redis:6380 / backend:8080 / admin:8081 / front:80，网 `bioplatform_net`。
- **生产** `docker-compose-remote.yml`：backend:8083→8080, front:3000, admin:3001，
  加入外部 `blog_net`，**共用 blog_mysql / blog_redis**。
- `nginx-proxy.conf`：`/` → front|admin 静态，`/api/` `/ws/` → `bioplatform-backend:8080`；
  两个前端容器内 nginx 也各自反代 `/api` `/ws` 到 `backend:8080`。
- 上传卷：本地宿主目录映射；远程 `bioplatform-uploads` → 容器 `/app/uploads`。

## 架构图

仓库根目录已有 `bioplatform-architecture.html`（architecture-diagram skill 产出的深色 SVG 图，
Chrome headless 截图验证过）。结构变化大时可按上表重新生成。