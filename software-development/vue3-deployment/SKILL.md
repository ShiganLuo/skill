---
name: vue3-deployment
description: Deploy Vue3 multi-project setups (Docker, favicon, assets).
---

# Vue3 Full-Stack Deployment & Configuration

Operational patterns for Vue3 projects with multiple sub-projects (e.g., `blog-vue3-front`, `blog-vue3-back`, `blog-springboot`). NOT about creating projects (see `full-stack-project-scaffolding`) or debugging UI (see `vue3-frontend-debugging`).

## Docker Deploy Script

Create a `docker-deploy.sh` at project root. Template:

```bash
#!/bin/bash
set -e
# Commands: start, debug, stop, restart, rebuild, logs, status, init
cd "$(dirname "$0")"
# Use docker compose (V2), not docker-compose
case "${1:-help}" in
    start)  docker compose up -d ;;
    debug)  docker compose up -d <infra-services-only> ;;
    stop)   docker compose down ;;
    restart) docker compose restart ;;
    rebuild) docker compose build --no-cache && docker compose up -d ;;
    logs)   docker compose logs -f "$2" ;;
    status) docker compose ps ;;
    init)   # build + up + wait for DB ;;
    help|*) # print usage ;;
esac
```

Key points:
- `debug` starts only infrastructure deps (MySQL/Redis/MinIO) for local source debugging
- Always `cd` to script directory first
- Use colored output (`\033[0;32m` etc.) for INFO/SUCCESS/WARNING/ERROR
- `chmod +x` after creation

## Favicon Configuration

See `references/vue3-favicon.md` for the full procedure.

## Remote Deployment (SCP-based)

See `references/remote-deployment.md` for the full workflow, file layout, and pitfalls.

When deploying to a remote VPS (not CI/CD), use a two-script pattern:

**`remote_publish.sh`** (run locally): build JAR → build images → export tars → upload to remote → SSH remote to load + deploy.

Critical: `remote_publish.sh` MUST include `docker compose build` before `docker save`. Without it, stale images get deployed and code changes (favicon, config, compiled code) are silently lost.

The remote needs a separate `docker-compose-remote.yml` (no `build:` directives, only `image:` refs) since images are loaded from tar.

**Upload path**: Always upload to a persistent directory like `~/app/` or `~/bioplatform/`, NOT `/tmp/`. The `/tmp/` directory gets cleaned on reboot, and the deploy script needs to find the compose file there on subsequent runs.

**Upload method**: If the remote shell produces any output (check with `ssh host 'echo ok'` — should print ONLY "ok"), `scp` will fail with "Received message too long". Use SSH pipe instead: `cat file.tar.gz | ssh host "cat > /tmp/file.tar.gz"`. See `references/remote-deployment.md` for details.

## Configuration Drift Pitfall

Multi-profile Spring Boot projects (`application-dev.yml`, `application-prod.yml`) + `redis.conf` + `docker-compose-remote.yml` create a matrix of credentials that MUST stay synchronized. Mismatches cause silent runtime failures — the app starts fine (lazy Redis/MinIO init) but operations fail at request time.

**Common drift pattern**: dev profile Redis password changed during local testing → prod profile left with old password → captcha/session/cache broken on remote.

**Verification script** (run before every deploy):

```bash
#!/bin/bash
# Compare Redis password across all config sources
DEV_PW=$(grep 'password:' application-dev.yml | head -2 | tail -1 | awk '{print $2}')
PROD_PW=$(grep 'password:' application-prod.yml | head -2 | tail -1 | awk '{print $2}')
CONF_PW=$(awk '/^requirepass/{print $2}' redis.conf)
echo "dev=$DEV_PW prod=$PROD_PW redis.conf=$CONF_PW"
[ "$PROD_PW" = "$CONF_PW" ] || echo "MISMATCH: prod vs redis.conf"
```

Also check MinIO keys: `MINIO_SECRET_KEY` env var in `docker-compose-remote.yml` vs `MINIO_ROOT_PASSWORD` in the MinIO service vs `minio.secretKey` in the prod YAML.

