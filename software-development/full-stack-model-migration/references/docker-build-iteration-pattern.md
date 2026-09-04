# Docker Build Iteration Pattern (China)

When `docker compose up -d --build` fails in China, errors typically come in waves.
Fix one category at a time, rebuild, check the next error.

## Common Error Sequence

### Wave 1: Image pull 403
```
ERROR: openjdk:17-jdk-slim: failed to resolve source metadata ... 403 Forbidden
```
**Fix**: Swap base images in Dockerfiles:
- `openjdk:17-jdk-slim` → `eclipse-temurin:17-jre`
- `nginx:stable-alpine` → `nginx:alpine`
- `node:18` usually works (check if blocked)

### Wave 2: Missing build tool
```
error: [vite:terser] terser not found. Since Vite v3, terser has become an optional dependency.
```
**Fix**: Remove `minify: 'terser'` and `terserOptions` from `vite.config.ts`.
Check BOTH frontend and admin configs. Use `patch` tool, NOT `sed` (sed breaks JS syntax).

### Wave 3: TypeScript errors
```
error TS2339: Property 'isReward' does not exist on type 'WebsiteResult'
error TS2552: Cannot find name 'userStore'
```
**Fix**: These are code issues exposed by the build:
- Missing type fields → add to `.d.ts`
- Missing variable declarations → add `const userStore = useUserStore()`
- Missing form init fields → add to `ref<WebsiteResult>({...})`

### Wave 4: Container conflicts
```
Error response from daemon: Conflict. The container name "/blog_minio" is already in use
```
**Fix**: 
```bash
docker compose down
# Or force remove:
docker rm -f blog_minio blog_mysql blog_redis
docker compose up -d
```

## Port Conflicts
```
failed to bind host port 0.0.0.0:8080/tcp: address already in use
```
**Fix**:
```bash
lsof -ti:8080 | xargs kill -9
```

## Verification After Full Build
```bash
docker compose ps
# All containers should show "Up"
```

## Image Naming
Docker Compose auto-names images as `<project_dir>-<service>`. If the directory
is `blog`, service `web`, image becomes `blog-web` (underscores → hyphens).
To control: add `image: blog_web` to docker-compose.yml build section.
