---
name: full-stack-model-migration
description: >
  Coordinate data model changes across Spring Boot (MyBatis) backend + Vue3 frontend.
  Covers: adding tenant/user isolation columns, updating entity→mapper→service→controller,
  frontend API/type/view alignment. Trigger: user wants to add multi-tenancy, refactor
  a data model, or change database schema across full stack.
tags: [spring-boot, mybatis, vue3, full-stack, database, multi-tenant, refactoring]
---

# Full-Stack Model Migration

Pattern: change a database table, then propagate the change through every layer of the stack.

## Migration Checklist (Spring Boot + MyBatis + Vue3)

### Layer 1: Database
1. ALTER TABLE to add/modify columns
2. Add UNIQUE constraints, foreign keys as needed
3. Update the SQL schema file (.sql) for fresh installs
4. Update existing data if needed (migrate old records)

### Layer 2: Entity (Java)
1. Add new fields to the entity class
2. Fix type mismatches (e.g., String vs Integer for TINYINT columns)
3. Ensure field names match MyBatis naming conventions

### Layer 3: Mapper Interface (Java)
1. Add new query methods (e.g., `getXxxByUserId`)
2. Remove duplicate/ambiguous method signatures
3. Add `@Param` annotations for multi-param methods
4. Add delete/update methods for the new queries

### Layer 4: Mapper XML
1. Add new columns to `<resultMap>`
2. Update all `<insert>` statements to include new columns
3. Add new `<select>` queries for the new access patterns
4. Add `<update>` variants if needed (selective vs full update)
5. Add `<delete>` if needed

### Layer 5: Service
1. Inject any new dependencies (e.g., UserMapper for auth)
2. Add helper methods (e.g., `getCurrentUserId()` from SecurityContext)
3. Replace hardcoded IDs with dynamic lookups
4. Add null-safety checks (NPE protection)
5. Update method signatures if needed

### Layer 6: Service Interface
1. Add new method declarations
2. Update existing signatures

### Layer 7: Controller
1. Update endpoints to use new service methods
2. Remove redundant/duplicate endpoints
3. Update URL patterns if needed (e.g., add path variables)
4. Ensure auth context is used correctly

### Layer 8: Frontend Types (TypeScript)
1. Update/add interfaces to match backend DTOs
2. Add missing fields
3. Fix naming inconsistencies

### Layer 9: Frontend API (TypeScript)
1. Update API method signatures (add parameters)
2. Update URL patterns to match new backend routes
3. Ensure type parameters match

### Layer 10: Frontend Views (Vue)
1. Import new dependencies (stores, utilities)
2. Pass required parameters to API calls
3. Handle loading/error states for new flows
4. Update templates if data structure changed

## Remote Schema Comparison

When the remote database is out of sync with the local SQL schema file, use this workflow:

```bash
# 1. Get remote table columns
ssh -p PORT user@host "docker exec blog_mysql mysql -uroot -pPW blog -e 'DESCRIBE table_name;'"

# 2. Get local SQL file columns (handle mixed tabs/spaces and optional backticks)
awk '/CREATE TABLE.*table_name/,/);/' blog.sql | grep -E '^\s+`\w+`\s+' | awk '{print $1}' | tr -d '`'

# 3. Compare column lists
```

**SQL file parsing pitfall**: `blog.sql` may use mixed indentation (tabs vs spaces) and some tables lack backticks around column names. The regex `^\s+\`(\w+)\`\s+\w+` catches backtick-quoted columns but misses unquoted ones. Always verify with a direct grep of the SQL file.

## ALTER TABLE with Existing Data

When adding a NOT NULL column with FOREIGN KEY to a table that already has data:

```sql
-- Step 1: Add column as nullable (avoids default value issues)
ALTER TABLE blog_settings ADD COLUMN user_id BIGINT DEFAULT NULL AFTER id;

-- Step 2: Update existing rows with valid values
UPDATE blog_settings SET user_id = 1 WHERE user_id IS NULL;

-- Step 3: Modify to NOT NULL
ALTER TABLE blog_settings MODIFY COLUMN user_id BIGINT NOT NULL;

-- Step 4: Add constraints
ALTER TABLE blog_settings ADD UNIQUE KEY uk_blog_setting_user (user_id);
ALTER TABLE blog_settings ADD CONSTRAINT fk_blog_setting_user
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
```

**Why this order matters**: Adding NOT NULL + FK in one statement fails if existing rows have user_id=0 (default for NOT NULL without explicit value) because 0 doesn't exist in the referenced users table. The nullable→update→NOT NULL→FK sequence avoids this.

## Pitfall: Remote schema drift after local-only changes

When `blog.sql` is updated locally but the corresponding ALTER TABLE is never executed on the remote Docker MySQL, the backend crashes at runtime with `Unknown column 'xxx' in 'field list'` or `Data too long for column 'xxx'`. Common after adding new features locally and deploying code without running the migration.

**Detection**: Backend logs show `SQLSyntaxErrorException` or `MysqlDataTruncation` on INSERT/UPDATE. Cross-check with `DESCRIBE table_name` on remote vs the CREATE TABLE in blog.sql.

**Fix**:
```bash
# MySQL is inside Docker, not on host PATH
ssh -p PORT user@host "docker exec blog_mysql mysql -uroot -pPW blog -e 'ALTER TABLE ...;'"
```

**Column type mismatch pattern**: blog.sql may define a column as `TEXT` but the remote DB has it as `varchar(32)` from an earlier schema version. This causes `Data truncation: Data too long for column 'tag'` when storing JSON (e.g., talk image URLs). Fix: `ALTER TABLE MODIFY COLUMN tag TEXT`.

**Prevention**: After any local schema change, always diff blog.sql against remote `DESCRIBE` before deploying the code. The skill's "Remote Schema Comparison" section has the comparison commands.

## Pitfalls