Run `scripts/verify-deploy-config.sh <project-root>` to check all credentials at once.

**Why this breaks captcha specifically**: kaptcha generates images in-memory (no Redis needed) but storing/validating the text requires Redis. If Redis auth fails, `SafeRedisExecutor` swallows the error → captcha image shows normally → user enters correct text → validation finds nothing in Redis → "验证码错误或过期". The symptom looks like a frontend bug but is a backend config issue.

## Multi-Project Style/Theme Unification

When front-end and back-end are separate Vue3 projects with different UI frameworks (e.g., custom blog theme vs Element Plus admin), unify the visual identity through shared CSS variables.

### Primary Color Alignment

1. **Identify the source of truth** for each project:
   - Front-end: `src/styles/variable.scss` → `--primary: #xxx`
   - Back-end (Element Plus): `src/config/core/base-config.ts` → `elementPlusTheme.primary` and `src/assets/styles/variables.scss` → `--art-primary`

2. **Pick one color** and apply to both. Update the `--primary` variable in `variable.scss` — all 30+ `var(--primary)` usages across components inherit automatically.

3. **Sync the favicon SVG** to use the same primary color gradient.

4. **Verify no hardcoded old color** remains in src/:
   ```bash
   grep -rci '#oldcolor' front/src/ | awk -F: '$2>0'
   ```

### Key Insight

CSS variable changes cascade automatically — no need to touch individual component files. Changing `--primary` in one file updates every `var(--primary)` reference across the entire project.

## Element Plus Styling Pitfalls

### Dropdown/Popper Contrast Issue

Element Plus `.el-popper.is-light` default styling uses a light gradient background (`linear-gradient(120deg, #faeeff, #cfebf3)`) which clashes with menu item text color inherited from `--menu-color` (often `#fff` in light headers). Result: white text on light background = unreadable.

**Fix** in `src/styles/element/element.scss` (global, not scoped):

```scss
.el-popper.is-light {
  border: none !important;
  font-weight: 600 !important;
  color: #333 !important;
  background: #fff !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
  border-radius: 8px !important;
  .el-menu-item,
  .el-sub-menu__title {
    color: #333 !important;
  }
  .el-menu-item:hover,
  .el-sub-menu__title:hover {
    color: var(--primary) !important;
    background-color: rgba(93, 135, 255, 0.08) !important;
  }
}
```

**Also fix** `.el-collapse-item__header` and `.el-collapse-item__content` if they use the same gradient — replace with solid `#fff`.

**Dark mode**: The `dark.scss` override for `.el-popper.is-light` uses `var(--global-gradient)` background and `var(--global-white)` text — this is correct, no change needed.

## md-editor-v3: Extending the Image Dropdown

The built-in image button in md-editor-v3 has a dropdown with 3 options: 添加链接, 上传图片, 裁剪上传. This dropdown is NOT extensible via props or slots — it's hardcoded in the minified source.

**Solution: DOM injection.** After the editor renders, find the dropdown menu items and append a new `<li>`:

```ts
const injectLibraryOption = () => {
  const editorEl = editorRef.value?.$el
  if (!editorEl) return
  const menuItems = editorEl.querySelectorAll('.md-editor-menu-item-image')
  if (!menuItems.length) return
  const parent = menuItems[0].parentElement
  if (parent?.querySelector('.md-editor-menu-item-library')) return

  const li = document.createElement('li')
  li.className = 'md-editor-menu-item md-editor-menu-item-image md-editor-menu-item-library'
  li.textContent = '从素材库选择'
  li.setAttribute('role', 'menuitem')
  li.addEventListener('click', () => { showImagePicker.value = true })
  parent?.appendChild(li)
}

// Inject after editor renders
watch(() => editorRef.value, () => nextTick(injectLibraryOption))
onMounted(() => nextTick(() => setTimeout(injectLibraryOption, 500)))
```

