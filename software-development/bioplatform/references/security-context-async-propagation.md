# SecurityContext 跨线程传播（2026-10-08 会话实证，源码级验证）

适用于：解释/修改 SSE async dispatch 鉴权、给自建异步线程加鉴权上下文、排查 async 线程 401。
所有结论均从本地 m2 的实际 jar 反编译核对过（Spring Security 6.4.2 / Boot 3.4.2），
不是凭文档记忆——改动前若版本变了，用文末配方重验。

## 两套机制各管一段

| 场景 | 机制 | 代码位置 |
|---|---|---|
| 容器对同一 request 的再次分发（ASYNC dispatch） | `RequestAttributeSecurityContextRepository` | `config/SecurityConfig.java:133-136` |
| 自建 `new Thread`（SSE 流式输出线程） | 手动 setContext/clearContext | `service/impl/AgentServiceImpl.java:209-264` |

原理一句话：SecurityContext 存 ThreadLocal（跟线程走），request attribute 挂在
HttpServletRequest 对象上（对象跨线程分发不变）。换线程重入时从 attribute 复制回新线程 ThreadLocal。

## 关键实证（容易讲错的三个点）

1. **`SecurityContextHolderFilter` 只读不写**。`.securityContext(sc -> sc.securityContextRepository(...))`
   注册的就是它：doFilter = loadDeferredContext → setDeferredContext(懒加载) → chain → finally
   clearContext + 摘掉自己的 `FILTER_APPLIED` 标记。它的 javadoc 明说 save 必须由认证机制显式调用。
   即：**这行配置本身不保存任何东西**。

2. **本项目里真正 saveContext 的是 `SessionManagementFilter`（框架源码 113 行）**，不是自定义的
   `JwtAuthenticationFilter`（它只 set 进 ThreadLocal，从不调 repository.save）。链路：
   JWT filter（位置在 UsernamePasswordAuthenticationFilter 之前）设好认证
   → 链条靠后的 SessionManagementFilter 判断 `!containsContext && isAuthenticated`
   → 调 `repository.saveContext(...)` 提前存入 request attribute（框架注释 SEC-1396：
   "eagerly save ... for any possible re-entrant requests"）。STATELESS 下其
   sessionAuthenticationStrategy 是空操作，不影响这条保存路径。
   **推论（改鉴权链时的坑）**：若把认证信息的写入挪到 SessionManagementFilter 之后的位置，
   或让 `containsContext` 提前为 true，attribute 就永远不会被写 → 配置静默失效，
   async 分发鉴权 401，且没有任何报错提示。

3. **ASYNC 分发时过滤器链会重跑，但 JWT filter 不会**：
   - Boot 3.4.2 默认 `SecurityProperties$Filter` 构造器 `EnumSet.allOf(DispatcherType.class)`
     → springSecurityFilterChain 覆盖 REQUEST/ASYNC/ERROR 全部分发类型；
   - `JwtAuthenticationFilter` 是 `OncePerRequestFilter`，默认 `shouldNotFilterAsyncDispatch()=true` → ASYNC 分发跳过（内部重入也不该再解析 token）；
   - `SecurityContextHolderFilter` 的 `FILTER_APPLIED` 在上一轮 finally 被 removeAttribute → 重跑 → 从 attribute 恢复到新线程。

## 属性名与边界

- attribute 常量：`RequestAttributeSecurityContextRepository.SPRING_SECURITY_CONTEXT`
  （= 类全限定名 + `.SPRING_SECURITY_CONTEXT`）。
- 只覆盖"同一 request 的再次分发"；**不覆盖自建线程**——`AgentServiceImpl` 流式线程从不经过
  过滤器链，必须手动 `SecurityHolder.setContext`（起线程前捕获、线程内注入、finally 清理）。
  心跳线程 `sse-heartbeat-*` 不注入（只发心跳不碰鉴权）。
- 下游依赖方：`common/util/OwnershipUtils.java:24` 等从 `SecurityContextHolder` 取当前用户做归属校验；
  context 丢 = 归属校验失败或鉴权 401。
- 排错表：`docs/tech/01-sse-streaming-chat.md`（仓库内文档，105 行起）。

## SSE 为什么会触发 ASYNC 分发（spring-webmvc 6.2.2 源码实证）

