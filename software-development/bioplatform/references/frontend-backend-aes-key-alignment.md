# 前后端 AES 密钥对齐

## 问题

前端 `crypto.ts` 的 `SECRET_KEY` 和后端 `AesEncryptUtil` 的密钥必须一致，
否则前端 `encrypt()` 产出的 `ENC:...` 密文后端无法解密。

表现：管理页"获取模型"返回 `{"code":400,"message":"API Key 解密失败，请重新输入"}`。

## 密钥来源

| 端   | 位置                                         | 变量                         |
|------|----------------------------------------------|------------------------------|
| 后端 | 环境变量 `BIOPLATFORM_AES_KEY`（docker-compose-remote.yml） | `bioplatform-aes-key-2024-default-32b` |
| 前端 | `bioplatform-admin/src/utils/crypto.ts` 第9行 | `const SECRET_KEY = '...'`   |

两者都取前32字节（AES-256），`AesEncryptUtil.getKeyBytes()` 和 `getKeyBytes()` 各自截断。

## 注意事项

1. 工具输出会把 `SECRET_KEY = 'bioplatform...'` 脱敏显示为 `REDACTED_AES_KEY`，
   不要以显示值为准，用 `python ord()` 字节确认。
2. 部署时如果修改了后端 AES key 环境变量，前端 `crypto.ts` 也必须同步修改并重新构建 admin 镜像。
3. `llm_api_key`（全局）和 `llm_api_key_<provider>`（每提供商）都走这条加密链路。
4. `handleFetchModels` 前端对新输入的 key 也走 `encrypt()` → 后端解密后直接用于 API 调用（不存库）。
5. **绝不能因为解密失败就去掉加密**：如果前后端密钥不一致导致解密失败，修密钥——
   不能改成传明文。用户原话："需要加密"、"你传明文,泄漏了怎么办"。

## 加密格式

`ENC:` + Base64(iv[12] + ciphertext + tag[16])，iv 随机生成，AES-256-GCM 128-bit tag。
与 `AesEncryptUtil.encrypt/decrypt` 完全对齐。`decrypt` 对非 `ENC:` 开头的值原样返回
（历史明文配置兼容）。

## 全链路收发点（2026-10-07 对源码核实）

加密点（明文只在浏览器内存里）：
- `ConfigView.vue:355` 保存配置：key 含 `api_key` 且非 `ENC:` → `await encrypt()` 再 updateConfig
- `ConfigView.vue:444` 获取模型：新输入 key（不含 `***`）→ `encrypt()` 后进请求 body

存储（`SystemServiceImpl.updateConfig`，敏感 key = 含 key/secret/password/token）三分支：
1. 解密后含 `***`（前端回传遮蔽值 = 用户没改）→ 跳过不写库
2. 已是 `ENC:` → 原样入库
3. 明文（老路径兜底）→ 服务端 `encrypt()` 后入库
→ `system_configs` 里敏感项存的都是 `ENC:` 密文。

解密点（用的时候才解）：`getConfigValue()`（业务读）、`LLMClient:100`（调 LLM 时）、
`AdminSystemController.fetchModels`（遮蔽值→取库存 key；`ENC:`→解密直用；明文→直用）。
回显点：`getAllConfigs()` 敏感项只给 `AesEncryptUtil.mask()`（前3+`***`+后4）。

## 后端兜底默认键曾被写坏（2026-10-07 已修）

`AesEncryptUtil.getSecretKey()` 在 env `BIOPLATFORM_AES_KEY` 缺失时走的字面量默认值，
曾真实损坏为字面量 `"REDACTED_AES_KEY"`（16 字符，ord 82,69,68,65,67,84，不是显示脱敏）——
早期 patch 工具把密钥字面量改写后留下的。症状：任何没带该 env 的部署，后端密钥 ≠ 前端密钥，
所有 `ENC:` 解密失败（本地开发跑后端就是这种）。已改为与前端同值。
**教训：密钥字面量永远不要打进工具参数**（会被脱敏改写成 `REDACTED_AES_KEY` 一类垃圾），
正确姿势 = 用脚本从 source-of-truth 文件（`crypto.ts`）正则读出值再写入，
写完程序化比对 `java_literal == ts_key` 确认，不看回显。

## 互操作验证配方（2026-10-07 实测可用）

改密钥/格式后的端到端验证，三步，全部本地跑：

1. 编译：`mvn -q -DskipTests compile`。**别信 `| tail` 后的退出码**（管道掩盖），
   改查产物存在性 `ls target/classes/com/bioplatform/common/util/AesEncryptUtil.class`。
2. node 侧：小脚本正则读 `crypto.ts` 的 `SECRET_KEY`，用 WebCrypto 复刻
   `encrypt/decrypt`（AES-GCM, iv12, tag128, `ENC:`+Base64(iv||ct||tag)）。
3. Java 侧：`javac -cp target/classes` 编一个接收 `dec|enc` 的小类，
   跑时 `env -u BIOPLATFORM_AES_KEY` **强制走兜底路径**，两个方向各测一次：
   node 加密→Java 解、Java 加密→node 解。

判定铁律：**比较必须在进程内做**（Java 打 `MATCH=true`、node 打布尔），
绝不看回显文本——工具输出会把 `sk-` 串截成 `sk-tes...3456`，
连 `len(out)` 都是回显后的长度，看回显必然误判（本案例一度以为解密值不对）。
负向测试：改密文末尾 4 字符 → 解密应失败退出码非 0，证明 GCM tag 校验生效。