**Why NOT use NormalToolbar**: Adding a separate `NormalToolbar` button next to the image button looks disconnected — users don't expect two image-related buttons. DOM injection puts the option IN the existing dropdown where users naturally look.

**Why NOT use DropdownToolbar to replace**: Replicating the 3 built-in options (link modal, file upload, cropper) requires deep integration with md-editor-v3's internal event bus. DOM injection is simpler and survives library updates better.

## Image Upload Architecture

See `references/image-upload-architecture.md` for the full pattern.

**Core principle**: Store relative paths (`/my-bucket/xxx.png`) in article content, NOT full URLs. Resolve to full URL at render time via `VITE_MINIO_URL` env var. This makes MinIO migration a single env var change instead of a database-wide find-replace.

**WangEditor integration**: WangEditor expects `{ errno: 0, data: { url } }` but Spring Boot returns `{ code: 200, result: { imageUrl } }`. Use `customUpload` callback instead of `server` URL. Pass `result.imageUrl` to `insertFn()`.

**md-editor-v3 integration**: The `onUploadImg` callback in `MarkdownEditor.vue` also needs fixing. Default code checks `res.errno === 0` and uses `res.data.url` — change to `res.code === 200` and `res.result.imageUrl`. Also ensure `Authorization` header has `Bearer ` prefix.

**Image library**: Add `ImagePicker` component (grid dialog with search/upload) to avoid re-uploading the same images. Backend API: `GET /api/admin/image/list?fileName=xxx`.

## Element Plus Blank Page (CRITICAL)

When deploying a Vue3 + Element Plus project and the page is blank (200 status, Vue mounts, but renders nothing):

**Cause**: `app.use(ElementPlus)` missing in `main.ts`. The CSS import and icon registration are NOT enough.

**Diagnosis**: `google-chrome --headless --no-sandbox --virtual-time-budget=10000 --dump-dom URL` — if `el-` class count is 0, Element Plus is not registered.

**Fix**: Add `import ElementPlus from 'element-plus'` and `app.use(ElementPlus)` before `app.use(pinia)`.

## Shared Nginx-Proxy Cascading Failure (CRITICAL)

When bioplatform (or any project) shares an nginx-proxy container with other projects (e.g., the blog), a failure in ANY upstream project brings down the ENTIRE proxy.

**Mechanism**: nginx loads ALL `server {}` blocks at startup. If any `proxy_pass` upstream hostname can't be resolved (e.g., `blog_web` container is down), nginx refuses to reload/start — returning 000 for ALL domains including yours.

**Diagnosis**:
```bash
# This is the FIRST thing to check when all domains return 000
ssh ... 'docker exec nginx-proxy nginx -t 2>&1'
# Output: "host not found in upstream 'blog_web'" = root cause found

# Check which containers are down
ssh ... 'docker ps -a --format "{{.Names}}\t{{.Status}}"'
```

**Fix**: Start the missing upstream containers, then reload nginx:
```bash
ssh ... 'cd ~/blog && docker-compose -f docker-compose-remote.yml up -d'
ssh ... 'docker exec nginx-proxy nginx -s reload'
```

**Prevention**: The nginx-proxy.conf should use `resolver` directive with `set $upstream` variable syntax to avoid hard-failing on unresolvable upstreams. But the simpler fix is ensuring all referenced projects stay running.

## Remote Server Pitfalls

### docker-compose vs docker compose

The Aliyun server has `docker-compose` v1 (standalone binary at `/usr/local/bin/docker-compose`), NOT the v2 Docker plugin (`docker compose`). Commands like `docker compose -f ... up` fail with `unknown shorthand flag: 'f'`.

**Fix**: Use `docker-compose` (with hyphen) in all remote scripts, or detect which is available:
```bash
if docker compose version &>/dev/null; then COMPOSE="docker compose"
elif docker-compose version &>/dev/null; then COMPOSE="docker-compose"
else echo "No compose found"; exit 1; fi
```

