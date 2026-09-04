# Nginx-Proxy Upstream Dependency & SSL Wildcard Pitfalls

## nginx-proxy Fails When Upstream Containers Are Down

nginx-proxy reads ALL `proxy_pass` directives at startup. If ANY referenced upstream container (e.g., `blog_web`, `blog_minio`) is not running, nginx-proxy fails with:

```
[emerg] host not found in upstream "blog_web" in /etc/nginx/conf.d/nginx-proxy.conf:32
```

**This means stopping one project's containers can break nginx-proxy for ALL projects sharing the same config.**

When deploying bioplatform alongside blog, stopping blog containers (blog_web, blog_admin, blog_minio) caused nginx-proxy to fail, which took down bioplatform's HTTPS access too.

**Fix**: Before stopping containers shared with nginx-proxy, either:
1. Start all referenced containers first: `docker start blog_web blog_admin blog_backend blog_minio`
2. Or remove the stopped container's server blocks from nginx-proxy.conf before restarting nginx-proxy

**Diagnostic**: `docker logs --tail 5 nginx-proxy` shows which upstream is missing.

## Wildcard SSL Certificate Limitation

`*.shiganluo.top` wildcard certificate matches `blog.shiganluo.top` and `bio.shiganluo.top` but does **NOT** match `admin.bio.shiganluo.top` (second-level subdomain).

Symptom: `curl -v https://admin.bio.shiganluo.top/` shows `SSL: no alternative certificate subject name matches target host name`.

**Fix**: Use single-level subdomains only: `bioadmin.shiganluo.top` instead of `admin.bio.shiganluo.top`.

When planning domain names for a new project sharing an existing server's SSL cert, check the cert's SAN first:
```bash
echo | openssl s_client -connect domain:443 2>/dev/null | openssl x509 -noout -text | grep -A1 "Subject Alternative"
```

## Don't Create a `deploy/` Directory

Users expect Dockerfiles alongside their source code, not centralized. The convention is: Dockerfile in each sub-project, nginx-proxy.conf and deploy scripts at root. Creating `deploy/dockerfiles/` and `deploy/nginx/` is over-engineering.
