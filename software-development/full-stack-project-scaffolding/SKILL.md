---
name: full-stack-project-scaffolding
description: >-
  Create full-stack projects (Spring Boot + Vue3 + Docker) from scratch via
  parallel subagent delegation. Covers: reference project analysis, layered
  architecture generation, post-delegation compilation verification, and
  cross-cutting pitfall remediation. Trigger: user asks to "create a new
  project", "scaffold", "initialize" a full-stack app, or references existing
  projects as style guides.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [scaffolding, fullstack, spring-boot, vue3, docker, subagent, parallel]
    related_skills:
      - subagent-driven-development
      - safe-file-editing
      - writing-plans
---

# Full-Stack Project Scaffolding

## Overview

Create complete full-stack projects by analyzing reference codebases, then delegating parallel subagent tasks for each architectural layer. The key challenge is **cross-cutting consistency** — parallel subagents may introduce mismatched dependencies, annotations, or API versions.

## When to Use

- User asks to "create a new project", "build a platform", "scaffold an app"
- User references existing projects as style guides
- Tech stack spans backend + frontend + infrastructure (Docker/Nginx)
- Multiple layers can be built in parallel

## The Process

### Phase 1: Reference Analysis

Before writing any code, analyze ALL reference projects the user provides. Extract:

1. **Backend architecture**: Spring Boot version, ORM (MyBatis vs MyBatis-Plus vs JPA), security (Spring Security vs custom), dependency versions
2. **Frontend architecture**: Vue version, UI library, state management, build tool
3. **Database patterns**: Table naming conventions, entity annotations, mapper patterns
4. **Code conventions**: Constructor injection vs field injection, DTO patterns (records vs classes), response wrapper format
5. **Infrastructure**: Docker Compose services, Nginx config, port mappings

**Critical**: Record the EXACT dependency versions and frameworks. Subagents will reference these, and mismatches cause compilation failures.

### Phase 2: Parallel Delegation

Delegate these layers as independent subagent tasks:

| Batch | Tasks | Dependencies |
|-------|-------|-------------|
| 1 | pom.xml + SQL schema + application.yml + main class | None |
| 2 | Entity classes + Mapper XML + DTOs + Enums + Exceptions | Batch 1 (for table names, column types) |
| 3 | Security config + JWT filter + Service layer | Batch 2 (for entity imports) |
| 4 | Controllers + AI Agent module | Batch 3 (for service interfaces) |
| 5 | Frontend admin + Frontend public | Batch 1 (for API endpoints) |
| 6 | Docker Compose + Nginx + Dockerfile | All above |

**Within each batch**, tasks can run in parallel. Between batches, wait for completion.

### Phase 3: Compilation Verification (MANDATORY)

After ALL subagents complete, run these checks **sequentially**:

```bash
# 1. Backend compilation
cd bioplatform-springboot && mvn compile

# 2. Frontend builds
cd bioplatform-vue3/bioplatform-admin && npm install && npx vite build
cd bioplatform-vue3/bioplatform-front && npm install --legacy-peer-deps && npx vite build
```

**Do not skip this step.** Cross-cutting issues WILL exist after parallel delegation.

### Phase 4: Fix Cross-Cutting Issues

See the Pitfalls section below for the most common issues and their fixes.

## Pitfalls

### Pitfall 1: MyBatis vs MyBatis-Plus Annotation Mismatch

**Symptom**: `cannot find symbol: class TableName` / `cannot find symbol: IdType`

**Root cause**: Subagent writes entity classes with `@TableName`, `@TableId(type = IdType.AUTO)` from `com.baomidou.mybatisplus.annotation.*`, but the project uses plain MyBatis (no MyBatis-Plus dependency).

**Detection**: `mvn compile` shows `cannot find symbol` errors on entity classes.

**Fix**: Remove ALL `com.baomidou.*` imports and `@TableName`/`@TableId` annotations from entity classes. Plain MyBatis entities are plain POJOs with `@Data` only.

**Prevention**: In subagent context, explicitly state: "Use PLAIN MyBatis (not MyBatis-Plus). Entity classes must NOT use @TableName, @TableId, or any com.baomidou imports."

### Pitfall 2: JJWT API Version Mismatch

**Symptom**: `cannot find symbol: method subject(String)` / `cannot find symbol: method verifyWith(SecretKey)`