**Impact on deploy scripts**: `remote_publish.sh` uses `docker compose` — must be changed to `docker-compose` or the detection pattern above for the remote server.

### http_proxy on Remote Server

The Aliyun server has `http_proxy=http://127.0.0.1:7890` set (likely from a stopped clash/v2ray proxy). This causes ALL `curl` commands to fail with "Connection refused to 127.0.0.1:7890".

**Diagnosis**: `curl -v http://localhost/ 2>&1 | head -5` shows "Uses proxy env variable http_proxy".

**Fix**: Use `curl --noproxy '*'` for all testing, or `unset http_proxy HTTPS_PROXY` before testing.

### nginx-proxy DNS Caching After Container Recreation

After `docker-compose up -d --force-recreate`, containers get new IP addresses. nginx caches the old DNS resolutions, so requests route to stale (now-dead) IPs. Result: `bio.shiganluo.top` serves `bioadmin.shiganluo.top`'s content and vice versa — routing appears "reversed".

**Fix**: Always reload nginx after container recreation:
```bash
docker-compose -f docker-compose-remote.yml up -d --force-recreate <services>
docker exec nginx-proxy nginx -s reload
```

**Pitfall**: If other upstream containers are down (e.g., `blog_web`), `nginx -s reload` fails with `host not found in upstream`. Start all referenced containers first, THEN reload.

### JWT Whitelist Bypass for Stale Tokens

Spring Security's `JwtAuthenticationFilter` should unconditionally permit whitelisted paths. The original pattern:
```java
if (isWhitelisted(requestUri) && !StringUtils.hasText(jwt)) {
    filterChain.doFilter(request, response);
    return;
}
```
This fails when the browser sends a stale JWT token (from localStorage, signed with a different secret) to a whitelisted endpoint like `/api/admin/auth/login`. The filter tries to validate the invalid token and returns 403.

**Fix**: Whitelist check first, unconditionally:
```java
if (isWhitelisted(requestUri)) {
    filterChain.doFilter(request, response);
    return;
}
String jwt = extractTokenFromRequest(request);
```

**Why tokens get stale**: JWT secret changed between deployments (e.g., Base64 vs plaintext format in `application-prod.yml` vs `application-docker.yml`). Users' browsers still have the old token.

- **Admin nginx.conf must include /api/ proxy.** When the admin frontend container's nginx config only serves static files (no `/api/` location), direct access to the admin container's port fails API calls. The shared nginx-proxy intercepts `/api/` before reaching the admin container, so this only matters for direct port access. But for consistency and resilience, always include `/api/` and `/ws/` proxy locations in admin nginx.conf matching the front nginx.conf pattern.

- **Multi-layer nginx Authorization header forwarding (CRITICAL).** When requests go through multiple nginx layers (nginx-proxy → container nginx → backend), the `Authorization` header must be forwarded at EVERY layer with `proxy_set_header Authorization $http_authorization;`. Missing it at ANY layer causes 403 from Spring Security's JWT filter — the token arrives at the backend as null. Symptom: login works (whitelisted, no auth needed), but all authenticated API calls return HTTP 403. The user sees "token是正常的" because the browser sends it correctly — it gets stripped by an intermediate nginx. Diagnosis: test from inside the container (`docker exec <admin> wget -q -O- --header='Authorization: Bearer <token>' http://backend:8080/api/admin/...`) to bypass all nginx layers. If that works, the issue is in nginx forwarding, not the backend. Both `nginx-proxy.conf` (the shared proxy) AND each container's own `nginx.conf` need the header.
- **Remote deploy script should use docker-compose**

The `remote_publish.sh` runs on the remote server via SSH. It MUST use `docker-compose` (v1) not `docker compose` (v2), because the remote server only has v1 installed.

