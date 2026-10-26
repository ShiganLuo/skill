# 系统监控 / 操作日志 诊断与设计（2026-10，已实施）

用户反馈：「操作日志一堆不完善消息根本看不出什么」「不能监控到底谁登陆了系统、执行了任务」。
以下根因均对照源码核实；2026-10-06 已按本方案落地（迁移已在生产库执行），
**以代码为准**，本文件记录设计意图与坑。计划文档：`.hermes/plans/2026-10-06_144327-system-monitor-audit-logs.md`。

## 根因（四条，按症状顺序）

1. **前后端字段完全错位**（"看不出什么"的直接原因）
   - `bioplatform-admin/src/views/monitor/LogView.vue` 取 `level/username/action/module/message/createTime`
   - `AdminLogController`（`/api/admin/logs/list`）返回 `id/userId/operation/method/params/result/ip/createdAt`
   - → 除 ID、IP 外整列全空。写监控/列表页前必须从 controller 返回 + entity + resultMap
     反推列定义，不要凭页面字段名假设接口形状。
2. **日志内容质量差**
   - 原 `config/OperLogAspect.java` 存全限定类名（`com.bioplatform...XxxController.yyy`）；
     params 是整个 `getArgs()` 数组 JSON 截断 2000 字符；result 是响应 JSON 截断 2000 字符，看不出成败。
   - **明文密码入库**：`AdminUserCreateRequest.password` / 重置密码请求会被切面原样序列化进
     `operation_logs.params`。切面必须序列化后递归 mask（key 含 password/token/secret/
     authorization/apiKey/credential），并跳过 MultipartFile/ServletRequest/BindingResult。
   - 注解 `@OperLog(module=...)` 的 module 没有落库；只存 userId 不存用户名。
3. **登录/登出/注册零记录**，且登录发生在 JWT 过滤器建立 `LoginUserHolder` 之前
   → 给 login 加注解也拿不到"谁"。必须在 `UserServiceImpl.login()`（admin/front 共用入口）
   显式写审计：成功 + 失败原因（用户不存在/密码错误/账号禁用），失败记录是安全价值最高的一条。
   IP/路径从 `RequestContextHolder` 取（service 与 controller 同线程）。
4. **`operation_logs.user_id` 有外键**，而 `UserServiceImpl.deleteUser()` 只清 `user_roles`
   → 删任何留过日志的用户直接外键报错。审计表去掉 FK、保留索引，加 `username` 快照列。

## 已实施形态（与代码一致）

- 表列：`user_id / username(快照) / operation / module / method(POST /api/... URI 形式) /
  params(脱敏 JSON) / result(code+message 或异常摘要) / status(SUCCESS|FAIL) / ip / created_at`，
  索引 `idx_ol_user / idx_ol_username / idx_ol_operation / idx_ol_status / idx_ol_created`，
  **无外键**（注意：没有独立 error_msg 列，失败原因放 `result`）。
- 切面 `OperLogAspect`：落 module/username（holder 空则按 userId 查库兜底）/URI 形式 method；
  失败判定 = 抛异常，或正常返回但 `ApiResponse.code != 200`；序列化经 Jackson JsonNode 递归脱敏。
- 登录审计：`UserServiceImpl.login()` 成功+失败各写一条（`auditAuth()` 私有方法，
  module=`认证`，params=`用户名=xxx`，绝不落密码）；注册成功在 `register()` 写；
  登出在 `AdminAuthController.logout` / `FrontAuthController.logout` 显式写；
  `AdminAuthController.resetPassword`（无需登录的高危口）挂了 `@OperLog(module=认证)`。
- `AdminWorkerController`（增删改/启停节点）、`AdminFeedbackController.closeSession` 补了 `@OperLog`；
  `AdminRoleController` 是纯只读，无需日志。