- **Batch frontend API updates incomplete**: When changing an API signature (adding required param), grep ALL callers across the frontend: `grep -rn "methodName()" src/ --include="*.vue" --include="*.ts"`. Missing one caller = runtime error. Common miss: `app-init.ts` which runs before login and can't access user store.
- **Hardcoded IDs**: The most common single-site→multi-user issue. Search for `1L`, `id=1`, `(long) 1` in service layer AND background services. Commonly missed locations: `@Scheduled` tasks (e.g., VisitCountSyncTask), cache/counter services (e.g., RedisVisitCounter), RSS/feed generators. These don't go through controllers so they're easy to overlook. Grep broadly: `grep -rn "1L\|= 1;" src/main/java/ --include="*.java"`
- **Semantic parameter mismatch after migration**: When adding `userId` to a table, controllers may pass `userId` but internal service calls still use `getSettingById(id)` instead of `getSettingByUserId(userId)`. The method receives a `userId` value but queries by primary key — silently returning null. After ANY migration that adds a user/tenant isolation column, grep ALL service method bodies for old query methods: `grep -rn "getSettingById\|getXXXById" src/main/java/.../service/`. Verify every caller passes the right type of ID to the right query method.
- **Mapper duplicate signatures**: Two methods with same name but different param types (long vs Long) cause MyBatis binding errors.
- **Null-safety gaps**: Service methods that call `entity.getXxx()` without null-checking the entity first.
- **Type mismatches**: DB TINYINT(1) mapped to Java String when DTO expects Integer (or vice versa).
- **Naming inconsistencies**: Entity field `wechatQrCode` vs DTO `weiXinQRCode` vs DB column `wechat_qrcode` — must be consistent.
- **Frontend param propagation**: When backend adds required params to API, every frontend caller must be updated. Search for all usages of the API method.
- **Vue store initialization is two steps**: Adding `import { useUserStore } from "@/stores/index"` is NOT enough. You must ALSO add `const userStore = useUserStore()`. These are independent operations that can each be missed. When batch-modifying Vue files, always verify BOTH the import AND the const declaration exist. Check with: `grep -rn "useUserStore" src/ --include="*.vue"` — files with import but no `const userStore` will have runtime errors.
- **API error silencing for expected errors**: When a backend endpoint returns a "not found" or "not initialized" error that's expected (e.g., user hasn't set up blog settings), the HTTP interceptor shows an ElMessage toast BEFORE the promise rejects. `.catch()` alone cannot suppress the message because the interceptor fires first. **Two-layer fix**: (1) Add `silent?: boolean` to AxiosRequestConfig via `declare module 'axios'`, check it in the response interceptor before showing ElMessage. (2) Add `silent: true` to the API call config, plus `.catch()` for graceful fallback. See `references/http-interceptor-silent-pattern.md` for the full implementation.
- **Default asset fallback pattern**: When a dynamic asset URL (background image, avatar, logo) might be empty, import a local default and use `|| defaultBg` as fallback in both JS and template: `:src="url || defaultBg"`. Apply at the component level (e.g., PageHeader) so all parent pages inherit the fallback.
- **Selective vs Full update**: MyBatis `<if test="xxx != null">` means null fields won't be cleared. Use a separate full-update SQL if users need to clear fields.
- **Vue SFC file corruption (CRITICAL)**: `write_file` on `.vue` files silently empties them, causing "At least one <template> or <script> is required" errors. NEVER use `write_file` on existing `.vue` files. ALWAYS use `patch` for modifications. If corrupted, recover with `terminal: git checkout -- <file>`. See `safe-file-editing` skill for the full rule set.
- **Batch execute_code + write_file**: Using `execute_code` with `write_file` inside a loop empties multiple files in one pass. Use `patch` for targeted edits instead; only use `write_file` for brand-new files.
- **GET + @RequestBody**: Spring Boot `@GetMapping` with `@RequestBody` fails with "Required request body is missing". GET requests have no body. Use `@ModelAttribute` for query parameters, or change to `@PostMapping`. Common when frontend sends `params: {}` (query string) but backend expects body.
- **Frontend-backend param mismatch**: Frontend `request.get({ params: query })` sends URL query params. Backend must use `@ModelAttribute` or `@RequestParam`, NOT `@RequestBody`. Verify HTTP method matches parameter binding.
- **Components in App.vue re-mount on route change**: Any component imported in `App.vue` (e.g., WelcomeMessage, global notifications) will re-trigger `onMounted` every time the user navigates. If the component has side effects (API calls, ElMessage popups), they repeat on every page switch. Fix: add a `sessionStorage` guard to ensure the side effect runs only once per session.
- **ElMessage "positioning" is usually not a CSS issue**: When unexpected text appears on the page (especially bottom-left), don't assume it's an ElMessage CSS positioning bug. First check: is a component in `App.vue` or a layout component re-firing on route change? The text is often a legitimate ElMessage from a component that re-mounts. Check component lifecycle before checking CSS.
- **Docker build in China: multi-round fixes**: Docker builds in China often fail in sequence: (1) image 403 → swap base images, (2) terser not found → remove terser config, (3) TypeScript errors → fix code. Fix one category at a time, rebuild, check next error. Don't try to fix everything at once. Also: `sed` on vite.config.ts can break syntax — use `patch` tool for precise edits instead.
- **TypeScript build errors surface in Docker builds**: When `pnpm run build` runs `type-check` before `vite build`, any missing type (removed field, wrong import) blocks the entire Docker build. Fix the code, then rebuild. Don't disable type-checking to work around it.
- **Vite terser not found in v3+**: Since Vite v3, `terser` is an optional dependency. If `vite.config.ts` has `minify: 'terser'` and `terserOptions: {...}`, the Docker build fails with `terser not found`. Fix: remove `minify: 'terser'` and `terserOptions` from the build config entirely — Vite defaults to esbuild which is built-in. Check both frontend and admin vite.config.ts files.
- **`git checkout -- .` reverts ALL changes**: When `git checkout -- .` is used to restore files, it reverts EVERYTHING — including unrelated fixes that were made in the same session. If the user asks to restore code, clarify whether they want to revert everything or just specific changes. After restoring, re-apply fixes that were collateral damage.
- **Frontend route patterns matter for link generation**: When generating URLs (RSS, share links, etc.), always check the actual frontend router definition. Vue router may use query params (`/article?id=11`) instead of path params (`/article/11`). Check `router.push()` calls in the view to confirm the pattern: `router.push({ path: "/article", query: { id: id } })` means the URL is `/article?id=11`.
- **TypeScript TS2339 from missing backend endpoints**: When frontend view calls `PhotoService.updatePhoto()` but the API service class doesn't have that method, `vue-tsc --noEmit` fails with `TS2339: Property 'updatePhoto' does not exist`. Fix: add stub methods to the API service class with TODO comments pointing to the missing backend endpoint. This unblocks the build while the backend catches up. Example:
  ```typescript
  // TODO: 后端未实现，占位方法
  static updatePhoto(data: any) {
    return request.put({ url: '/admin/image/updateImage', data })
  }
  ```