**Root cause**: Code uses JJWT 0.12.x APIs (`subject()`, `verifyWith()`, `parseSignedClaims()`) but pom.xml declares 0.11.5.

**Detection**: `mvn compile` shows errors in JwtTokenProviderUtil.

**Fix**: Either update pom.xml to `jjwt-*:0.12.6` or rewrite JWT utility to use 0.11.x APIs (`setSubject()`, `setSigningKey()`, `parseClaimsJws()`).

**Prevention**: Specify exact JJWT version in subagent context: "Use JJWT 0.12.6 APIs: subject(), verifyWith(), parseSignedClaims(), getPayload()."

### Pitfall 3: Missing AOP Dependency

**Symptom**: `package org.aspectj.lang does not exist`

**Root cause**: `@Aspect` / `@Around` / `@Pointcut` used in OperLogAspect but `spring-boot-starter-aop` not in pom.xml.

**Fix**: Add `spring-boot-starter-aop` dependency to pom.xml.

**Prevention**: When creating `@Aspect` classes, always add the AOP starter dependency.

### Pitfall 4: Missing Static Assets

**Symptom**: `Could not load src/assets/logo.svg` during vite build

**Root cause**: Vue components import assets (logo, images) that subagent didn't create.

**Fix**: Create placeholder SVG/image files, or remove imports from components.

**Prevention**: After frontend subagent completes, check for missing asset imports before build.

### Pitfall 5: npm Peer Dependency Conflicts

**Symptom**: `Could not resolve dependency: peerOptional pinia@">=3.0.0" from pinia-plugin-persistedstate@4.x`

**Root cause**: pinia-plugin-persistedstate v4 requires pinia >=3.0.0 but project uses pinia 2.x.

**Fix**: Downgrade to `pinia-plugin-persistedstate@^3.2.3` (supports pinia 2.x), or use `npm install --legacy-peer-deps`.

**Prevention**: Check peer dependency compatibility when selecting npm package versions. pinia 2.x → pinia-plugin-persistedstate 3.x.

### Pitfall 6: tsconfig.node.json Missing composite

**Symptom**: `Referenced project must have setting "composite": true`

**Root cause**: tsconfig.node.json has `"noEmit": true` but tsconfig.json references it as a project reference.

**Fix**: Replace `"noEmit": true` with `"composite": true` in tsconfig.node.json.

### Pitfall 7: OkHttp Missing Version

**Symptom**: `'dependencies.dependency.version' for okhttp is missing`

**Root cause**: `<artifactId>okhttp</artifactId>` without `<version>` and no BOM/parent managing it.

**Fix**: Add explicit version: `<version>4.12.0</version>`.

### Pitfall 8: YAML Duplicate Keys from Parallel Subagents

**Symptom**: `DuplicateKeyException: found duplicate key servlet` at Spring Boot startup.

**Root cause**: Multiple subagents write to the same `application-dev.yml` independently. Both add a `servlet:` key under `spring:`, creating a duplicate.

**Detection**: Spring Boot fails to start with SnakeYAML DuplicateKeyException.

**Fix**: Read the YAML file, identify duplicate keys, merge them into a single block.

**Prevention**: When delegating config file creation to subagents, either (a) create the YAML yourself in a single task, or (b) specify EXACTLY which section each subagent owns (e.g., "only write spring.datasource and spring.redis sections").

### Pitfall 9: JDBC characterEncoding=utf8mb4 Invalid

**Symptom**: `Unsupported character encoding 'utf8mb4'` when connecting to MySQL.

**Root cause**: JDBC URL has `characterEncoding=utf8mb4` but the MySQL JDBC driver only accepts Java charset names like `UTF-8`, not MySQL charset names.

**Fix**: Change `characterEncoding=utf8mb4` to `characterEncoding=UTF-8` in the JDBC URL.

**Prevention**: Always use `UTF-8` (Java charset name) in JDBC URLs, never `utf8mb4` (MySQL charset name).

### Pitfall 10: Frontend API Path Mismatches

**Symptom**: Login returns empty response or 404; API calls silently fail.

**Root cause**: Frontend API files call endpoints like `/api/auth/login` but backend controllers are mapped to `/api/admin/auth/login`. Subagents create frontend and backend independently without cross-referencing exact paths.