- **SSH reverse tunnel + Docker container port access.** When a Worker node establishes an SSH reverse tunnel (`ssh -R 18081:127.0.0.1:18081`), the tunnel binds to `127.0.0.1:18081` on the gateway server by default. Docker containers CANNOT reach `127.0.0.1` on the host — it resolves to the container's own loopback. Fix: use `socat` to relay from `0.0.0.0:18081` to `127.0.0.1:18081` on the gateway server. Note: `ssh -R 0.0.0.0:18081:127.0.0.1:18081` requires `GatewayPorts yes` in sshd_config (default is `no`), and the user may not have sudo. Also, socat can't bind to `0.0.0.0:18081` if the SSH tunnel already occupies `127.0.0.1:18081` (Linux treats them as overlapping). Workaround: use a different port for the tunnel (e.g., 28081) and socat from `0.0.0.0:18081` → `127.0.0.1:28081`. Container URLs should use `172.19.0.1` (blog_net gateway = host) not `localhost`.

- **VITE_API_BASE_URL double /api path (CRITICAL).** When the frontend API calls already include `/api` prefix (e.g., `http.get('/api/front/projects/list')`) AND `VITE_API_BASE_URL=/api` is set in `.env.production`, the resulting URL becomes `/api/api/front/projects/list` → 403 from backend. The nginx-proxy forwards `/api/` to the backend, so the path is preserved. Fix: set `VITE_API_BASE_URL=` (empty string) in `.env.production` when API paths already contain the `/api` prefix. This applies to BOTH `bioplatform-front` and `bioplatform-admin`.

- **Docker container outbound connectivity (iptables NAT).** On Aliyun ECS, Docker containers on custom bridge networks (like `blog_net`) may not be able to reach external hosts even though the host can. Root cause: missing iptables NAT masquerade rule. Diagnosis: `docker exec <container> curl -s --max-time 5 http://www.baidu.com/` returns empty/000 while the host can access it. Fix: `sudo iptables -t nat -A POSTROUTING -s 172.19.0.0/16 ! -o docker0 -j MASQUERADE`. Also check FORWARD chain policy. Note: Docker restart (`systemctl restart docker`) may clear custom iptables rules — re-add after restart. Persist rules in `/etc/rc.local` or cron `@reboot`.

- **Aliyun ECS raw table PREROUTING DROP rules (CRITICAL).** Even with correct NAT rules and security groups, containers may still get "Connection refused" (RST) when accessing external hosts. Root cause: Aliyun security tools add DROP rules in `iptables -t raw PREROUTING` for each container IP: `! -i br-xxx -d 172.19.0.x -j DROP`. These rules operate BEFORE conntrack, so return traffic for ESTABLISHED connections is also dropped — the host generates a RST instead of forwarding the response.

  **Diagnosis**: `sudo tcpdump -i br-f94c057f9c2b -n host 172.19.0.3 -c 5` shows SYN going out and RST coming back in the SAME millisecond — too fast for a real round trip, meaning the RST is locally generated. The `sudo iptables -t raw -L PREROUTING -n` shows per-container-IP DROP rules.

  **Fix**: Delete the raw table DROP rules for the Docker subnet:
  ```bash
  sudo iptables -t raw -D PREROUTING ! -i br-f94c057f9c2b -d 172.19.0.2 -j DROP
  # ... repeat for each container IP
  ```
  Note: `!` must come BEFORE `-i` (not after), and bash history expansion (`!br`) must be disabled with `set +H` or escaped.

  **Why this is separate from NAT issues**: NAT rules handle source IP translation. Raw table rules operate at a lower level — they drop packets before conntrack even sees them, so ESTABLISHED,RELATED rules in other tables can't help. Both must be fixed for containers to reach the internet.

  **Persistence**: These rules are re-added by Aliyun's security agent on reboot. Persist the deletion in a cron job or systemd service.

- **Aliyun security group outbound rules.** If iptables NAT rules are correct but containers still can't reach external hosts, check the Aliyun ECS security group. By default, security groups may restrict outbound traffic. Add an outbound rule: protocol=ALL, destination=0.0.0.0/0, policy=ALLOW. This is separate from iptables — the security group operates at the VPC/network level.

