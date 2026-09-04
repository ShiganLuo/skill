# Deployment Patterns for Spring Boot + Vue3 Projects

## File Structure (参考博客项目)

```
project-root/
├── bioplatform-springboot/Dockerfile     # 后端 Dockerfile（各子项目自己管理）
├── bioplatform-vue3/bioplatform-admin/Dockerfile  # 后台 Dockerfile
├── bioplatform-vue3/bioplatform-front/Dockerfile  # 前台 Dockerfile
├── docker-compose.yml                    # 本地编排
├── docker-deploy.sh                      # 本地部署脚本
├── nginx-proxy.conf                      # nginx 反代配置（根目录，不放 deploy/ 子目录）
├── remote_publish.sh                     # 远程部署脚本
└── database/bioplatform.sql              # 数据库初始化
```

**关键规则：不要创建 `deploy/` 子目录收纳 Dockerfile 和 nginx 配置。** 各子项目已有 Dockerfile，nginx-proxy 配置放根目录，与博客项目保持一致。

## remote_publish.sh 远程部署流程

参考博客项目 `remote_publish.sh`：
1. 本地 `mvn clean package -DskipTests`
2. `docker compose build`
3. `docker save` 所有镜像为一个 tar
4. `scp` tar + SQL + nginx 配置到服务器
5. 服务器 `docker load` → `docker run`

后端用环境变量覆盖数据库连接：
```bash
docker run -d --name bioplatform-backend \
    --network blog_net \
    -e SPRING_PROFILES_ACTIVE=prod \
    -e SPRING_DATASOURCE_URL='jdbc:mysql://blog_mysql:3306/bioplatform?...' \
    -e SPRING_DATASOURCE_USERNAME=root \
    -e SPRING_DATASOURCE_PASSWORD=xxx \
    bioplatform-backend
```

## 低内存服务器部署 (2G 以下)

- 停掉非必要服务释放内存后再部署
- MySQL OOM 风险：大 SQL 导入可能触发 OOM kill，只建必要表更安全
- 用 `--network blog_net` 加入已有网络，数据库通过容器名访问
- nginx-proxy 依赖所有上游容器运行（blog_web/blog_admin/blog_minio 等），停掉会导致 nginx-proxy 启动失败

## deploy.sh 脚本规范

- 直接用 PATH 中的 `java` 和 `mvn`，不要要求 JAVA_HOME
- 用户环境通常有 `java` 在 PATH 但没有 JAVA_HOME
- 服务器可能用 jenv 管理多版本

## Nginx 反代配置

与已有项目共用 nginx-proxy 容器：
- 新项目的 server block 追加到现有 `nginx-proxy.conf` 中
- 不要创建独立的 nginx 配置文件
- 前台/后台分别用独立 server_name（如 `bio.shiganluo.top` / `admin.bio.shiganluo.top`）
- API 和 WebSocket 代理在 nginx-proxy 层处理，容器内 nginx 只处理 Vue Router history 模式

## Spring Bean 命名冲突

- `TaskScheduler` 会和 Spring `@EnableScheduling` 自动创建的 `taskScheduler` bean 冲突
- 用具体业务名如 `PipelineTaskDispatcher` 避免冲突
- `@EnableAsync` + `@Scheduled` 的 bean 名不能和 Spring 内置 bean 同名

## Git 操作规范

- 删除文件用 `git rm`，不要用 `filter-branch` 重写历史
- `filter-branch` 会导致 force push，且会清理 untracked 文件
- 推送前确认所有改动已提交