**Detection**: `curl` to the correct backend endpoint works, but the frontend shows no data.

**Fix**: Align frontend API paths to match backend `@RequestMapping` + `@PostMapping` paths exactly. Example: frontend `/api/auth/login` → backend `/api/admin/auth/login`.

**Prevention**: After creating controllers, extract the full API path map and pass it to the frontend subagent as a constraint.

### Pitfall 11: Frontend Response Field Naming (camelCase vs snake_case)

**Symptom**: Login succeeds (API returns 200) but frontend can't read tokens; `localStorage` shows `undefined`.

**Root cause**: Backend returns `accessToken`/`refreshToken` (camelCase Java record fields) but frontend store expects `access_token`/`refresh_token` (snake_case). The axios response interceptor returns `response.data` (the full ApiResponse wrapper), but the store reads fields directly without unwrapping `.result`.

**Fix**: Update the Pinia store to (a) unwrap `res.result || res` from the ApiResponse wrapper, and (b) use camelCase field names matching the backend: `data.accessToken` not `res.access_token`.

**Prevention**: Define the response contract once (field names, nesting) and enforce it in both backend DTOs and frontend types.

### Pitfall 12: SPA Routing Fails with Python http.server

**Symptom**: Navigating to `/login` returns `404 Error response: File not found`.

**Root cause**: Python's `http.server` serves files literally. SPA routes like `/login` don't correspond to real files; the server should return `index.html` for all routes.

**Fix**: Use `npx serve <dist> -l <port> -s` (the `-s` flag enables SPA single-page-app mode) instead of `python3 -m http.server`.

### Pitfall 13: Vite EMFILE (Too Many Open Files)

**Symptom**: `errno: -24, code: 'EMFILE'` during `npx vite` dev server start.

**Root cause**: System inotify watch limit too low for large projects with node_modules.

**Fix**: Either (a) increase limits: `echo 524288 | sudo tee /proc/sys/fs/inotify/max_user_watches`, or (b) skip Vite dev server entirely and serve the pre-built `dist/` with `npx serve -s`.

**Prevention**: For CI/demo environments, always serve built artifacts rather than relying on Vite dev server.

### Pitfall 14: Security Whitelist Path Mismatch

**Symptom**: API returns 403 Forbidden for login endpoint despite being a public endpoint.

**Root cause**: Security whitelist in `application-dev.yml` lists `/api/admin/users/login` but the actual controller is mapped to `/api/admin/auth/login`. Subagents copy whitelist from a reference project without checking actual controller paths.

**Detection**: `curl -v` shows `HTTP/1.1 403` with empty body.

**Fix**: Update the whitelist to match actual controller `@RequestMapping` paths. After creating all controllers, grep for `@RequestMapping` and `@PostMapping("/login")` to build the correct whitelist.

**Prevention**: Extract the full list of public endpoints from controllers before writing the whitelist.

### Pitfall 15: Entity Missing Timestamp Fields

**Symptom**: `There is no setter for property named 'createdAt' in 'class ...Role'` during MyBatis query.

**Root cause**: Database table has `created_at`/`updated_at` columns but the Java entity class is missing these fields. MyBatis attempts to map all result columns to entity properties.

**Fix**: Add `private LocalDateTime createdAt;` and `private LocalDateTime updatedAt;` to the entity class, plus `import java.time.LocalDateTime;`.

**Prevention**: After creating entities, cross-reference with `DESCRIBE <table>` in the database schema. Any column in the DB must have a corresponding field in the entity.

### Pitfall 16: MyBatis Boolean Property Name Collision

**Symptom**: `There is no getter for property named 'private' in 'class ...Project'`.

**Root cause**: Entity has `private Boolean isPrivate;` which Lombok generates as `isPrivate()` getter. But the mapper XML uses `property="private"` (the DB column name). MyBatis looks for a getter named `getPrivate()` which doesn't exist.

**Fix**: In mapper XML, change `property="private"` to `property="isPrivate"` and `#{private}` to `#{isPrivate}`.

**Prevention**: When a Java field name differs from the DB column name (common with `is*` boolean fields), always verify the mapper XML property names match the Lombok-generated getter names, not the DB column names.

### Pitfall 17: Initial bcrypt Password Hash Placeholder

