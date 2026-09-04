---
name: spring-vue-admin-crud-alignment
description: "Use when Spring/Vue admin CRUD contracts drift. Align APIs."
tags: [spring-boot, vue3, mybatis, admin-crud, api-alignment, verification]
related_skills: [full-stack-model-migration, systematic-debugging, safe-file-editing]
---

# Spring/Vue Admin CRUD Alignment

Use when an admin page exists on both backend and frontend, but the contract has drifted: routes differ, DTO fields no longer match, pagination keys differ, or only part of CRUD was updated.

## Core rule

Do not treat "the list page loads" as evidence the CRUD surface is aligned. For admin modules, verify list/create/update/status/reset/delete separately.

## Tight loop

1. Read the frontend API wrapper (`src/api/*Api.ts`) and the consuming view together.
2. Read the backend controller, DTOs, service interface, service impl, and mapper/XML together.
3. Build a contract table before editing:
   - route/method
   - request field names
   - response field names
   - pagination keys
   - dependent entities (roles, user_roles, owner_id, etc.)
4. Compile backend.
5. Build frontend(s).
6. If the app is containerized, run at least a targeted Docker build for the changed backend/frontend service.
7. Run CRUD smoke tests that cover every mutating endpoint, not just `list`.

## Alignment checklist

### 1) Route shape
Check whether the backend uses action-style routes:
- `/list`
- `/create`
- `/update`
- `/status`
- `/reset-password`

or REST-style routes:
- `GET /resource`
- `POST /resource`
- `PUT /resource/{id}`
- `DELETE /resource/{id}`

Do not mix them in the same module unless you confirmed both sides intentionally support both.

### 2) Request DTO names
Admin DTOs often drift from frontend expectations.
Common traps:
- `password` vs `newPassword`
- `nickName` vs `nickname`
- `page/pageSize` vs `pageNum/pageSize`
- `keyword` vs `username`
- `roles: ['user']` on frontend vs `ROLE_USER` in DB/service layer

Normalize role inputs in the service layer so the view can send simple values (`user`, `admin`) without knowing DB role naming.

### 3) Response DTO names
Spring `PageResult` frequently serializes as:
- `total`
- `pageNum`
- `pageSize`
- `list`

But many Vue admin wrappers assume:
- `records`
- `page`
- `size`

When a table renders empty despite a healthy endpoint, inspect the TS API wrapper before touching the controller.

### 4) Service-layer completeness
Fixing the controller is not enough. Verify the service actually uses the incoming parameters.
Common misses:
- `PageHelper.startPage(1, 10)` hardcoded
- keyword/status accepted by controller but ignored in service/mapper
- update only changing one field while the view edits several
- delete missing cleanup of join tables like `user_roles`
- role assignment hardcoded to `1L`

### 5) Related-table safety
When CRUD touches users/roles/projects, inspect join tables and foreign keys.
Typical pattern:
- delete child rows in join tables first (`user_roles`)
- then delete main row
- if foreign keys exist from owned resources, decide whether delete should be blocked, cascaded, or soft-deleted

### 6) Front/admin vs public/front DTO separation
Do not reuse assumptions across admin and public user flows.
Typical failure:
- admin create/update request has `nickname/phone/roles`
- public register request still only has `username/email/password/nickName`

Before reusing field accessors, read the exact DTO/record for that path.
A change that compiles in one code path can still break Docker/package builds when another DTO is compiled later.

## Verification pattern

Minimum verification after alignment:

1. `mvn -q -DskipTests compile`
2. frontend build(s)
3. Docker build of changed service(s)
4. data-driven smoke tests covering:
   - list
   - create
   - update
   - status toggle
   - reset password (if present)
   - delete

If the full stack is not currently running, report that clearly. A successful compile/build is valid evidence, but it is not equivalent to runtime CRUD verification.

## Pitfalls

