# 分片上传 + spark-md5 秒传（2026-10-07 实施，已部署生产）

对应计划 `.hermes/plans/2026-10-07_211645-instant-upload-spark-md5.md`；
提交 `3880b3a`（功能）/ `60f8635`（本地配置修复）/ `3460612`（文档）。以代码为准。

## 设计要点

- **uploadId = 文件内容 MD5**（前端 spark-md5 2MB 分片流式算，进度状态 `hashing`），
  一个值三用：断点续传身份、秒传键、merge 完整性校验。替换了旧的
  `name+size+lastModified` 32 位字符串 hash（碰撞 + mtime 变即失效）。
- **秒传范围 = 同项目**（跨项目涉及复制/引用计数，YAGNI）：命中返回**既有** DataFile
  记录，不新建行、不复制文件；范围外/历史行（content_hash=NULL）不参与，正常上传不受影响。
- **合并完整性校验在服务端**：`ChunkUploadServiceImpl.mergeChunks` 用 1MB buffer
  边写边喂 `MessageDigest`（与合并同量级开销），合并后与前端声明比对，不符 →
  删除目标文件 + 抛 `IllegalStateException` → HTTP **422**，不入库；
  入库 `content_hash` 一律用**服务端实算值**，不信任前端。
- 老客户端不带 fileHash → 不校验但照常实算入库（兼容分支，JUnit 有用例覆盖）。
- 参数：10MB/片、3 并发、每片重试 3（1s×attempt 退避、单片 120s 超时）、>5MB 走分片。
- DB：`data_files.content_hash VARCHAR(32)` + 索引 `idx_df_hash`；
  `bioplatform.sql` 是唯一 schema 来源；**生产与本地库的 ALTER 都已手工执行**
  （一次性脚本按约定放 `/tmp`，执行完即删）。
- 前端文件：`utils/fileHash.ts`（calculateFileHash）、`utils/chunkUpload.ts`、
  `views/data/DataView.vue`（hashing 阶段显示「文件名（计算校验和…）」）。
- 单测：`src/test/.../ChunkUploadHashTest.java`（5 用例，仓库第一个测试）
  —— `mvn test -Dtest=ChunkUploadHashTest`。

## 接口契约

```
POST /api/admin/datafiles/upload-chunk    chunk, uploadId, chunkIndex, totalChunks, fileName
GET  /api/admin/datafiles/upload-status   → result.uploadedChunks: number[]
GET  /api/admin/datafiles/check-instant   fileHash, projectId → result: DataFile | null
POST /api/admin/datafiles/merge-chunks    uploadId, fileName, projectId, fileHash(可空)
                                          → 422 = 校验失败且文件已删
```

- **ApiResponse 载荷字段是 `result`，不是 `data`**：
  `{"code":200,"message":"操作成功","result":{...}}`。
  e2e 脚本第一版全用 `data` 取值 → 全链路 None/401 假失败，浪费一轮。
- login 响应 `result.accessToken`；admin 登录**无验证码**，仅 username+password。
- merge 成功返回的 `path` 是**容器相对路径**（`./uploads/<projectId>/<uuid>.bin`）。

## 本地 e2e 配方（2026-10-07 实测 10/10 PASS）

前置（一次性）：
1. `docker compose up -d mysql redis backend admin`（compose JWT 修复后 backend 才能起，
   admin 端口若被本机进程占用临时改映射）。
2. 本地 admin 密码直接设：python `bcrypt.hashpw` 生成 →
   `echo "UPDATE users SET password='<hash>' WHERE id=1;" | docker exec -i bioplatform-mysql sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -uroot bioplatform'`
3. 插测试项目：`INSERT INTO projects (name, owner_id) VALUES ('秒传测试项目', 1);`
4. 25MB 随机文件 + python hashlib 算 md5。

10 条断言（顺序即脚本流程）：
1. 登录拿 accessToken；2. check-instant 未命中；3. 只传第 0 片 → status=[0]（断点状态实证）；
4. 三片齐全；5. merge（正确 fileHash）→ contentHash==本地 md5；
6. 合并文件存在且 size 一致；7. `_chunks/<uid>` 已删；8. 二次 check-instant 命中同一 id（秒传）；
9. 错误 fileHash → code 422 且项目目录文件集合不变、不入库；
10. merge 后 upload-status 清空。

关键注意：
- **文件与分片落在容器内 `./uploads`（=/app/uploads）**，本地 compose 挂的是
  `/data/bioplatform/uploads`，宿主机看不到 → 核验必须 `docker exec bioplatform-backend`
  进容器 `stat`/`ls`；生产 compose 把命名卷挂在 `/app/uploads`，所以生产是一致的。
  根因：`ChunkUploadServiceImpl` 的 key 是 `bioplatform.upload.path`（默认 `./uploads`），
  任何 profile 都没显式定义它，靠进程 cwd 兜底。
- 接口全部要 JWT（即使 upload-status），断点状态本身是服务端目录扫描、与账号无关。

## 本次踩过的坑（已在代码/配置里修掉，记录防再犯）

- **本地 docker/dev profile 三处坏配置**（commit `60f8635`）：
  JWT fallback 字面量是 26 字节的 `REDACTED_*` 占位（工具历史写坏）→ jjwt
  `WeakKeyException:208 bits` 后端起不来；缺 `spring.mail` → EmailCodeService 的
  `@Value("${spring.mail.username}")` 注入失败；JDBC `characterEncoding=utf8mb4`
  不是合法 Java 字符集名 → `UnsupportedEncodingException`。三个都会让本地栈
  "换新 jar 后起不来"，且报错一个比一个深，逐层剥。
- uploadId 算法变更 → **进行中的旧格式中断上传需重传**（一次性成本，无数据损坏）。
- `docs/tech/03-chunk-upload.md` 曾长期描述**从未实现**的 spark-md5/秒传（文档先行、
  代码没跟上），本次已对齐；以后改上传先让文档与代码互查。
