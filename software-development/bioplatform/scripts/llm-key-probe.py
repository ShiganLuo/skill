#!/usr/bin/env python3
"""bioplatform LLM key probe: 按提供商解析 key，解密后实测各提供商 /models 端点。

只输出 mask 形态与 HTTP 状态，绝不打印明文 key。py3.6 兼容（远端服务器 python3=3.6）。

用法（在服务器上经 stdin 管道执行，脚本不落盘）：
  MYSQL_PW=<db密码> AES_KEY=<aes密钥> TARGET_BASES=https://a/v1,https://b/v1 \
    ssh -p <port> <user>@<host> 'MYSQL_PW=... AES_KEY=... TARGET_BASES=... python3 -' < llm-key-probe.py

判读：
  目标401 + 自家401 -> key 失效；目标401 + 自家200 -> key 用错家；200但data空 -> 结构不匹配。
"""
import os, sys, json, base64, subprocess, ssl, urllib.request, urllib.error

MYSQL_PW = os.environ.get("MYSQL_PW", "")
AES_KEY = os.environ.get("AES_KEY", "").encode("utf-8")[:32].ljust(32, b"\0")
DB_CONTAINER = os.environ.get("MYSQL_CONTAINER", "blog_mysql")
DB_NAME = os.environ.get("MYSQL_DB", "bioplatform")
# 逗号分隔的 baseUrl（可不带 /models）
TARGETS = [u.strip().rstrip("/") for u in os.environ.get("TARGET_BASES", "").split(",") if u.strip()]
KEY_OWN_BASE = os.environ.get("KEY_OWN_BASE", "")  # key 所属提供商 baseUrl，用于区分"失效 vs 用错家"


def mysql_scalar(sql):
    cmd = ["docker", "exec", "-i", DB_CONTAINER, "mysql", "-uroot", "-p" + MYSQL_PW,
           "--default-character-set=utf8mb4", DB_NAME, "-N", "-B", "-e", sql]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if p.returncode != 0:
        sys.stderr.write("MYSQL ERR: %s\n" % p.stderr.strip()[:300])
        sys.exit(1)
    return p.stdout.strip()


def decrypt(enc):
    if not enc.startswith("ENC:"):
        return enc  # 未加密存储的旧值
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    data = base64.b64decode(enc[4:])
    return AESGCM(AES_KEY).decrypt(data[:12], data[12:], None).decode("utf-8")


def mask(s):
    return s[:3] + "***" + s[-4:] if len(s) > 8 else "********"


def probe(url, key):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
            body = r.read().decode("utf-8", "replace")
            n = -1
            try:
                data = json.loads(body).get("data")
                if isinstance(data, list):
                    n = len(data)
            except ValueError:
                pass
            print("  [%s] -> %s (data items=%d)" % (url, r.status, n))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("  [%s] -> HTTP %s | %s" % (url, e.code, body[:200].replace("\n", " ")))
    except Exception as e:
        print("  [%s] -> EXC %s: %s" % (url, type(e).__name__, e))


def main():
    if not MYSQL_PW:
        sys.exit("need MYSQL_PW env")

    # 读取当前提供商
    provider = mysql_scalar(
        "SELECT config_value FROM system_configs WHERE config_key='llm_provider' LIMIT 1")
    print("llm_provider = %s" % provider)

    for k in ("llm_base_url", "llm_model"):
        print("%s = %s" % (k, mysql_scalar(
            "SELECT config_value FROM system_configs WHERE config_key='%s' LIMIT 1" % k)))

    # 按提供商解析 key：llm_api_key_<provider> -> 回退 llm_api_key
    key_source = "global"
    enc = None
    if provider and provider.strip() and provider.strip() != "custom":
        provider_key = "llm_api_key_%s" % provider.strip()
        enc = mysql_scalar(
            "SELECT config_value FROM system_configs WHERE config_key='%s' LIMIT 1" % provider_key)
        if enc:
            key_source = provider_key

    if not enc:
        enc = mysql_scalar(
            "SELECT config_value FROM system_configs WHERE config_key='llm_api_key' LIMIT 1")
        key_source = "llm_api_key (global fallback)"

    if not enc:
        sys.exit("no API key found in system_configs")

    try:
        plain = decrypt(enc)
        print("key source: %s, decrypt OK, mask=%s len=%d" % (key_source, mask(plain), len(plain)))
    except Exception as e:
        sys.exit("decrypt FAILED (AES_KEY 不匹配?): %s" % e)

    urls = list(TARGETS)
    if KEY_OWN_BASE:
        urls.append(KEY_OWN_BASE)
    if not urls:
        sys.exit("need TARGET_BASES or KEY_OWN_BASE")
    seen = set()
    for base in urls:
        url = base if base.endswith("/models") else base + "/models"
        if url in seen:
            continue
        seen.add(url)
        probe(url, plain)


if __name__ == "__main__":
    main()