- **PageResult field names AND controller @RequestParam names must BOTH match frontend.** Two independent mismatches can coexist: (1) The Java `PageResult` record uses `list`/`pageNum`/`pageSize` but the frontend TS `PageResult<T>` expects `records`/`page`/`size`. The axios interceptor unwraps `response.data.result`, so the frontend receives the record fields directly — `res.records` returns `undefined` and the table is always empty. Fix: rename the Java record components `list→records, pageNum→page, pageSize→size`. (2) Controllers use `@RequestParam pageNum/pageSize` but the frontend sends `page/size` as query params — the params silently fall back to defaults. Fix BOTH in one batch. When changing `PageResult` record field names, grep for `.pageNum()` / `.pageSize()` / `.list()` accessor calls (usually none since services use the `of()` factory). When renaming `@RequestParam`, update ALL admin+front controllers at once — the same mismatch typically affects every module. See `references/bioplatform-pipeline-alignment.md` for a real 8-controller fix.
- **DTO field completeness on create/update.** The frontend form sends 6 fields but the backend `AdminCreateRequest` DTO only declares 3 — the extra fields are silently ignored by Jackson. The entity has all 6 columns but the service only sets the 3 from the DTO. Symptom: "creation succeeded" but the record has null values for the missing fields. Fix: add ALL entity-relevant fields to the create AND update DTOs, then set them in both `createXxx()` and `updateXxx()` service methods. Also fix the controller's update handler which manually constructs a `CreateRequest` from the `UpdateRequest` — it must pass all fields, not just name/description.
- **Frontend TS interface must mirror backend entity, not imagined schema.** If the backend entity has `createdAt`/`configJson`/`ownerId`, the TS interface must use those exact names — not `createTime`/`config`/`version`/`status` which don't exist in the entity. Columns referencing nonexistent fields render as `undefined` in the table. Always read the Java entity + MyBatis resultMap before writing the TS interface.
- **Editing the wrong Spring profile config file.** Before changing any `application-*.yml`, check `docker-compose.yml` for `SPRING_PROFILES_ACTIVE` — it overrides `application.yml`'s default. Editing `application-dev.yml` when the container uses `docker` profile has zero effect. This applies to HikariCP, datasource, Redis, JWT — any config. Also fix ALL profile files (dev/docker/prod), not just the active one. (See `references/hikari-mysql-timeout.md` for a real example.)
- **HikariCP max-lifetime == MySQL wait_timeout causes periodic connection failures.** The symptom is "first request fails every ~30 min, retry works". HikariCP `max-lifetime` MUST be at least 30s less than MySQL `wait_timeout`. When equal, a race condition kills connections that HikariCP still holds. Fix: set `max-lifetime: 1200000` (20 min) when `wait_timeout=1800` (30 min). (See `references/hikari-mysql-timeout.md` for full diagnosis.)
- **JWT whitelist path mismatch breaks token refresh silently.** The docker profile whitelist had `/api/admin/users/refreshToken` instead of `/api/admin/auth/refreshToken`. Since the refresh endpoint wasn't whitelisted, Spring Security blocked it with HTTP 401, causing the refresh to fail and the user to be logged out. Always verify whitelist paths match actual controller `@RequestMapping` paths.
- **NPE in `@RequestBody Map<String, Object>` controllers.** When using `Map<String, Object>` instead of typed DTOs, `params.get("field")` returns null if the field is missing. Calling `.toString()` on null throws NPE. Always null-check: `if (params.get("field") == null) return ApiResponse.error(400, "...");`
- **Frontend/backend field name mismatch.** Frontend may send `message` while backend expects `content` (or vice versa). When using `Map<String, Object>`, add fallback logic: `Object val = params.get("content"); if (val == null) val = params.get("message");`
- **Axios response interceptor double-unwrap.** When the response interceptor returns `Promise.resolve(response.data.result)`, `axiosInstance.request()` resolves to the unwrapped result, NOT an AxiosResponse. Any code doing `res.data` after that gets `undefined` → all lists empty, no console errors. Fix: `return res as any` in the request helper. This is the #1 cause of "API returns data but page shows nothing" in Spring+Vue projects.
- **Token refresh field name + response shape mismatch.** Two bugs in one: (1) Frontend sends `{token: currentToken}` but backend `RefreshTokenRequest` expects `{refreshToken: ...}`. (2) Backend returns `Map<String, String>` with `{accessToken, refreshToken}`, but code does `refreshRes.data.result` — after interceptor unwraps, `refreshRes` IS the Map, so `.data.result` is undefined → `userStore.token = undefined` → token silently cleared on next request. Fix: send `{refreshToken: token}`, access `refreshRes?.accessToken`. Affects both reactive (401 handler) and proactive (request interceptor) refresh paths.
- **Anonymous user FK constraint on whitelisted endpoints.** When `LoginUserHolder.getCurrentUserId()` returns null for whitelisted endpoints, code may set `userId=0L` and insert into tables with FK to `users(id)` → `SQLIntegrityConstraintViolationException`. Fix: return 400/401 requiring login, or insert a system user with id=0.
- **Frontend/backend on separate ports = separate localStorage.** Admin and front are independent Vue apps on different ports. Being logged in on admin does NOT mean logged in on front. User may say "我已经登录了" but only be logged in on one side.
- **HMR doesn't hot-reload axios interceptor changes.** Vite HMR updates Vue components but changes to `axios.ts` interceptors require manual F5. User may report "still broken" after a fix because old interceptor code is still running.
- **Sensitive config (API keys) must be end-to-end encrypted.** Masking in responses is NOT enough — the save request still sends plain text visible in DevTools. Correct pattern: frontend AES-GCM encrypts (Web Crypto API) → sends `ENC:Base64...` → backend detects `ENC:` prefix, stores directly → `getConfigValue()` decrypts for internal use → `getAllConfigs()` returns masked display. Backend must skip re-encryption for `ENC:` values.
- **Encrypted masked value bypass — decrypt BEFORE checking for `***`.** When frontend encrypts a masked value like `sk-***here` → `ENC:Base64...`, backend's `***` check on the raw encrypted string passes (no `***` in Base64). The encrypted garbage gets stored. Fix: in `updateConfig`, decrypt first, then check for `***`. In `callLlmApi`, check the decrypted key for `***` before calling the API. In frontend, check for `***` BEFORE encrypting. Three-layer defense. See `references/llm-config-foolproofing.md`.
- **When fixing a sensitive data leak, grep ALL code paths — not just the obvious one.** A page may have multiple buttons that send the same sensitive field (e.g., "保存配置" AND "测试连接" both send API key). Fixing only the main save handler while a secondary button still sends plaintext means the fix is incomplete. The user will test the secondary button, see plaintext, and lose trust. After fixing one path, immediately run `grep -rn 'field_name' src/` to find every place that sends the value.
- **Don't tell the user "just refresh the page" as a first response.** When the user reports a bug persists after a code change, investigate the actual code paths before blaming HMR or cache. The user has likely already refreshed. Instead, verify the change is actually in the file, check for alternative code paths, and test in the browser yourself. Exception: NEW files (like `crypto.ts`) genuinely require F5 — Vite HMR only updates existing files. But check the code first before blaming HMR.
- **User frustration signals are first-class debugging signals.** When user says "能不能动动脑子" or "根本没有变化", they're telling you the fix didn't work — don't repeat the same explanation. Stop, re-read the code, find the actual bug. In this session: user reported plaintext API key in network tab three times before I found `testLlmConnection` was the unpatched code path.
- **Admin/front apps on separate ports have separate login sessions.** Being logged in on admin (:3000) does NOT mean logged in on front (:3001). When user says "I'm already logged in", check which app they mean. Each has its own localStorage key.
- **HMR won't hot-reload new files (like crypto.ts).** Vite HMR updates existing files but newly created files require F5. When adding a new utility file, always tell the user to hard-refresh.
- **Don't hardcode LLM model names in controller code.** `"gpt-4"` causes 400 on DeepSeek/MiMo. Let the database config determine the model. See `references/llm-provider-config.md`.
- **Don't over-engineer config — single source of truth.** User will correct you if you create a JSON file AND database config for the same thing. Pick one storage and stick with it. Same for fallback chains: `if null try X, if X null try Y` makes errors invisible. Throw a clear error telling the user which field is missing.
- **Fetch model lists dynamically via `/v1/models` API.** Don't hardcode model lists in frontend or config files — providers update models frequently. Call `GET {baseUrl}/models` with Bearer auth, filter out non-chat models (embedding/tts/whisper/dall-e/image/audio), and let user select or type manually (`filterable` + `allow-create` on el-select).
- Updating only the backend controller while `src/api/*Api.ts` still points to old routes.
- Fixing routes but forgetting to update the consuming Vue page from `records` to `list`.
- Adding admin DTO fields and then accidentally calling them from public/front DTO flows.
- Hardcoding role IDs like `1L` instead of resolving by role name.
- Adding delete endpoint but not cleaning join-table rows first.
- Extending smoke tests with create endpoints but forgetting placeholder substitution for created IDs in later update/delete calls.
- Trusting `python3 test_api.py` when the backend is not actually listening; first verify service availability.
- Seeing `NoResourceFoundException: No static resource api/...` — this means the URL hit no controller mapping and fell through to the static resource handler. The fix is always a missing or mismatched `@RequestMapping`/`@GetMapping`, NOT a static resource config issue.
- **`MissingServletRequestParameterException: Required request parameter 'X' for method parameter type Long is not present`** — backend has `@RequestParam Long projectId` (required) but frontend doesn't always pass it. Fix: make optional with `@RequestParam(required = false) Long projectId` and add null-check fallback logic (e.g., call `listAllFiles()` when projectId is null, `listByProjectId()` when present). This is common for list endpoints that can be called with or without a parent-entity filter.