- 查询：`AdminLogController.list` 支持 `username/module/status/operation/keyword/startDate/endDate/userId`；
  条件统一在 `OperationLogMapper.xml` 的 `<sql id="Filter_Conditions">`（`selectAll`/`selectWithFilter` 共用）。
  `endDate` 用 `< DATE_ADD(#{endDate}, INTERVAL 1 DAY)` 含当天。
- 前端 `LogView.vue` 列：时间/用户名/模块/操作/状态/IP/接口/结果 + 详情抽屉（params 美化 JSON）；
  快捷按钮「只看失败」「登录日志」= 置 `status=FAIL` / `module=认证`。
  `systemApi.ts` 导出 `LogQuery` / `OperationLogItem` 类型。
- `common/util/RequestContextUtil.getEndpoint()/getClientIp()` 是取 IP/路径的唯一实现。
- 写入口只有两个：切面 `OperLogService.save`（注解触发）、
  `OperationLogService.record(...)`（登录类显式调用，内部 catch 不影响业务）。没有第三个。

## 迁移（已在生产执行，2026-10-06）

- 原迁移文件 `database/migration_20261006_operation_logs.sql`（加三列 + DROP FK + 两索引 + 回填）
  **已在生产执行完毕并于 2026-10-07 删除**：compose 挂载整个 `database/` 目录进 initdb.d，
  留着它会让全新本地初始化重复执行而失败（实测 exit 1）。`database/bioplatform.sql` 已同步新表结构。
- 执行结果：`SHOW CREATE TABLE` 确认新列/新索引存在、无 `fk_ol_user`；254 条历史日志
  回填 username 254/254（回填前后各 `SELECT COUNT(*)` 留底）。
- 复用命令（密码不进命令行，SSH 噪声走 stderr 不污染 stdin）：
  ```
  ssh aliyun 'PW=$(docker exec blog_mysql printenv MYSQL_ROOT_PASSWORD); \
    docker exec -i -e MYSQL_PWD="$PW" blog_mysql mysql --default-character-set=utf8mb4 bioplatform' \
    < /tmp/migration_xxx.sql
  ```
- 以后再改这张表：更新 `database/bioplatform.sql`（保持最终形态），对存量库另写**一次性** ALTER 脚本
  （放 `/tmp` 或执行后即删，不要留在 `database/`），先 `SELECT COUNT(*)` 留底，执行后 `SHOW CREATE TABLE` 核对。

## 验证标准（用户强制：编译通过 ≠ 修好）

端到端逐条实测，全部通过才算完成：
登录成功一次 + 故意输错密码一次（两条 `module=认证` 记录，失败为 FAIL 并带原因）、
创建含密码的记录（params 显示 `***`）、执行流水线（日志显示执行人用户名）、
删除测试用户（不再外键报错）、监控页每一列都有值、详情抽屉能展开参数。
部署后浏览器实测走域名 `bioadmin.shiganluo.top`，不靠 curl。

### 无管理员账号时的替代探针（2026-10-06 实测可用）

浏览器 harness 不可用/没有账号时，这两个**无需登录**的真实 HTTP 探针能证明写入链路，
都走域名路径（`curl --noproxy '*'`），随后按 id 水位 `SELECT ... WHERE id > 上次值` 核对：

1. **登录失败审计**：`POST /api/admin/auth/login`
   body `{"username":"不存在的用户名","password":"x"}` → 期望库里
   `module=认证 / operation=登录失败 / status=FAIL / method=POST /api/admin/auth/login / result=用户不存在`。
   用**不存在的用户名**而不是错密码：不碰 `login_attempts`，不会把真实账号锁了。
2. **参数脱敏**：`POST /api/admin/auth/resetPassword`（本来就无需登录）
   body `{"email":"x@x","code":"000000","newPassword":"Secret123"}`
   → 期望 `params=[{"email":"x@x","code":"000000","newPassword":"***"}]`、`status=FAIL`。

局限要如实说：探针只证明后端写入与字段，**页面列渲染仍需浏览器看一眼**——
本次根因恰恰是"列名与接口字段错位"，只查 DB 会漏掉那一类问题。
