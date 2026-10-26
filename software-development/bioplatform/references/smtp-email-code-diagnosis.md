# SMTP 邮件验证码诊断（验证码发送失败: Authentication failed）

案例：2026-10-05，前端返回 `{"code":500,"message":"验证码发送失败: Authentication failed"}`。
**最终根因：控制台重置 SMTP 密码的生效延迟（约 10 分钟）**——不是密码值不匹配、
不是域名未验证、不是代码问题；修复全程未改 `.env`、未重建容器。

## 配置拓扑

- `application-prod.yml`（打进 jar，服务器上 `unzip -p /app/app.jar BOOT-INF/classes/application-prod.yml` 可查）：
  - host `smtpdm.aliyun.com`（阿里云 DirectMail），port 465 SSL，`mail.smtp.auth=true`
  - **username 硬编码** `bio@mail.shiganluo.top` → 换发信地址必须改配置并重建镜像
  - password `${SMTP_PASSWORD:}` ← 环境变量
- `SMTP_PASSWORD` 三级：本地 `.env`、服务器 `.env`（compose 工作目录 =
  `docker inspect <c> --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'`）、
  容器 env（`docker exec ... printenv`）。一致性用 sha256 对比，**永不打印明文**。
- 案例中三级从头到尾一致，博客 `blog@mail.shiganluo.top` 用的还是**同一个密码值**
  （从 blog 项目的 `application-prod.yml` 提取比对 sha 得知）→ 现成的对照组。

## 探针

一键：`scripts/smtp-probe.sh`（三组差分 + blog@ 对照组，服务器端跑，不回显密码）。核心逻辑：

```python
import smtplib, subprocess
pw = subprocess.check_output(["docker","exec","bioplatform-backend","printenv","SMTP_PASSWORD"]).strip().decode()
def t(u, p, label):
    try:
        s = smtplib.SMTP_SSL("smtpdm.aliyun.com", 465, timeout=15); s.login(u, p)
        print(label, "-> LOGIN_OK"); s.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(label, "->", e.smtp_code, e.smtp_error)
    except Exception as e:
        print(label, "->", repr(e))
VALID = "bio@mail.shiganluo.top"
t(VALID, pw, "real+real")
t(VALID, "WrongPass123!", "real+WRONG")
t("nonexistent-xyz123@mail.shiganluo.top", pw, "FAKE+real")
t("blog@mail.shiganluo.top", pw, "CTRL(blog)+same-pw")   # 同域已知可用对照组
```

## 判读（案例实测矩阵）

| 时机 | real+real | real+WRONG | FAKE+real | CTRL(blog)+同密码 | 结论 |
|---|---|---|---|---|---|
| 控制台创建发信地址**前** | 535 `@ud010301` | 535 `@ud010301` | 535 `@ud010301` | – | 三组全同 → 地址在 DirectMail 不存在 |
| 新建 bio@ 地址**后** | 535 `@ud010201` | 535 `@ud010201` | 535 `@ud010301` | – | 真地址码变、假不变 → 地址存在；**错密码同码 → 标签与密码对错无关**，只反映地址状态 |
| 重置密码后 3-4 分钟内 | 535 `@ud010201` | – | – | – | 传播延迟窗口：此窗口内任何失败**无结论价值** |
| ~10 分钟后 | **LOGIN_OK** | – | – | **LOGIN_OK** | 重置生效；两地址同密码都能登 → 密码值本就正确 |

- **没有对照组就无法解读 DirectMail 的 535**：它故意不区分失败原因；
  错误码标签**变化本身**是状态变化的证据（假地址是控制变量），
  但标签**不能**解读成"密码不对"——案例中错密码也返回 `ud010201`。
- TLS/EHLO 正常（EHLO 返回 250）即排除网络、证书、端口问题。
- 对照组（同域可用地址）LOGIN_OK 而目标地址被拒 → 账号、域名、网络、密码值
  全部排除，只剩目标地址自身状态；配合传播延迟再复测即可定案。

## 日志判读（重要修正）

- Jakarta Mail 的 `INFO jakarta.mail - Jakarta Mail version 2.1.3 ...` 会话初始化
  **每个 JVM 只打一次**（首次发信）。之后的重试无论到没到后端都不会新增计数——
  **不能**用 `grep -c 'Jakarta Mail version'` 判断"重试是否到达"。
- 判断请求是否到达后端，用 nginx 访问日志：
  `ssh aliyun 'docker logs nginx-proxy --since 30m 2>&1 | grep sendEmailCode'`
  （案例：nginx 显示 15:20 / 15:21 / 15:49 三次 POST 均达后端、均返回 69 字节错误 JSON，
  而后端日志毫无痕迹——EmailCodeService catch 后不打堆栈，只把 message 塞进 HTTP 响应）。
- 并行噪音 `WorkerRegistry 计算节点健康检查失败 ... host.docker.internal:18081`
  与邮件无关，直接忽略。

## DNS 旁证的教训（曾引向错误假设）

- `dig +short TXT shiganluo.top` 案例中为空；`dig +short TXT mail.shiganluo.top`
  只有 SPF `v=spf1 include:spf1.dm.aliyun.com -all`。
- 据此曾推断"域名未验证 → 地址未开通"，**被用户反例当场推翻**：
  "不可能，博客发信地址 blog@mail.shiganluo.top 都是可用的"（同域名）。
- 教训：**不要用 DNS 反推 DirectMail 的域名/地址验证状态**（验证记录可能已删除、
  或记录形式与猜测不符）；同域存在可用发信地址时，直接把它当对照组实测。

## 案例时间线（完整）

1. 首次报错 → 后端日志只有 jakarta 初始化（14:55，JVM 首拍），无异常堆栈。
2. 三级 sha 比对一致 → 排除"密码传丢/容器没重建"。
3. 服务器直连差分：EHLO 250、AUTH 535 → 定性阿里云侧拒绝，排除代码/TLS/网络。
4. 用户新建发信地址 → 真地址错误码 `ud010301`→`ud010201`（地址已存在）。
5. 用户重置密码 = 系统存的值（sha 相同）→ 3-4 分钟内复测仍全拒；
   期间错误假设（域名未验证）被用户反例推翻。
6. 对照组 blog@ 同密码 LOGIN_OK → 与 bio@ 同时刻 LOGIN_OK（重置已生效）。
7. 端到端收尾：`curl -s --noproxy '*' -X POST https://bio.shiganluo.top/api/front/auth/sendEmailCode
   -H 'Content-Type: application/json' -d '{"email":"..."}'` → `{"code":200,"message":"操作成功"}`。
