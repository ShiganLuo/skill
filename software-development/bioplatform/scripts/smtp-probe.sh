#!/usr/bin/env bash
# SMTP 发信地址差分探针：三组差分 + 同域对照组，服务器端执行，不回显任何密码。
# 用法: bash scripts/smtp-probe.sh    （依赖: 本地 ssh config 里的 aliyun 主机别名）
set -euo pipefail
ssh aliyun 'python3 - <<'"'"'EOF'"'"'
import smtplib, subprocess
pw = subprocess.check_output(
    ["docker", "exec", "bioplatform-backend", "printenv", "SMTP_PASSWORD"]
).strip().decode()

def t(u, p, label):
    try:
        s = smtplib.SMTP_SSL("smtpdm.aliyun.com", 465, timeout=15)
        s.login(u, p)
        print(label, "-> LOGIN_OK")
        s.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(label, "->", e.smtp_code, e.smtp_error)
    except Exception as e:
        print(label, "->", repr(e))

VALID = "bio@mail.shiganluo.top"      # application-prod.yml 硬编码的发信地址
CTRL  = "blog@mail.shiganluo.top"     # 同域已知可用对照组（博客项目）

t(VALID, pw, "real+real  ")
t(VALID, "WrongPass123!", "real+WRONG")
t("nonexistent-xyz123@mail.shiganluo.top", pw, "FAKE+real  ")
t(CTRL, pw, "CTRL(blog)  ")
EOF'
