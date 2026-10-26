# LLM 提供商 / API Key 401 诊断案例

## 案例：MiniMax 获取模型失败（2026-10-02 已修复）

管理页切换到 MiniMax 点"获取模型"报 `获取模型列表失败: 401`。

根因：全局一把 `llm_api_key`（MiMo 的 key `tp-***dso9`），
切换提供商只换 baseUrl 不换 key → 拿 MiMo key 请求 MiniMax → 401。
加上 `fetchModels` 对 ENC: 值也丢弃改读 DB → 新填 key 不保存就无效。

额外发现：存的 MiMo key 对自家网关也 401（key 已失效），AI 对话同时挂。

### 诊断证据链

1. `curl --noproxy '*' https://api.minimax.io/v1/models`（无 key）→ 401 JSON，0.5s = 链路通。
2. `system_configs`：`llm_provider=mimo`，`llm_api_key` 解密后 mask=`tp-***dso9`（51 位）。
3. 同一把 key：MiniMax → 401 `authorized_error`；MiMo → 401 `Invalid API Key`。
4. `LLMClient` 日志：连续 3 次 401 → 对话功能同坏。

### 修复方案（已部署）

1. **每提供商独立 key**：`llm_api_key_<provider>` 配置项，`getActiveLlmApiKey()` 按当前 `llm_provider` 解析，回退全局。
2. **fetch-models 免保存**：ENC: 值直接解密使用；遮蔽值按 provider 取已存 key。
3. **对话侧同步**：AgentServiceImpl + LLMClient 统一走 `getActiveLlmApiKey()`。
4. **前端切换即换 key**：`llmProviderKeys` 暂存每提供商 key，切到 MiniMax 自动显示 MiniMax 的 key（无则清空）。
5. **DB 迁移**：旧全局 key 归档到 `llm_api_key_mimo`；`llm_provider_zhipu` 坏 JSON 修复。

## 案例：crypto.ts 密钥占位符导致解密失败（2026-10-02 已修复）

前端 `crypto.ts` 的 `SECRET_KEY` 是占位符 `REDACTED_AES_KEY`（16字节），
后端 `BIOPLATFORM_AES_KEY` 是 `bioplatform-aes-key-2024-default-32b`（34字节，取前32）。
前端 `encrypt()` 产出的 `ENC:` 密文后端解不开 → "API Key 解密失败"。

根因：crypto.ts 的密钥从未与后端同步。工具输出会把 SECRET_KEY 脱敏显示为
`REDACTED_AES_KEY`，难以从显示判断是占位符还是真实值被脱敏。
用 `python ord()` 字节确认：`REDACTED_AES_KEY` 的 ord 序列是 `[82,69,68,65,67,84,...]`，
与后端密钥完全不同。

修复：crypto.ts 密钥改为与后端 `BIOPLATFORM_AES_KEY` 一致。

## 案例：MiniMax base URL 用错（2026-10-02 已修复）

`llm_provider_minimax` 的 baseUrl 存的是 `https://api.minimax.io/v1`（国际端点），
实际中国可用端点是 `https://api.minimax.cn/v1`。用错 URL 返回 401 "invalid api key (2049)"。

## 判读规则（两次实测缺一不可）

| 目标端点 | key 自家端点 | 定性 |
|---|---|---|
| 401 | 401 | key 本身失效（换 key） |
| 401 | 200 | key 用错家（没切提供商 / 没保存） |
| 200 但列表空 | — | 响应结构不匹配 |
| 超时/连接错 | — | 网络问题 |

## 相关但不同：chatStream "服务不可用"

如果 AI 助手报"服务不可用"但管理页配置正常、LLM key 有效，可能是 token 过期。
`chatStream()` 用原生 `fetch()` 发 SSE，不走 axios 拦截器的自动刷新。
access_token 过期（默认1小时）后，fetch 收到 HTTP 401 → 显示"服务不可用"。
刷新页面会重新登录获取新 token，或等 `chatStream` 内置的 `tryRefreshToken()` 生效。
诊断：检查浏览器 Network 面板，`/api/admin/agent/chat/stream` 返回 401 = token 过期。

## 安全约定

- 解密后的 key 永不打印、不写文件；只输出 mask（前3+`***`+后4）和长度。
- 诊断脚本通过 stdin 管道送远端执行，不落盘到服务器。
- **永远不传明文 API key**：即使走 HTTPS，前端也必须 encrypt() 后再传输。
  获取模型对新输入的 key 同样要加密，后端解密后直接用。如果解密失败，修密钥——
  不能因为解密失败就去掉加密。用户原话："需要加密"、"你传明文,泄漏了怎么办"。

## 关键代码位置

- `AdminSystemController.fetchModels`：`bioplatform-springboot/.../controller/admin/`
- `SystemServiceImpl.getActiveLlmApiKey()`：`bioplatform-springboot/.../service/impl/`
- `LLMClient.loadConfig()`：`bioplatform-springboot/.../agent/`
- `ConfigView.vue` handleFetchModels / handleProviderChange：`bioplatform-vue3/bioplatform-admin/src/views/system/config/`