- **User correction: verify before diving deep**: When debugging an issue (e.g., "ElMessage appearing at bottom-left"), don't assume the root cause. The user may know what the actual symptom is. If your initial investigation finds nothing, STOP and ask for clarification instead of continuing to guess. In this session, I spent time checking CSS positioning when the real issue was a WelcomeMessage component re-mounting on route change.

## Spring Security: Getting Current User

```java
// In service layer
Authentication auth = SecurityContextHolder.getContext().getAuthentication();
String username = auth.getName();
Long userId = userMapper.getIdByUsername(auth.getName());
```

For admin endpoints: use SecurityContext (user must be logged in).
For public endpoints: accept userId as path parameter, no auth required.

## Pitfall: Whitelist `/api/admin/**` breaks all admin endpoints

**Symptom**: All admin endpoints return 401 "请先登录" even though the user is logged in. JWT filter debug log shows "白名单匹配成功" (whitelist match succeeded).

**Root cause**: In `application-dev.yml`, the whitelist has `/api/admin/**`. The JWT filter passes whitelisted requests through WITHOUT validating the token, so `SecurityContext` is never populated. But admin service methods call `getCurrentUserId()` which reads from `SecurityContext` → returns null → 401.

**The conflict**: Whitelisting means "no auth required", but admin endpoints NEED auth to identify the current user.

**Fix**: Remove `/api/admin/**` from the whitelist. Only whitelist specific endpoints that truly don't need auth (login, register, captcha, public front APIs). Dev and prod whitelists should be identical for admin endpoints.

**Debugging**: When 401 appears on admin endpoints, check TWO layers:
1. JWT filter (does it pass through or reject?) — add `logger.debug` to see whitelist matching
2. Service layer (does `getCurrentUserId()` return null?) — if filter passes but service returns 401, the whitelist is too broad

## Pitfall: Java regex `\\\\d` vs `\\d` in Pattern.compile

```java
// WRONG — \\\\d in Java source = \\d in regex = literal backslash + d
Pattern.compile("(?::\\\\d{1,5})?")

// RIGHT — \\d in Java source = \\d in regex = digit
Pattern.compile("(?::\\d{1,5})?")
```

In Java string literals: `\\` is escape for one `\`. So `\\\\d` = two actual backslashes + `d` (literal `\d` in regex, NOT digit class). This breaks URL prefix stripping silently — the regex still compiles, but port numbers like `:9007` don't match, leaving the full URL in the database.

**Detection**: If `UrlNormalizeUtil.stripUrlPrefix` returns the original URL unchanged, check the regex escaping.

## Pitfall: MinioResponseAdvice + @MinioFile auto URL conversion

The blog project has `MinioResponseAdvice` (ResponseBodyAdvice) that intercepts ALL `ApiResponse` responses. It uses `MinioUrlConverter` to find fields annotated with `@MinioFile` and prepends `file.public-base-url` (e.g., `http://127.0.0.1:9007`).