- **Database schema drift vs MyBatis mapper XML.** When `ALTER TABLE` is done on the remote DB but the mapper XML references columns not in the local `bioplatform.sql` init script, new deployments from scratch will fail. Always sync `ALTER TABLE` changes back to the SQL init file. Verify with `ssh ... 'docker exec blog_mysql mysql ... -e "DESCRIBE table;"'` vs the mapper's `<sql id="Base_Column_List">`.

- **Axios interceptor + frontend catch block duplicate error messages.** When the axios response interceptor already shows `ElMessage.error(msg)` for non-200 responses, the frontend component's `catch` block must NOT also call `ElMessage.error(...)`. This causes two identical/similar toasts. Pattern: remove `ElMessage.error` from catch blocks in login/register forms; the interceptor handles it. Only keep `ElMessage.success` in the try block.

## Pitfalls

- **NEVER clone repo on remote and rebuild (CRITICAL).** When deploying a change, ALWAYS build the image locally and transfer via `docker save` → pipe → `docker load`. NEVER `git clone` on the remote server and `docker build` there. Cloning pulls the latest code which may differ from what's running (different pom.xml dependencies, new config requirements, changed application.yml). This causes the container to fail on startup (missing `jwt.secret`, `JavaMailSender` not found, etc.) and breaks the entire production system. The user will be extremely frustrated. The ONLY exception is when the remote server IS the build server and has the full dev environment set up.

- **NEVER patch a JAR file in-place inside a running container (CRITICAL).** Using `docker cp` to extract a JAR, `zip -f` to update a single file (like a mapper XML), then `docker cp` back will corrupt the JAR. Spring Boot fat JARs have complex nested structures and `zip -f` doesn't properly update the central directory CRC. The corrupted JAR causes ALL backend requests to fail. The correct approach for ANY change (even a single XML file): rebuild the image locally, `docker save`, transfer, `docker load`, restart. It takes longer but never breaks anything.

- **"只构建变更镜像" — only build the changed image.** When only one service changed (e.g., backend only), do NOT rebuild all images. Build/save/upload/restart ONLY the changed service. This is faster and reduces risk. See `references/remote-deployment.md` for the selective rebuild pattern.