## Testing discipline (user-enforced)

- **Never assume a fix works.** After making a change, verify it end-to-end on the actual target environment (remote server if that's where the bug manifests). A successful `mvn compile` or `pnpm build` is NOT evidence the fix works at runtime.
- **Test with real auth tokens.** Don't use curl without a token to test authenticated endpoints — that just confirms the whitelist works, not that the feature works. If the user is logged in on their browser, ask them to test, or use the browser tools to login and test.
- **Remote-first debugging.** When the user reports a bug on the remote server, debug against the remote server. Don't switch to local testing unless explicitly asked.

## Good implementation pattern

- Backend controller stays thin and validated.
- DTOs express exact request/response contract.
- Service resolves roles by role name, not hardcoded IDs.
- Mapper filtering matches controller query params.
- TS API wrappers mirror backend route shape exactly.
- Vue view uses the actual paginated response keys from the backend.
- Test registry stores created IDs and reuses them in downstream CRUD steps.

## Handling RuoYi Template Stub Endpoints

When a Spring Boot + Vue3 admin project uses RuoYi-Vue-Plus as a template, the frontend ships with ~90 API calls to `/system/*`, `/monitor/*`, `/tool/*` modules. These need 10+ database tables. For a blog project, create **stub controllers** in `controller/stub/` that return empty data to prevent 404s and token refresh loops.

Key response shapes differ per RuoYi module — `dept/list` and `menu/list` return `List<Map>` directly; `role/list` and `notice/list` return `{rows: [], total: 0}`. The `/api/getInfo` stub must return `{user, roles: ["admin"], permissions: ["*:*:*"]}` or frontend permissions break.

For blog-specific APIs (tag/category/article/photo), fix **frontend API files** to match backend controller paths rather than changing backend controllers.

See `references/ruoyi-stub-controllers.md` for the full set of stub controller code and module-by-module response shapes.

## Systematic full-admin audit

When fixing one module's drift, ALWAYS audit ALL admin modules at once. The same class of error (missing `/api/admin/` prefix, wrong HTTP method, id-in-path vs id-in-body) typically affects multiple modules.

**Audit procedure:**

1. Extract all frontend API calls:
   ```bash
   grep -n "http\.\(get\|post\|put\|delete\)" src/api/*Api.ts
   ```
2. Extract all backend endpoints:
   ```bash
   grep -oP '(Get|Post|Put|Delete)Mapping\("[^"]*"\)' .../controller/admin/*.java
   ```
3. Build a comparison table: frontend URL vs backend route
4. Fix all mismatches in one batch (sed or patch)
5. Verify with a Node.js script that all URLs start with `/api/admin/<module>`

See `references/bioplatform-full-admin-audit.md` for a real example covering 5 modules.

## TS2339: Frontend calls API methods that don't exist

When a Vue view calls `PhotoService.updatePhoto()` or similar but the method doesn't exist in the API class (`src/api/*Api.ts`), `vue-tsc --noEmit` fails with:

```
error TS2339: Property 'xxx' does not exist on type 'typeof XxxService'.
```

This happens when a view was written before the API methods were added, or when copying patterns from another module.

**Quick fix to unblock the build**: Add stub methods to the API class with the expected URL shape:

```typescript
// TODO: 后端未实现，占位方法
static updatePhoto(data: any) {
  return request.put({ url: '/admin/image/updateImage', data })
}
```

Use `any` for the parameter type to avoid cascading type errors. Mark with `// TODO` so it's greppable. The HTTP method (put/post) and URL path should match the expected backend contract.

**Proper fix**: Implement the backend endpoint (service interface → impl → controller) and replace the stub with typed parameters.

**Detection**: Build failure is the signal. Run `vue-tsc --noEmit 2>&1 | grep TS2339` to list all missing methods at once — typically multiple methods in the same API class are missing together.

## Implementing missing backend endpoints

When frontend calls an endpoint that doesn't exist in backend:

1. Check if service layer method already exists (common for execute/getById patterns)
2. If not, add in order: service interface → service impl → controller
3. For file downloads: use `FileSystemResource` + `ResponseEntity<Resource>`, NOT `ApiResponse`
4. For log/text returns: use `ApiResponse<String>`
5. Always validate entity exists before operating on it
6. For execute-type endpoints: accept `Map<String, Object>` body with optional params

Pattern:
```java
// Service interface
DataFile getFileById(Long id);
Path getFilePath(Long id);

// Service impl
@Override
public Path getFilePath(Long id) {
    DataFile dataFile = dataFileMapper.selectById(id);
    if (dataFile == null) throw new IllegalArgumentException("文件不存在");
    Path filePath = Paths.get(dataFile.getPath());
    if (!Files.exists(filePath)) throw new IllegalArgumentException("物理文件不存在");
    return filePath;
}

// Controller — file download uses ResponseEntity, not ApiResponse
@GetMapping("/{id}/download")
public ResponseEntity<Resource> download(@PathVariable Long id) {
    Path filePath = dataFileService.getFilePath(id);
    Resource resource = new FileSystemResource(filePath.toFile());
    return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"...\"")
            .contentType(MediaType.APPLICATION_OCTET_STREAM)
            .body(resource);
}
```

## When to reach for this skill

- Admin page buttons exist but 404 or silently fail.
- Pagination/search UI renders but has no effect.
- DTO names recently changed on one side only.
- A CRUD module was partially migrated from REST-style to action-style routes.
- Runtime works locally but Docker build fails after DTO edits.
- MySQL connection timeout or HikariCP pool issues during CRUD operations (see `references/hikari-mysql-timeout.md`).
- "Every ~30 min first request fails, retry works" — HikariCP max-lifetime race condition.
- Frontend calls a backend endpoint that returns 404 or `NoResourceFoundException` — likely missing endpoint or URL mismatch.
- User asks to "check all APIs" or "systematically audit" — run the full-admin audit procedure.
- User reports `No static resource api/...` error — the request is falling through to static resource handler, meaning no controller mapping matched.
- **Token refresh fails silently** — check JWT whitelist paths in the active Spring profile match actual controller `@RequestMapping` paths.
- **JWT proactive refresh prevents 401 errors** — reactive refresh (waiting for 401) means every expired token causes a failed request. Instead, parse the JWT payload on the frontend before each request, check if `exp` is within 5 minutes, and refresh proactively. See `references/jwt-proactive-refresh.md` for the full pattern. Also: backend `ExpiredJwtException` should be logged at DEBUG, not ERROR — token expiration is normal business flow, not an error.
- **Backend logs "Expired JWT token" at ERROR level** — change to DEBUG. Token expiration is expected business flow, not an error condition.
- **Token refresh loop from unconditional init API calls.** If `app-init.ts` calls an authenticated API endpoint without checking `userStore.accessToken` first, the request returns 401 → interceptor triggers refreshToken → refreshToken also fails (no valid session) → `logOut()` → page reloads → loop. Fix: always gate `initApp()` API calls behind `if (!userStore.accessToken) return;` and wrap in try-catch. The front-end blog app-init had this guard; the back-end admin did not, causing rapid-fire `/getBlogConfig` + `/refreshToken` requests.
- **Token refresh loop persists even after fixing initApp — `logOut()` setTimeout race condition.** Even with the initApp guard, the refresh loop can continue because `logOut()` uses `setTimeout(() => { ... }, 300)` to clear the token. During those 300ms: (1) `isRefreshing` is already `false` (from `finally` block), (2) the old token is still in memory, (3) any new request from a component's `onMounted` or watcher fires with the stale token, gets 401, and triggers another refresh cycle. The fix is a `refreshFailed` boolean flag: (a) declare `let refreshFailed = false` alongside `isRefreshing`, (b) at the top of the 401 handler, check `if (refreshFailed) return Promise.reject(...)` to block re-entry, (c) set `refreshFailed = true` in BOTH the refreshToken-401 handler AND the catch block, BEFORE calling `logOut()`, (d) remove the `finally { isRefreshing = false }` block — set `isRefreshing = false` explicitly in each branch, (e) reset `refreshFailed = false` in the request interceptor when a valid token exists (handles re-login). Also: clear the pending `requests` queue with `cb(null)` before `logOut()` to reject queued requests immediately. See `references/token-refresh-loop-fix.md`.
- **JWT whitelist bypasses filter but NOT `getCurrentUserId()` in service layer.** The JWT filter checks the whitelist and passes the request through without authentication. But if the controller/service calls `getCurrentUserId()` (which reads from `SecurityContextHolder.getContext().getAuthentication()`), it returns null → `ApiResponse.error(UNAUTHORIZED, "请先登录")`. Debug log shows "白名单匹配成功" but the API still returns 401. Fix: for truly public endpoints (like favicon/settings for non-logged-in visitors), bypass `getCurrentUserId()` and use a hardcoded default userId (e.g., `1L` for single-user blogs). The whitelist is correct — the issue is the service layer assuming authentication always exists.
- **`@MinioFile` annotation for automatic URL conversion.** Spring Boot projects with MinIO storage have `MinioResponseAdvice` + `MinioUrlConverter` that automatically prepend `file.public-base-url` to fields annotated with `@MinioFile` in `ApiResponse` responses. Use this instead of manually building URLs in service code. The annotation goes on DTO/entity String fields that store relative paths (e.g., `/my-bucket/xxx.png`). Check if the project already has this pattern before adding manual URL construction — the converter handles nested objects, collections, and Maps automatically.
- **`write_file` corrupts template literals in .ts files.** When using `write_file` on TypeScript files containing backtick template literals (`` `Bearer ${token}` ``), the backticks can get corrupted to `***`. Always use `patch` for targeted edits on .ts files, or use Python with `open(path, "rb")` + byte-level replacement when the corruption has already occurred.
- **vue-tsc fails with TS2339 on API class methods.** A view calls `XxxService.someMethod()` but the method isn't defined. Add stub methods to unblock build. See "TS2339: Frontend calls API methods that don't exist" section above.
- **User reports "token expired" errors in logs but app still works** — the reactive refresh is working, but the ERROR log is alarming. Switch to proactive refresh to prevent the log entirely.
- **NullPointerException in Map-based controllers** — add null-checks before `.toString()` on `params.get()` results.
- **Frontend sends different field names than backend expects** — add fallback logic when using `@RequestBody Map<String, Object>`.
- **File upload needs folder support** — use `webkitdirectory` attribute on `<input>`, collect `webkitRelativePath`, batch upload with relative paths. See `references/file-management-architecture.md`.
- **Large files can't go through HTTP upload** — implement rsync + import pattern: rsync transfers files to server disk, then `POST /import-local` scans directory and writes metadata to DB. See `references/file-management-architecture.md`.
- **User quota enforcement needed** — add `upload_quota` column to users table, sum `file_size` from data_files per user, check before upload. See `references/file-management-architecture.md`.
- **Large file upload fails or times out** — implement chunked upload with resume. Files >5MB are auto-split into 10MB chunks, uploaded in parallel (3 concurrent), with retry and resume support. See `references/chunked-upload-architecture.md`.
- **ALTER TABLE on running Docker MySQL** — after `docker exec ... ALTER TABLE`, also update `database/bioplatform.sql` and MyBatis mapper XML `Base_Column_List` + `resultMap`.
- **`accessTokenExpiration` wrong value in dev profile causes infinite refresh loop.** The blog project's `application-dev.yml` had `accessTokenExpiration: 10000` (10 seconds) with a comment saying `# 1h`. Token expires in 10s → interceptor refreshes → new token also expires in 10s → refreshes again → 401 cascade. Always verify expiration values match their comments: `3600000` = 1 hour, `86400000` = 1 day. Check ALL profile files (dev/docker/prod/template), not just the active one.
- **`@Slf4j` + manual `Logger` field = compile error "Field 'log' already exists".** Lombok's `@Slf4j` generates `private static final Logger log = LoggerFactory.getLogger(...)`. If the class also declares `private static final Logger log` manually, compilation fails. Fix: remove the manual declaration and the `import org.slf4j.Logger/LoggerFactory` lines — `@Slf4j` handles both.
- **Favicon: SVG for HTML pages, ICO for everything else.** Non-HTML responses (RSS XML, JSON API, Web Workers) don't parse `<link rel="icon">`. The browser falls back to `/favicon.ico`. Always provide both: `public/favicon.svg` (referenced in `index.html`) AND `public/favicon.ico` (16x16 + 32x32, generated from SVG via cairosvg + Pillow). Keep them in sync — if you change the SVG, regenerate the ICO. Use `file favicon.ico` to verify it contains "2 icons" (16+32).
- **Element Plus `.el-popper.is-light` dropdown contrast.** Default Element Plus popper uses `background: linear-gradient(...)` with light colors. If menu items inherit `color: #fff` from the header's `--menu-color`, white text on light background = unreadable. Fix: override `.el-popper.is-light` with `color: #333; background: #fff` and add nested `.el-menu-item` color rules. Also fix `.el-collapse-item__header/content` if they share the same gradient.
- **HTML editor content shows raw tags on frontend.** When admin uses wangEditor (HTML) but frontend renders with `TextOverflow` or plain text, HTML tags like `<p><br></p>` appear literally. Fix: migrate to md-editor-v3 (Markdown) on both sides — `MdEditor` for admin editing, `MdPreview` for frontend rendering. Update initial state from `'<p><br></p>'` to `''`, and empty-check from `content.trim() == '<p><br></p>'` to `!content || content.trim() === ''`. Both projects need `md-editor-v3` installed. See `references/markdown-editor-migration.md`.
- **`blog.sql` only applies to new databases.** Changing the schema file does NOT alter existing Docker MySQL databases. After adding columns to `blog.sql`, also run `ALTER TABLE` on the live database: `docker exec blog_mysql mysql -uroot -p<pass> <db> -e "ALTER TABLE ..."`. Verify with `docker exec blog_mysql mysql -uroot -p<pass> <db> -e "DESCRIBE <table>"`.
- **TS2339 build failure — missing API methods.** `vue-tsc --noEmit` fails with `Property 'xxx' does not exist on type 'typeof XxxService'` when a view calls methods not yet defined in the API class. Add stub methods with `any` param types to unblock the build, then implement the backend endpoint properly.
- **WangEditor `server` mode response format mismatch.** WangEditor's `uploadImage.server` mode expects `{ errno: 0, data: { url, alt, href } }` but Spring Boot backends typically return `{ code: 200, result: { imageUrl } }`. The image uploads successfully but never appears in the editor. Fix: replace `server` + `headers` with `customUpload(file, insertFn)` that calls the backend directly (via `fetch` with Authorization header), parses the custom response, and calls `insertFn(url, alt, href)`. The `customUpload` function also lets you transform the URL before inserting (e.g., store relative path instead of full URL). See `references/wangeditor-custom-upload.md`.
- **Java regex escaping in string literals.** `\\\\d` in Java source = `\\d` in string = literal backslash+d (NOT digit). Correct: `\\d` in source = `\d` in string = digit. See `references/java-regex-nginx-proxy-pitfalls.md`.
- **Nginx double-proxy Authorization header loss.** Inner proxy needs `proxy_set_header Authorization $http_authorization;`. See `references/java-regex-nginx-proxy-pitfalls.md`.
- **Dev whitelist `/api/admin/**` breaks authenticated endpoints.** Remove wildcard, only whitelist specific public endpoints. See `references/java-regex-nginx-proxy-pitfalls.md`.
- **Image library (素材库) integration.** Pattern for adding image picker to all upload points in admin. See `references/image-library-integration.md`.
- **Axios per-request `headers` config can strip interceptor-set Authorization.** When a request passes `headers: { 'Content-Type': undefined }` (common for FormData uploads where Content-Type must be auto-detected with multipart boundary), it can cause axios to not send the Authorization header set by the request interceptor. The interceptor uses `request.headers.set({ Authorization: ... })` but the per-request `headers` config may create a fresh headers object that doesn't carry the interceptor's additions. Symptom: all authenticated API calls work EXCEPT file upload; backend logs "请求未携带accessToken". Fix: remove the custom `headers` from the request config entirely — axios auto-detects Content-Type for FormData (adds the correct multipart boundary). If you must override Content-Type for other reasons, do it in the interceptor, not per-request.
- **`el-upload` `:action` mode bypasses axios interceptors entirely.** Element Plus `<el-upload :action="url">` sends HTTP requests via its own XHR implementation, NOT through axios. The request interceptor that adds `Authorization: Bearer ${token}` never runs. Symptom: all API calls work except file uploads from el-upload; backend logs "请求未携带accessToken". Fix: add `:headers` prop to el-upload: `:headers="{ Authorization: \`Bearer ${accessToken}\` }"`. CRITICAL: the `Bearer ` prefix is MANDATORY — setting just `{ Authorization: accessToken }` without it causes the JWT filter to reject with the same error because `authHeader.startsWith("Bearer ")` fails. This affects ALL el-upload usages with `:action` mode — when you hit this bug, grep ALL `.vue` files for `:action=` and audit each one. Common in: website settings (8+ upload fields), friend links, photo albums.
- **`ImageFileUtil` magic number validation rejects SVG/ICO.** The default `ImageFileUtil.generateUniqueImageName()` only validates via magic numbers (FFD8FF=jpg, 89504E47=png, 47494638=gif, 424D=bmp). SVG is text-based XML with no magic number; ICO has magic `00000100`. Both return null → "图片为空或图片类型错误". Fix: add ICO magic number `00000100` to the map, and add a fallback that reads the first 100 bytes as a string to detect SVG (`<svg` or `xmlns`). The fallback must open a NEW InputStream since the magic number check already consumed the first one.
- **DELETE request body: raw array vs wrapped object.** When a Spring backend has `@RequestBody AdminDeleteRequest request` (wrapping `List<Long> ids`), the frontend must send `{ ids: [1, 2, 3] }`, NOT a raw array `[1, 3]`. Sending a raw array causes `MismatchedInputException: Cannot deserialize value of type ...AdminDeleteRequest from Array value`. This is the most common DELETE contract mismatch — always check the backend DTO wrapper. Frontend fix: `data: { ids: talkIds }` instead of `data: talkIds`.
- **`v-if="!isEdit"` on form items silently hides fields in edit mode.** A common source of create/edit drift: the developer adds a field (like `createdAt`) with `v-if="!isEdit"` to show it only during creation, but forgets that the edit form also needs the field. The backend DTO for update then also lacks the field. Symptoms: (1) edit dialog missing fields that create has, (2) user can't modify the field after initial creation. Fix checklist: (a) Remove or condition the `v-if` — if edit should allow changing the field, show it unconditionally; if edit should show but not require, use a different placeholder/hint. (b) Add the field to the backend `UpdateRequest` DTO. (c) In the service `updateXxx()`, set the field conditionally: `if (request.field() != null) { entity.setField(request.field()); }`. (d) In the frontend `handleSubmit` for edit, strip empty values so they don't overwrite: `if (!data.field) data.field = undefined`. (e) In `handleEdit`, initialize the field to empty so it starts clean. This is a specialization of the "DTO field completeness" pitfall but triggered by Vue template conditionals rather than missing DTO fields.
- **Adding optional field with DB DEFAULT — backward-compatible MyBatis INSERT.** When adding a column that has `DEFAULT CURRENT_TIMESTAMP` in the DB but should accept explicit values for backfill/补录 scenarios, use this 4-layer pattern: (1) **SQL**: `ALTER TABLE t ADD COLUMN created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) AFTER some_col;` — existing rows get current time. (2) **DTO**: add `LocalDateTime createdAt` as a nullable field in the create request record. (3) **Service**: `if (request.createdAt() != null) { entity.setCreatedAt(request.createdAt()); }` — only set when provided, otherwise MyBatis omits it and DB default applies. (4) **Mapper XML**: conditionally include the column: `<if test="createdAt != null">, created_at</if>` in both the column list AND values list of the INSERT statement. (5) **Frontend**: use `el-date-picker type="datetime"` with `value-format="YYYY-MM-dd HH:mm:ss"`, empty string = don't send. In the submit handler, strip empty values: `formData.createdAt ? formData : { ...formData, createdAt: undefined }` so Jackson doesn't fail parsing empty string as LocalDateTime. Also update `Base_Column_List` and `resultMap` in the mapper XML so SELECTs return the new column. Pitfall: the `<if>` test uses the Java property name (`createdAt`), NOT the SQL column name (`created_at`).
- **Snapshot-based dirty tracking for config save — only send changed items.** When a settings page has many fields and a single "save all" button, sending ALL fields every time risks overwriting sensitive values (API keys) and wastes requests. Pattern: (1) On load, save `originalSnapshot = collectSnapshot()` of all key-value pairs. (2) On save, compare current values against snapshot, only submit changed items. (3) For sensitive fields (API keys), the snapshot stores the masked value from backend — if user doesn't touch it, it stays identical → skipped. (4) If user enters a new real value, it differs from snapshot → encrypted and sent. (5) After successful save, update snapshot. This eliminates the need for per-field `isDirty` flags like `apiKeyDirty` — everything uses the same mechanism.
- **Hierarchical data model (parent-child entities).** Pattern for adding parent-child relationships to existing entities: (1) **DB**: `ALTER TABLE x ADD COLUMN parent_id BIGINT NULL AFTER id; CREATE INDEX idx_parent_id ON x(parent_id);` (2) **Entity**: add `private Long parentId;` (3) **Mapper XML**: add `parent_id` to `Base_Column_List` + `resultMap`; add `selectAdminList` with `LEFT JOIN` for parent name; add `selectParentCandidates` (WHERE parent_id IS NULL); add `unbindChildren` (UPDATE SET parent_id=NULL WHERE parent_id=#{id}). (4) **DTO**: add `parentId` to Create/Update records, `parentName` to List record. (5) **Service**: set `entity.setParentId(request.parentId())` in create/update; call `mapper.unbindChildren(id)` before `deleteById`. (6) **Frontend**: add parent column to table, add `el-select` for parent in dialog, load candidates via `/parents` endpoint. (7) **SQL file**: sync schema SQL with the new column + index. Constraint: max 2 levels deep, cascade-unbind on delete (not cascade-delete).
- **SSE requires `proxy_buffering off` in ALL nginx layers.** When nginx-proxy (outer) proxies to container nginx (inner) which proxies to backend, BOTH need `proxy_buffering off` for SSE. If only one is set, the other buffers SSE events and the connection appears to hang. Also set `proxy_read_timeout 300s` on both — tool calls + LLM processing can exceed 60s.

## Session references

- `references/bioplatform-user-management-alignment.md` — user module: routes, pagination keys, role assignment, join-table cleanup.
- `references/bioplatform-project-alignment.md` — project module: action-style routes, update body vs path mismatch.
- `references/bioplatform-full-admin-audit.md` — full admin audit: 5 modules fixed, 4 missing endpoints implemented, verification script pattern.
- `references/hikari-mysql-timeout.md` — MySQL/HikariCP timeout debugging, profile-aware config editing.
- `references/jwt-proactive-refresh.md` — JWT proactive token refresh: parse payload before request, refresh 5min before expiry, two-layer defense against 401.
- `references/file-management-architecture.md` — Full-stack file management: folder upload with webkitdirectory, batch upload with relative paths, storage quota (disk + user), rsync + import workflow for large files.
- `references/chunked-upload-architecture.md` — Chunked upload with resume: split large files into chunks, parallel upload, resume on network failure, merge into final file.
- `references/bioplatform-pipeline-alignment.md` — Pipeline module: 3-layer fix (PageResult field names, @RequestParam naming, DTO field completeness), 8-controller batch update, TS interface vs entity alignment.
- `references/wangeditor-custom-upload.md` — WangEditor customUpload: bypass server mode response format, parse custom ApiResponse, insertFn signature.
- `references/java-regex-nginx-proxy-pitfalls.md` — Java regex escaping (\\\\d vs \\d), nginx double-proxy Authorization header loss, dev whitelist /api/admin/** breaking authenticated endpoints.
- `references/image-library-integration.md` — Image library (素材库) integration: ImagePicker component, DOM injection for md-editor-v3, full URL emission pattern.
- `references/blog-talk-alignment.md` — Blog project: implementing missing admin talk CRUD when frontend API contract already exists. Comments table stores talks with type='talk', tag field repurposed for images JSON, is_top column added.
- `references/markdown-editor-migration.md` — Migrating from wangEditor (HTML) to md-editor-v3 (Markdown): admin editor, frontend renderer, initial state, empty-check patterns.
- `references/e2e-sensitive-config-encryption.md` — End-to-end AES-GCM encryption for API keys: frontend Web Crypto encrypt → backend ENC: prefix detection → decrypt on use → mask on display.
- `references/bioplatform-ai-assistant-integration.md` — AI assistant integration: entity field name mismatch, dynamic model fetching, LLM config validation, conversation history, provider switch UX.
- `references/bioplatform-silent-failure-aug2026.md` — Multi-bug session: axios double-unwrap, token refresh clearing token, field name mismatch, anonymous FK, LLM encryption. Symptom→root-cause chain.
- `references/bioplatform-silent-failure-aug2026.md` — Multi-bug debugging session: axios double-unwrap, token refresh clearing token, field name mismatch NPE, anonymous user FK, LLM encryption. Symptom chain and root causes.