**Flow**: DB stores relative path → `@MinioFile` on DTO field → `MinioResponseAdvice` auto-prepends prefix → frontend gets full URL.

**Don't duplicate**: If a DTO field has `@MinioFile`, the frontend should use the URL as-is. Don't add frontend-side URL resolution for fields that already have the annotation. Check `MinioResponseAdvice.java` and `MinioUrlConverter.java` before adding frontend URL helpers.

## References
- `references/blog-settings-migration-example.md` — Concrete example of single-site→multi-user migration
- `references/http-interceptor-silent-pattern.md` — Silent API calls for expected errors
- `references/rss-implementation-pattern.md` — RSS 2.0 feed implementation (Java DOM API, no library needed)
- `references/folder-upload-webkitdirectory.md` — Browser folder upload: webkitdirectory, directory tree preview, batch upload with progress, Spring Boot MultipartFile[] binding
- `references/pre-upload-storage-validation.md` — Pre-upload disk space + user quota check pattern: StorageInfo DTO, server-side validation, frontend three-touch-point UX
- `references/rich-editor-integration.md` — WangEditor customUpload, md-editor-v3 DOM injection for dropdown extension, NormalToolbar/DropdownToolbar usage, MinIO URL strategy

## Adding a New Full-Stack Feature (Image Picker Example)

When adding a reusable feature that spans the full stack (backend API → frontend component → multiple integration points), follow this layering order:

### Step 1: Backend — bottom-up
1. **Mapper interface**: Add new query method with `@Param` annotations
2. **Mapper XML**: Add SQL with proper `<where>` / `<if>` dynamic conditions
3. **Service interface**: Add method declaration
4. **Service implementation**: Add logic (keep thin — delegate to mapper)
5. **Controller**: Add endpoint (`@GetMapping` for queries, `@PostMapping` for mutations)

### Step 2: Frontend API layer
6. **API service class**: Add static method matching backend endpoint

### Step 3: Frontend component
7. **Create reusable component** in `src/components/Widgets/<Name>/index.vue`
   - Use `el-dialog` for modal presentation
   - Grid layout with `el-image` for previews
   - Search bar + reset + upload button
   - `v-model` for dialog visibility, `@select` event for result
   - Cast API response: `(res.result || []) as ItemType[]` to fix TS inference

### Step 4: Integration points
8. **Add to each consuming view**: Import component, add state (`showXxx = ref(false)`), add handler, add trigger button
9. **Environment variables**: If the feature needs external URLs (e.g., MinIO base URL), add to BOTH `.env.development` AND `.env.production`

### Pitfall: MinIO URL configuration
Image URLs stored in DB are relative paths like `/my-bucket/xxx.jpg`. The frontend needs a `VITE_MINIO_URL` env var to construct full URLs. Without it, images load from the wrong origin. Development uses `http://localhost:9007` (host-mapped port), production uses the MinIO domain.

### Pitfall: TypeScript response type casting
API responses typed as `ApiResponse<T>` may not infer `T` correctly when the result is an array. Use explicit cast: `imageList.value = (res.result || []) as ImageItem[]`. Without this, `vue-tsc` reports `TS2322: Type '{}' is not assignable`.

## Rich Text / Markdown Editor Integration

### WangEditor (wangeditor/editor-for-vue)

**Problem**: WangEditor's `server` upload mode expects `{ errno: 0, data: { url } }`. Backend returning `{ code: 200, result: { imageUrl } }` won't insert the image.