- **Back-end missing `public/`**: Vite serves `public/` as static root. If the back-end project was scaffolded without it, `mkdir -p` and copy the favicon.
- **Old favicon refs**: Check for `favicon.ico`, `favicon.png`, or asset-path references like `src/assets/img/favicon.ico` — these must be replaced, not left alongside.
- **`write_file` on .vue files**: ALWAYS use `patch` tool, never `write_file` — .vue files get corrupted by write_file.
- **Check the browser instead of asking the user.** When the user says a button doesn't show or a feature doesn't work, use `browser_navigate` + `browser_vision` to inspect the actual page. Don't ask "can you see it?" — go look yourself. The user explicitly corrected this: "你不可以寄实际查看浏览器页面看看效果吗,还需要问我".
- **Check existing storage format before adding URL conversion layers.** Before creating `imageUrl.ts` utilities with `toRelativePath`/`resolveImageUrl`, verify what the database actually stores. Run `SELECT file_path FROM images LIMIT 5` and `SELECT cover_image FROM articles LIMIT 5`. If these already contain relative paths (like `my-bucket/xxx.png`), do NOT create utility files, do NOT add `ImageResponse.filePath` fields, do NOT add `resolveImageUrl()` calls in display components. The only fix needed is the editor's `customUpload`/`onUploadImg` response handling. Adding unnecessary abstraction layers creates confusion and extra maintenance burden. The user WILL correct you on this.
- **Never `git checkout` to revert changes when debugging without careful scope control.** A blanket `git checkout -- <files>` reverts ALL changes to those files, including valid modifications made earlier in the session. When fixing a subset of changes, use targeted reverts: `git diff` to see what changed, then manually revert only the problematic lines. Or use `git stash` to save current state before reverting.
- **Lombok @Slf4j + manual Logger**: If a Java class has both `@Slf4j` annotation AND `private static final Logger log = LoggerFactory.getLogger(...)`, compilation fails with "Field 'log' already exists". Fix: remove the manual declaration and its imports (`org.slf4j.Logger`, `org.slf4j.LoggerFactory`). The `@Slf4j` annotation generates the field automatically.
- **`ElMessageBox.alert` for token expiry is intrusive on public pages.** When the token refresh fails on a public-facing blog page, `ElMessageBox.alert('登录状态已过期', '系统提示', { type: 'warning' })` creates a blocking modal dialog that appears in the wrong position (top-left) and requires user interaction. Replace with `ElMessage.warning('登录状态已过期，请重新登录')` — a non-blocking toast notification. Check BOTH `blog-vue3-front/src/utils/http/index.ts` AND `blog-vue3-back/src/utils/http/index.ts`. Also remove unused `ElMessageBox` import after replacement. The admin panel may have `ElMessageBox` used without import (runtime error when triggered).
- **Remote Docker MySQL schema comparison.** When remote DB was initialized from older `blog.sql`, columns may be missing. Compare with `ssh ... 'docker exec blog_mysql mysql ... -e "DESCRIBE table;"'` vs local SQL. See `references/remote-schema-comparison.md` for batch comparison script and pitfalls.
- **Browser cache after deployment (nginx `expires 30d; immutable`).** When nginx caches static assets for30 days with `Cache-Control: public, immutable`, even Vite content-hash filenames don't help if the browser cached the OLD `index.html` (which references the OLD JS filename). The user sees no changes after deployment. Hard refresh (`Ctrl+Shift+R`) fixes it, but users won't know to do this. Verify deployment by checking the JS file content directly: `docker exec <container> grep 'your-new-text' /usr/share/nginx/html/assets/SomeView-*.js`. If the content is there but the user sees no change, it's browser cache. Consider adding `no-cache` headers for `index.html` specifically in nginx config.

- **Vite EMFILE: too many open files (inotify exhaustion).** Vite dev server watches the entire project directory tree via Linux inotify. There are TWO independent limits: `max_user_watches` (65536, per-file watches) and `max_user_instances` (128, per-process monitoring contexts). VSCode with many extensions easily exhausts `max_user_instances` (each extension = 1 instance) even when watch count is low. Symptom: `Error: EMFILE: too many open files, watch '...'` crash during `pnpm run dev`. Fix: (1) Add `watch: { ignored: ['**/node_modules/**', '**/.git/**'] }` under `server:` in BOTH `blog-vue3-front/vite.config.ts` and `blog-vue3-back/vite.config.ts`. (2) Increase BOTH limits: `sudo sysctl fs.inotify.max_user_watches=524288 fs.inotify.max_user_instances=512` and persist in `/etc/sysctl.conf`. Diagnostics: check `max_user_instances` usage with `find /proc/*/fdinfo -type f -exec grep -l inotify {} \; 2>/dev/null | wc -l`. See `references/vite-watch-inotify.md` for full diagnostics and the watch-vs-instance distinction.
- **MinIO port mapping vs config.** Docker Compose maps `9007->9000` (API) and `9008->9001` (console). The `application-dev.yml` must use `endpoint: http://127.0.0.1:9007` and `consolePonint: http://127.0.0.1:9008`, NOT the internal container ports. Also update `file.public-base-url` to match. The prod profile uses Docker internal networking (`http://minio:9000`), so no host port mapping needed. Symptom: `java.net.ConnectException: Failed to connect to /127.0.0.1:9000` when uploading images in dev.
- **ImagePicker `vite.config.ts` patch corruption.** When using `patch` tool on `vite.config.ts` to add `watch: { ignored }`, the regex patterns in `proxy.rewrite` (e.g., `path.replace(/^\\/dev-api/, '/api')`) get their backslashes mangled by the patch tool's escaping. Fix: use `sed -i` via terminal instead of the `patch` tool for this file, or `git checkout` and re-apply manually.