**Symptom**: Login returns `密码错误` (password wrong) despite correct credentials.

**Root cause**: SQL schema inserts admin user with a placeholder bcrypt hash (`$2a$10$N9qo8uLOickgx2ZMRZoMye...`) that doesn't correspond to any actual password.

**Fix**: Generate a real bcrypt hash for the desired password and UPDATE the row:
```bash
pip install bcrypt
python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(10)).decode())"
# Then UPDATE users SET password='<hash>' WHERE username='admin';
```

**Prevention**: Include a note in the SQL schema that the password hash is a placeholder and must be regenerated, or generate it during the scaffolding process.

### Pitfall 18: Spring Security Overrides WebMvcConfigurer CORS

**Symptom**: OPTIONS preflight returns 200 with correct CORS headers, but actual GET/POST requests from browser fail with CORS error or empty response.

**Root cause**: Spring Security's `FilterChainProxy` processes requests BEFORE `WebMvcConfigurer.addCorsMappings()`. Without explicit CORS config in Security, the filter chain blocks cross-origin requests even though WebMvc CORS is configured.

**Fix**: Add CORS configuration directly in `SecurityConfig`:
```java
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration configuration = new CorsConfiguration();
    configuration.setAllowedOriginPatterns(List.of("*"));
    configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"));
    configuration.setAllowedHeaders(List.of("*"));
    configuration.setAllowCredentials(true);
    configuration.setMaxAge(3600L);
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", configuration);
    return source;
}

// In SecurityFilterChain:
http.cors(cors -> cors.configurationSource(corsConfigurationSource()))
```

**Detection**: Browser console shows "Failed to fetch" or CORS error; `curl` from command line works fine.

**Prevention**: ALWAYS add CORS config in SecurityConfig when the frontend and backend run on different ports (e.g., frontend :5173, backend :8080). Do NOT rely solely on WebMvcConfigurer CORS.

### Pitfall 19: Stale Target Directory Causes Lombok Failures

**Symptom**: `mvn compile` fails with `cannot find symbol: method getXxx()` on entities that have `@Data` and the import is correct. Previous compilation succeeded.

**Root cause**: `target/classes` contains stale `.class` files from a previous compilation with different entity definitions. Incremental compilation doesn't re-process Lombok annotations on unchanged files.

**Fix**: `mvn clean compile` (full clean rebuild).

**Prevention**: After modifying entity classes (adding/removing fields), always use `mvn clean compile` instead of `mvn compile`.

### Pitfall 20: Frontend Data Mapping Mismatches API Response

**Symptom**: Dashboard shows all zeros or blank data despite API returning correct values. Browser console shows no errors.

**Root cause**: Template binds to `dashboardData.totalUsers` but API returns `{userCount: 1}`. The frontend component doesn't map API field names to template field names.

**Fix**: Map API response fields to template bindings:
```typescript
const data = res.result || res  // Unwrap ApiResponse
dashboardData.value = {
  totalUsers: data.userCount || 0,      // Map API field to template field
  totalProjects: data.projectCount || 0,
  // ...
}
```

**Detection**: `fetch()` in browser console returns correct data, but UI shows blank/zero.

**Prevention**: Define the data contract (API response shape → template bindings) before implementing the component. Use TypeScript interfaces for both.

### Pitfall 21: Jackson Default Typing Breaks Map Deserialization

**Symptom**: `InvalidTypeIdException: missing type id property '@class'` when POST body is `Map<String, String>`.

**Root cause**: RedisConfig enables Jackson default typing (`ObjectMapper.enableDefaultTyping()` or `GenericJackson2JsonRedisSerializer`), which adds `@class` type hints to ALL serialized objects. When a controller accepts `@RequestBody Map<String, String>`, Jackson expects the JSON to include `@class` metadata, but plain JSON from clients doesn't have it.

**Fix**: Replace `Map<String, String>` request bodies with proper DTO records:
```java
// Before (breaks):
public ApiResponse<Map<String, String>> refreshToken(@RequestBody Map<String, String> request) {
    String token = request.get("refreshToken");

// After (works):
public record RefreshTokenRequest(String refreshToken) {}
public ApiResponse<Map<String, String>> refreshToken(@RequestBody RefreshTokenRequest request) {
    String token = request.refreshToken();
}
```