用户常卡在"不是新请求，为什么还要重入过滤链"——**过滤器的执行单位是 dispatch 不是 HTTP 请求**
（DispatcherType 就是为此设计的），且异步把一次处理拆成两段，第二段收尾必须重新进管线：

1. Controller 返回 SseEmitter → `ResponseBodyEmitterReturnValueHandler.handleReturnValue`：
   `new DeferredResult` + `webAsyncManager.startDeferredResultProcessing(...)`（启动异步）
   → 本轮 REQUEST 分发到此结束，线程归还容器，连接由 Tomcat 挂起保管。
   **第一圈过滤链在这一段跑完，身份验证发生在这一圈。**
2. `emitter.send()`：直接往 socket 写，**不经过过滤器、不触发分发**（业务线程上执行）。
3. `emitter.complete()` → `DefaultSseEmitterHandler.complete()` → `deferredResult.setResult(null)`
   → "async 已启动"状态下 setResult 触发 `asyncWebRequest.dispatch()` → Tomcat `AsyncContext.dispatch()`
   → dispatcherType=ASYNC 重入 → 过滤链跑第二圈（**授权过滤器此时要从 request attribute 读回身份**）
   → DispatcherServlet 交付 DeferredResult、跑拦截器 afterCompletion、`asyncContext.complete()` 关连接。
   `ResponseBodyEmitter.complete()` javadoc 原话："performing a dispatch into the servlet container,
   where Spring MVC is invoked once more"。
   超时、`send()` 抛 IOException 同样触发分发（ASYNC/ERROR），为让异常解析器收尾。
第二圈跑在容器线程上，ThreadLocal 是空的——request attribute 机制服务的就是这一圈。
没有"半路旁路"：容器进入 servlet 管线的唯一路径就是分发，过滤器挂在管线上。

## 身份消费点与两个已知缝隙（2026-10-08 排查，改动前必读）

- **消费点全在请求线程**：`FrontAgentController:67` LoginUserHolder gate（null → "请先登录"）、
  `userId` 以**普通参数**传入 `streamChat`（`:99`）。流线程内的活（插消息/调 LLM/
  `AgentToolExecutor.executeTool` → `Tool.execute`/推流）经全仓库 grep
  `OwnershipUtils\.|LoginUserHolder\.(get|is)|SecurityContextHolder` 确认**一处都不读身份**
  → `AgentServiceImpl:214` 的 setContext 当前无下游消费者，属防御性储备
  （将来工具要按用户过滤数据时才真正用上）。
- **缝隙1：LoginUserHolder 没跟着传播**。`OwnershipUtils` 是两条腿：`isAdmin()` 读
  SecurityContext（传播了、可用），`getCurrentUserId()` 读 LoginUserHolder（**新线程恒 null**）
  → 将来工具调 `checkOwnership`：admin 能过，普通用户因 `currentUserId == null` 被一律拒
  （`OwnershipUtils.java:49`）。给流线程加身份逻辑时，要么两个 ThreadLocal 都传播，
  要么显式传 userId 参数——不要假设"传播了 SecurityContext 就等于身份齐了"。
- **缝隙2：对话归属从未校验**。`streamChat` 拿 conversationId 直接 `selectById` 就插消息；
  `getMessages`（`FrontAgentController:127`）、`deleteConversation`(`:135`)/`batchDelete`
  只判"登录了没"，**不比对 `conversation.userId == 当前用户`** → 登录用户知道他人
  conversationId 即可读/删/灌消息。补校验按既有模式：Controller 只传 id，
  Service 层取当前用户比对（见 `docs/tech/08-rbac-permission.md` 的 Service 层归属原则）。

## 附：核验框架内部行为的配方（本会话验证可用）

jar 和 sources 都在本地 m2，不用上网：
```
ls ~/.m2/repository/org/springframework/security/spring-security-web/*/   # 找 -sources.jar
cd /tmp/x && unzip -oq ~/.m2/repository/.../spring-security-web-6.4.2-sources.jar   # 读源码最直接
JAVAP=/home/<USER>/.jenv/versions/17/bin/javap        # jenv shim 在 /tmp 等非项目目录会报 command not found，用绝对路径
$JAVAP -p -c -cp . <全限定类名>                       # 反编译验证调用点（无 sources 时）
grep -rn "saveContext(" org/springframework/security/web --include=*.java   # 反查谁在保存
```
注意：javap 在项目根目录下可用（jenv shim 按 .java-version 解析），换目录就失效 → 记绝对路径。