**Fix**: Use `customUpload` instead of `server`:
```typescript
uploadImage: {
  async customUpload(file: File, insertFn: Function) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(server, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData
    }).then(r => r.json())
    if (res.code === 200) {
      insertFn(res.result.imageUrl, '', res.result.imageUrl)
    }
  }
}
```

### md-editor-v3

**Problem**: The image dropdown (上传图片/添加链接/裁剪上传) is built-in, NOT extensible via props.

**Fix**: DOM injection after render — find `.md-editor-menu-item-image` elements and append a new `<li>`:
```typescript
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
watch(() => editorRef.value, () => nextTick(injectLibraryOption))
onMounted(() => nextTick(() => setTimeout(injectLibraryOption, 500)))
```

**`NormalToolbar`**: use `:onClick` prop (not `@onClick` event). Always provide `#trigger` slot with visible icon — without it the button renders but is invisible.

**`onUploadImg` callback**: backend returning `{ code: 200, result: { imageUrl } }` → `callback([res.result.imageUrl])`, not `res.data.url`. Ensure `Authorization: Bearer ${accessToken}` (with Bearer prefix).

## Relative Path vs Full URL (MinIO Storage)

DB stores relative paths (`my-bucket/xxx.jpg`), browser needs full URLs (`http://host:port/my-bucket/xxx.jpg`).

`MinioUtil`: `getPermanentRelativeFileUrl` → DB, `getPermanentFileUrl` → frontend display.

**Critical**: Reusable components (ImagePicker) must emit full URLs via display helper, not raw DB `filePath`. Otherwise Markdown preview and `<img>` tags fail. `VITE_MINIO_URL` env var needed in both `.env.development` and `.env.production`.

## Pitfall: Public endpoints that internally need userId

When adding a public endpoint (e.g., `getFrontInfo` for favicon) that internally calls `getCurrentUserId()`, it returns null → 401 because there's no SecurityContext for unauthenticated requests.

**Wrong**: `blogSettingService.getSomeFrontInformation()` — calls `getCurrentUserId()` internally.

**Right**: `blogSettingService.getSomeFrontInformationById(1L)` — bypasses auth, uses default userId. For single-user blogs, hardcoding userId=1 is acceptable for public display endpoints.

**Pattern**: Public endpoints should call `getXxxById(userId)` directly, not `getXxx()` which wraps it with auth checks.

## User Workflow Preferences (CRITICAL)

1. **Verify UI visually**: Use `browser_navigate` + `browser_vision` before asking the user about visual issues. NEVER ask "你在浏览器看看" — do it yourself.
2. **Understand existing code first**: If the project already handles relative paths or URL conversion, find and use that code. Don't add redundant utilities.
3. **Targeted git checkout only**: `git checkout -- .` reverts ALL changes including valid fixes. Always specify individual files.
4. **Don't over-abstract**: If backend has URL conversion utilities, use them. Don't create new frontend files for existing functionality.
5. **Debugging loops**: When user says "为什么这么久" or "停止", stop immediately. Don't keep restarting services or adding debug logging in loops. Step back, think about what the evidence already shows, then make ONE targeted fix.
6. **Fix, don't diagnose**: User expects working code, not investigation reports. If you know the root cause, fix it directly. Don't say "the issue is X, you should do Y" — just do Y.

## File Naming Patterns

- Entity: `src/main/java/.../entity/Xxx.java`
- Mapper interface: `src/main/java/.../mapper/XxxMapper.java`
- Mapper XML: `src/main/resources/mapper/XxxMapper.xml`
- Service: `src/main/java/.../service/XxxService.java` + `impl/XxxServiceImpl.java`
- Controller: `src/main/java/.../controller/admin/AdminXxxController.java` (admin) + `controller/front/FrontXxxController.java` (public)
- Frontend API: `src/api/xxxApi.ts`
- Frontend types: `src/types/xxx.ts` or `src/types/xxx/xxx.d.ts`
- Frontend views: `src/views/xxx/index.vue`