**Detection**: `mvn compile` succeeds but runtime POST requests to the endpoint return 500 with `InvalidTypeIdException`.

**Prevention**: When using `GenericJackson2JsonRedisSerializer` in RedisConfig (which enables default typing globally), never accept raw `Map<String, String>` in `@RequestBody`. Always use typed DTO records. Alternatively, disable default typing for the REST API ObjectMapper separately from the Redis ObjectMapper.

### Pitfall 22: Test Script Should Use Python with Decoupled Data

**Symptom**: User complains "测试用例用shell脚本写是不是不太优雅" (shell test scripts are inelegant) and "你没有做到测试数据和代码解耦" (test data not decoupled from code).

**Root cause**: Shell scripts for API testing are verbose, hard to maintain, and mix test data with test logic. Even Python scripts that embed endpoint URLs and expected values inline are hard to maintain.

**Fix**: Use Python with `requests` library AND separate test data into a dedicated config file:

**Architecture**:
```
test_data.py   # Test configuration: endpoints, execution order, expected values
test_api.py    # Test runner: logic only, reads from test_data.py
```

**test_data.py pattern**:
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TestConfig:
    base_url: str = "http://localhost:8080"
    username: str = "admin"
    password: str = "admin123"

@dataclass
class Endpoint:
    method: str
    path: str
    description: str
    body: Optional[dict] = None
    requires_auth: bool = True
    expected_code: int = 200
    depends_on: Optional[str] = None  # e.g., "admin.projects.create"

ENDPOINTS = {
    "health": Endpoint(method="GET", path="/api/front/pipelines/list", requires_auth=False),
    "auth.admin_login": Endpoint(method="POST", path="/api/admin/auth/login",
        body={"username": "{username}", "password": "{password}"}, requires_auth=False),
    # ... more endpoints
}

TEST_ORDER = [
    ["health"],
    ["auth.admin_login", "auth.user_info", ...],
    ["admin.projects.create", "admin.projects.get", ...],
    ["admin.projects.delete"],  # cleanup
]
```

**Benefits**:
- Add new tests by adding entries to ENDPOINTS dict — no logic changes needed
- Change URLs/credentials in one place (TestConfig)
- Dependencies auto-tracked (depends_on field)
- Placeholder resolution ({project_id}, {timestamp}) handled by runner
- Separation of concerns: data vs logic

**Prevention**: Always create `test_data.py` + `test_api.py` (not `test-api.sh`) as the default test format for full-stack projects.

### Pitfall 23: Database Column Length Too Short for Audit Logs

**Symptom**: `Data truncation: Data too long for column 'method' at row 1` during operation log insertion.

**Root cause**: The `operation_logs.method` column is `varchar(16)` but stores full Java method signatures like `com.bioplatform.controller.admin.AdminProjectController.update` (55+ chars).

**Fix**: Alter the column length:
```sql
ALTER TABLE operation_logs MODIFY COLUMN method VARCHAR(255);
```

**Prevention**: When creating audit/log tables, use `VARCHAR(255)` or `TEXT` for method/class name columns. Java fully-qualified class names easily exceed 100 chars.

### Pitfall 24: Vite Build Defaults to Production Mode

**Symptom**: `npx vite build` produces code with `baseURL: '/api'` instead of `baseURL: 'http://localhost:8080'`, even though `.env.development` has the correct value.

**Root cause**: `npx vite build` defaults to `--mode production`, loading `.env.production` (which typically has `VITE_API_BASE_URL=/api` for reverse proxy). The development `.env.development` is only loaded by `vite dev` or `vite build --mode development`.

**Detection**: Built JS contains `const sC = "/api"` instead of `const sC = "http://localhost:8080"`. Browser requests go to `localhost:5173/api/api/...` (double `/api`).

**Fix**: Either (a) build with `npx vite build --mode development`, or (b) update `package.json` scripts: `"build": "vite build --mode development"`, or (c) set `VITE_API_BASE_URL` in `.env.production` to the actual backend URL for that environment.

**Prevention**: Always document the build mode in the project README. For local development, the build script should explicitly use `--mode development`.

### Pitfall 25: Study Reference Projects Before Implementing

**Symptom**: User says "你的前后台axios包装没学到精髓" (you didn't learn the essence of the axios wrapper) — implemented a basic version when a mature pattern exists in the reference project.

**Root cause**: Proceeded to implement the axios wrapper from general knowledge instead of first reading the reference project's implementation to extract the proven patterns (Token auto-refresh queue, environment-based baseURL, unified api object, silent mode, binary passthrough).

**Fix**: Read the reference project's implementation thoroughly, list the specific patterns and their benefits, compare with alternatives, THEN implement.

**Prevention**: When user provides reference projects, ALWAYS:
1. Read the relevant files from ALL reference projects
2. Create a comparison table of approaches
3. Present findings to user before implementing
4. Adopt the best patterns from the reference

### Pitfall 26: Pinia Store Must Unwrap ApiResponse Consistently

**Symptom**: Login succeeds (API returns 200) but `localStorage` shows `undefined` for tokens; UI shows no user info.

**Root cause**: Axios response interceptor unwraps `response.data.result` (returns just the result), but the Pinia store does `res.result` on the already-unwrapped result (double unwrapping → `undefined`).

**Detection**: `console.log(res)` in store shows `{accessToken: '...', refreshToken: '...'}` (already unwrapped), but code does `res.result.accessToken`.

**Fix**: Store should use `const data = res?.result || res` to handle both cases:
```typescript
const res = await loginApi(params)
const data = res?.result || res  // Works whether interceptor unwrapped or not
token.value = data.accessToken
```

**Prevention**: When the axios interceptor returns `response.data.result` for code=200, ALL store functions that call API methods must handle the unwrapped response. Define this convention once and apply consistently.

### Pitfall 27: Duplicate Entity Fields After Batch Patching

**Symptom**: `variable ip is already defined in class OperationLog` — compilation fails with duplicate field error.

**Root cause**: Batch patching (e.g., adding timestamp fields to multiple entities) applied the same patch twice or merged patches incorrectly, resulting in duplicate field declarations.

**Detection**: `mvn compile` shows "variable X is already defined" errors.

**Fix**: Read the entity file, identify duplicates, remove the extra declarations.

**Prevention**: After batch patching entity classes, verify each file has no duplicate fields. Use `grep -c "private" Entity.java` to count fields and compare with expected count.

### Pitfall 28: HikariCP max-lifetime Equals MySQL wait_timeout

**Symptom**: Backend loses MySQL connectivity after ~30 min idle. All requests fail with `Communications link failure`. Restarting backend fixes it; MySQL container stays healthy.

**Root cause**: HikariCP `max-lifetime` is set equal to MySQL `wait_timeout` (both 1800s/30min). When both fire simultaneously, HikariCP holds a dead connection reference. `connection-test-query: SELECT 1` has a timing window where it passes but MySQL closes the connection before the real query.

**Fix**: Set HikariCP `max-lifetime` to 1200000 (20 min) — at least 30 seconds shorter than MySQL `wait_timeout`. Add `connection-test-query: SELECT 1` and `validation-timeout: 5000` if missing. Apply to ALL profiles (dev, docker, prod) — dev often omits HikariCP config entirely, falling back to the default 1800000.

**Prevention**: Always cross-check HikariCP `max-lifetime` against MySQL `wait_timeout` in docker-compose.yml. See `references/hikaricp-mysql-timeout-config.md` for correct values and relationships.

### Pitfall 29: Lombok @Slf4j Duplicate Logger Field

**Symptom**: `Field 'log' already exists` compilation error.

**Root cause**: Class has both `@Slf4j` annotation (which auto-generates `private static final Logger log = ...`) AND a manually declared `private static final Logger log = LoggerFactory.getLogger(...)` field. Lombok cannot generate the field because one already exists with the same name.

**Detection**: `mvn compile` shows `Field 'log' already exists` or `variable log is already defined`.

**Fix**: Remove the manual Logger declaration AND the unused `org.slf4j.Logger` / `org.slf4j.LoggerFactory` imports. Keep only `@Slf4j`.

**Detection script** (scan entire project):
```bash
for f in $(grep -rl '@Slf4j' src/ --include='*.java'); do
    grep -q 'private static final Logger log' "$f" && echo "CONFLICT: $f"
done
```

**Prevention**: When using `@Slf4j`, never also declare a `Logger log` field. If migrating from manual Logger to `@Slf4j`, always remove the manual declaration AND the `org.slf4j.*` imports in the same commit. See `references/compilation-fix-patterns.md` for the full before/after.

### Pitfall 30: Always Create Docker Deploy Script

**Symptom**: User asks to create an operational/deployment script for a new project, referencing an existing project's script.

**Root cause**: New projects lack operational tooling. Users expect consistent DX across projects.

**Fix**: Read the reference project's deploy script, extract the pattern, then adapt for the target project's docker-compose.yml. Standard commands: `start`, `debug`, `stop`, `restart`, `rebuild`, `logs [service]`, `status`, `init`, `help`.

**Prevention**: When scaffolding full-stack projects, always create `docker-deploy.sh` alongside `docker-compose.yml`. See `references/docker-deploy-script.md` for the template pattern and extraction checklist.

## Verification Checklist

After scaffolding a full-stack project, verify ALL of these:

- [ ] `mvn compile` succeeds (0 errors)
- [ ] `npx vite build` succeeds for admin frontend
- [ ] `npx vite build` succeeds for public frontend
- [ ] No entity classes use MyBatis-Plus annotations (if using plain MyBatis)
- [ ] All entity fields match database columns (cross-reference with DESCRIBE)
- [ ] Boolean fields in mapper XML use correct property names (isXxx not column name)
- [ ] JWT utility API matches declared JJWT version
- [ ] All referenced assets (SVG, images) exist
- [ ] Docker Compose file references correct Dockerfiles
- [ ] Nginx configs proxy to correct backend port
- [ ] README.md exists with setup instructions
- [ ] No duplicate YAML keys in application*.yml files
- [ ] JDBC URL uses `characterEncoding=UTF-8` (not utf8mb4)
- [ ] Frontend API paths match backend @RequestMapping paths exactly
- [ ] Frontend store unwraps ApiResponse `.result` and uses camelCase field names
- [ ] Security whitelist paths match actual controller endpoint paths
- [ ] SQL schema password hashes are valid for the intended passwords
- [ ] `curl` test to login endpoint returns 200 with tokens
- [ ] Browser login test succeeds and redirects to dashboard
- [ ] HikariCP `max-lifetime` < MySQL `wait_timeout` (at least 30s gap)
- [ ] `docker-deploy.sh` exists alongside `docker-compose.yml`
- [ ] No `@Slf4j` + manual Logger conflicts (scan with `grep -rl '@Slf4j' src/ --include='*.java' | xargs grep -l 'private static final Logger log'`)

## Feature Implementation References

When implementing file management features with folder upload, see `references/folder-upload-webkitdirectory.md` for the complete Vue3 + Spring Boot pattern: `webkitdirectory` input, directory tree preview with `el-tree`, batch upload with progress, and backend directory structure preservation.

When creating operational/deployment scripts, see `references/docker-deploy-script.md` for the template pattern: standard commands, service URL extraction from docker-compose.yml, color output, and debug mode for local development.

## Key Conventions (User-Specific)

When scaffolding for this user:
- **Language**: Chinese comments and UI labels throughout
- **Backend style**: Follow blog project conventions (constructor injection, records for DTOs, @Data entities, PageHelper pagination)
- **Frontend style**: Vue 3 + TypeScript + Vite + Element Plus + Pinia
- **Auth**: JWT dual-token (access + refresh) with Spring Security filter chain
- **Response format**: Unified `ApiResponse<T>` record with static factory methods
- **Deployment**: Docker Compose with MySQL, Redis, backend, admin, front services
- **Testing**: Create a comprehensive Python API test script (`test_api.py`) BEFORE manual browser testing. The user explicitly requested this: "我建议你建立一个完整的测试库,不用每次都要想" — they want a repeatable test suite, not ad-hoc curl commands. Use `requests` library, cover all CRUD endpoints, verify HTTP status + application code, support cleanup of test data, colored output.
- **Reference-first workflow**: When user provides reference projects, ALWAYS study them thoroughly before implementing. User explicitly corrected: "你的前后台axios包装没学到精髓" — they expect you to extract proven patterns from references, not implement from generic knowledge. Present comparison findings before coding.
- **Data decoupling in tests**: Test data (endpoints, expected values, execution order) MUST be separated from test logic. User explicitly said: "测试数据和代码解耦" — use separate `test_data.py` + `test_api.py` pattern, not inline data in test functions.
