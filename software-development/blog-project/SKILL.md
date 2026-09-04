---
name: blog-project
description: Use when working on the 拾感日记 blog project (SB3+Vue3+MinIO).
---

# Blog Project (拾感日记) Development Guide

Spring Boot 3.4 + Vue3 + Docker + MinIO personal blog system.

## Quick Reference

- **Local**: API:8080, Admin:8888, Front:3000, MinIO:9007/9008
- **Remote**: SSH -p 20225 luosg@39.97.180.240
- **Deploy**: `bash publish/remote.sh` (local build+upload), then remote `cd /home/luosg/blog && bash remote_publish.sh`
- **GitHub**: ShiganLuo/blog

## Architecture

### Image Storage Pattern (CRITICAL)

Database stores **relative paths** (e.g. `my-bucket/uuid.png`). Full URLs are constructed dynamically:

1. **Write path**: `UrlNormalizeUtil.stripUrlPrefix()` strips domain before DB insert
2. **Read path**: `@MinioFile` annotation on DTO fields + `MinioResponseAdvice` auto-prepends `file.public-base-url`

**Gotchas**:
- `@MinioFile` does NOT work on `List<String>` — the `MinioUrlConverter` skips simple types. For image arrays, manually convert in service layer (strip on save, `minioUtil.getFullUrl()` on read).
- `UrlNormalizeUtil` regex: in Java source code `\\\\\\\\d` = `\\\\d` in string = `\\d` in regex (digit). Single `\\\\d` in source = `\\d` in string = invalid Java escape!
- **Regex port matching**: The port group `(?::\\\\\\\\d{1,5})?` must match `:9007`. If regex fails, `stripUrlPrefix` returns the original URL unchanged → double URL in DB. Always test with `http://localhost:9007/path` format.
- ALL image-setting code paths must call `stripUrlPrefix()`. Checked locations: `ArticleServiceImpl` (new + update), `UserServiceImpl` (avatar upload + user info update), `BlogSettingServiceImpl` (8 fields including wechatQrCode, alipayQrCode), `FriendLinkServiceImpl`.
- **Double URL symptom** (`http://x:9007http://y:9007/...`): Means `stripUrlPrefix` regex failed to match, full URL stored in DB. Fix regex, then UPDATE existing bad rows in DB.

### JWT Authentication

- **Dual tokens**: Access (1h) + Refresh (14d)
- **Whitelist**: `/api/admin/**` must NOT be in whitelist — it causes ALL admin endpoints to skip auth, leaving `SecurityContext` empty, so `getCurrentUserId()` returns null → 401
- **Frontend**: Both admin and front HTTP interceptors add `Authorization: Bearer ${accessToken}`
- **el-upload `:action` mode**: Does NOT go through axios interceptor! Must manually pass `:headers="{ Authorization: \`Bearer \${accessToken}\` }"` on every el-upload that uses `:action`

### Comment Type System

Comments and talks share the `comments` table, differentiated by `type`:

| type | Description | for_id | root_id |
|------|-------------|--------|---------|
| `post` | Article root comment | article_id | article_id |
| `comment` | Child comment (any depth) | parent_comment_id | root_comment_id |
| `talk` | Talk/说说 itself (NOT a comment) | NULL | NULL |
| `talk_comment` | Talk root comment | talk_id | talk_id |

Querying talks: `WHERE type='talk'` (excludes talk comments).
Querying article comments: `WHERE root_id=X AND type IN ('post','comment')`.
Querying talk comments: `WHERE root_id=X AND type IN ('talk_comment','comment')`.

**ParentItem publish logic**: Root comments use `props.type` (e.g. `talk_comment`), child comments use `"comment"`. Pattern: `type: data.forId ? "comment" : props.type`.

### el-upload and Authorization Header

el-upload with `:action` mode sends requests directly, **NOT through axios interceptor**. Every el-upload using `:action` must have:
```
:headers="{ Authorization: `Bearer ${accessToken}` }"
```
Common bug: writing `Authorization: accessToken` without `Bearer ` prefix → JWT filter returns 401 "请求未携带accessToken".

**Subtle override bug**: If an API function passes `headers: { 'Content-Type': undefined }` in the request config (to let axios auto-set multipart boundary), this can create a NEW headers object that doesn't include the Authorization header set by the interceptor. The `uploadPhoto` function in `photoApi.ts` had this exact bug — removing the custom `headers` config fixed it.

### ImagePicker Component

- Emits full URLs (not relative paths) via `getImageDisplayUrl(filePath)`
- Used in: Editor toolbar, MarkdownEditor, article cover, website settings (8 uploaders), friend link cover, album cover, talk
- **Click behavior**: `el-image` with `preview-src-list` opens enlarged preview on click. For ImagePicker (click-to-select), REMOVE `preview-src-list` so click only triggers parent div's `@click="handleSelect"`
- **Integration pattern**: For each upload scenario, add:
  1. `import ImagePicker from '@/components/Widgets/ImagePicker/index.vue'`
  2. State: `const showImagePicker = ref(false)` + handler `const handleImageSelect = (image) => { /* set field */ }`
  3. Button next to upload area: `<el-button @click="showImagePicker = true">素材库</el-button>`
  4. Component: `<ImagePicker v-model="showImagePicker" @select="handleImageSelect" />`
- **md-editor-v3 toolbar**: Cannot extend image dropdown via props. Use DOM injection to add "从素材库选择" as 4th option in the existing image dropdown menu after mount.

### Image Upload Type Support

`ImageFileUtil.generateUniqueImageName()` validates by magic number:
- jpg (`FFD8FF`), png (`89504E47`), gif (`47494638`), bmp (`424D`), ICO (`00000100`) — via magic number
- SVG — no magic number, detected by content (`<svg` or `xmlns` in first 100 bytes)

### CommentType TypeScript Type

When adding new comment types, THREE places must be updated in the frontend:

1. `types/comment.ts` — add to `CommentType` union: `"post" | "comment" | "talk" | "talk_comment"`
2. `components/Comment/index.vue` — update the `type` prop definition to match
3. `components/Comment/item/ParentItem.vue` — the `publish` handler uses `type: data.forId ? "comment" : props.type`, which relies on `props.type` being the correct root type

If these don't match, TypeScript build fails with `Type 'xxx' is not assignable to type '...'`.

### Talk Page Type Distinction

The talk page has TWO different `type` usages that must not be confused:

1. **Talk list query param**: `type: "talk"` — fetches talks themselves (type='talk' in DB)
2. **Comment component prop**: `type="talk_comment"` — used for rendering comments on talks

The `const param` for fetching the talk list must stay `"talk"`. Only the `<Comment type="talk_comment">` uses `"talk_comment"`. Accidentally changing the list param to `"talk_comment"` causes talks to disappear.

### Photo Album Feature

Implemented with junction table pattern:

**Tables**:
- `photo_album`: id, album_name, description, album_cover, sort_order, is_visible
- `photo_album_images`: id, album_id (FK→photo_album), image_id (FK→images), sort_order, UNIQUE(album_id, image_id)

**Backend**:
- `PhotoAlbumMapper.xml`: `selectAllAlbums` (with photo_count subquery), `selectAlbumById` (with nested collection for photos), `insertAlbum`, `updateAlbum`, `deleteAlbum`, `insertAlbumImage`, `deleteAlbumImage`
- `PhotoAlbumServiceImpl`: CRUD + image association, uses `UrlNormalizeUtil.stripUrlPrefix` for album_cover
- `FrontPhotoAlbumController`: `/api/front/photoAlbum/list`, `/{id}`
- `AdminPhotoAlbumController`: `/api/admin/photoAlbum/{list,add,update,delete/{id},addImage,removeImage}`

**Frontend API** (`photoApi.ts`):
- `getAllAlbum()`, `getAlbumById(id)`, `adminGetAllAlbum()`, `addAlbum()`, `updateAlbum()`, `deleteAlbum()`, `addImageToAlbum()`, `removeImageFromAlbum()`

**Admin routes** (asyncRoutes.ts):
- `/photo` → parent route
- `/photo/index` → album list (photo/index.vue)
- `/photo/photo/:albumId` → album detail with photos (photo/photo.vue, isHide:true)

**Design**: Images and albums are independent. `images` table stores ALL images (素材库 + album photos). `photo_album_images` only links specific images to albums. Images without junction records are pure 素材库 images.

### art-table Selection Column

`art-table` with `selection` prop auto-adds a checkbox column. Do NOT also add `<el-table-column type="selection" />` inside the template — it creates duplicate columns.

### Comment Type Display

Database stores type as string (`'post'`, `'comment'`, `'talk'`, `'talk_comment'`, `'message'`), NOT numbers. Template must use `=== 'post'` not `== 1`.

### CommentConvertUtil.buildCommentTree()

When adding new comment types, `CommentConvertUtil.buildCommentTree()` MUST be updated. It only recognizes specific type strings as root comments. Currently handles: `post`, `talk`, `talk_comment` as roots, `comment` as children. Any new type that should be a root comment must be added to the condition:

```java
if ("post".equalsIgnoreCase(a.getType()) || "talk".equalsIgnoreCase(a.getType()) || "talk_comment".equalsIgnoreCase(a.getType())) {
    roots.add(current);
}
```

Without this, new comment types are silently dropped from the tree — they exist in DB but never render.

### Frontend Patterns

- **API classes**: Static methods on service classes (e.g. `PhotoService.uploadPhoto(data)`)
- **Pinia store**: Use `res?.result || res` to unwrap `ApiResponse`
- **Favicon**: Frontend `app-init.ts` calls `/api/front/settings/getFrontInfo` on load (no auth required). Returns favicon with `@MinioFile` auto-conversion. Backend controller uses hardcoded `userId=1L` for this public endpoint.
- **md-editor-v3 image dropdown**: Cannot extend via props. Use DOM injection to add custom options to the existing dropdown menu after mount.
- **ImagePicker component**: Emits full URLs (not relative paths) via `getImageDisplayUrl()`. Used in: editor, article cover, website settings (8 uploaders), friend link cover, album cover, talk.
- **Notifications**: Use `ElMessage` (lightweight toast, top center) for ALL operation feedback. Do NOT use `ElNotification` (card-style popup, appears in corner). The project migrated all `ElNotification` calls to `ElMessage.success/error/warning`. `h()` virtual DOM rendering is unnecessary — just pass strings directly.

### Deployment

- `remote.sh`: Builds Docker images locally, exports as .tar, SCPs to remote
- `remote_publish.sh`: Loads images, recreates containers
- Nginx double-proxy: nginx-proxy → blog_admin:80 → backend:8080
- Both nginx layers need `proxy_set_header Authorization $http_authorization;` for JWT to work through proxy

See also: `references/bioplatform-deployment.md` for bioplatform partial deploy workflow.

## Common Pitfalls

See also: `references/batch-replacement-pitfalls.md` for batch regex replacement patterns.
See also: `references/remote-disk-cleanup.md` for disk-full diagnostics and Docker resource cleanup.

1. **401 on admin APIs after login**: Check dev whitelist has `/api/admin/**` — remove it! It bypasses JWT for ALL admin endpoints, leaving `SecurityContext` empty.
2. **401 "请求未携带accessToken" on image upload**: el-upload `:action` mode doesn't use axios interceptor. Add `:headers="{ Authorization: `Bearer ${accessToken}` }"` to el-upload. Also check that custom `headers` config in API functions doesn't override the interceptor's Authorization.
3. **Double URL** (`http://x:9007http://y:9007/...`): `stripUrlPrefix` regex broken, full URL stored in DB. Fix regex, then UPDATE existing bad rows.
4. **Favicon not updating on front page**: `app-init.ts` must call `/api/front/settings/getFrontInfo` (no auth, defaults userId=1). The old `getSomeFrontInformation/{userId}` requires login.
5. **`cat -A` shows `***`**: It's actually a backtick (`` ` ``). Use `python3 -c "print(repr(line))"` to verify actual content.
6. **Build verification**: Don't assume changes work — always verify with actual curl/browser test against the deployed environment, not just local build. The user is very particular about this: "不要自以为修改好了". Test the actual endpoint, verify the response, then claim success.
7. **Comment management empty**: Default filter is `status: -1` (全部/all). Status values: -1=all, 0=pending, 1=approved, 2=rejected. Backend mapper uses `<if test="status != null and status >= 0">` to skip filter when -1.
8. **Talk comments appearing as talks**: If `type='talk'` with `for_id != NULL`, it's a comment not a talk. Use `type='talk_comment'` for talk root comments.
9. **README security**: Don't include server IPs, ports, SSH commands, or deployment details in README if `publish/` is gitignored. Public repo = no private infrastructure info.
10. **Duplicate selection columns**: `art-table` with `selection` prop already adds checkbox column. Don't add manual `<el-table-column type="selection" />`.
11. **Don't delete data without asking**: User corrected me for deleting a test record from the database without asking. Always ask before destructive operations.
12. **User frustration signals**: When user says "你在思考什么", "停止", "为什么这么久" — stop immediately and wait for direction. Don't continue debugging loops.
13. **"检查出问题后向我报告原因"**: User wants diagnosis FIRST, then report findings. Don't ask "what do you see?" or "can you check?" — investigate yourself (browser, curl, DB, logs), then report the root cause. The user expects you to USE your tools to diagnose, not delegate diagnosis back to them.
14. **Don't look at remote when local is available**: User said "你查看远程页面干啥,本地不是优服务吗". When debugging, prefer local environment first — it's faster and you have full access. Only go remote for deployment verification.
15. **Duplicate imports**: After batch regex replacements (e.g. `ElNotification` → `ElMessage`), always check for duplicate import statements. Pattern: `import { ElMessage } from "element-plus";\nimport { ElMessage } from "element-plus";` causes build failure. Also check for unused `h` import if `h()` virtual DOM calls were removed.
16. **el-image preview-src-list**: When `el-image` has `preview-src-list`, clicking opens enlarged preview. For click-to-select scenarios (like ImagePicker), remove `preview-src-list` so click only selects.
17. **Element Plus programmatic CSS**: `ElMessageBox.confirm()` and `ElMessage()` are programmatic calls — `unplugin-vue-components` doesn't auto-import their CSS. Must add `import 'element-plus/theme-chalk/el-message-box.css'` and `import 'element-plus/theme-chalk/el-message.css'` in `main.ts`. Without this, dialogs appear unstyled in top-left corner.
18. **Don't delete data without asking**: Already covered in #11 above. (duplicate removed - keeping as reference)
19. **Code changes ≠ deployed**: Pushing to git doesn't mean the remote is updated. Must run `remote.sh` + `remote_publish.sh` to deploy. Always verify the deployed state, not just the committed state.
20. **Checkbox alignment**: Element Plus `el-checkbox__inner::after` positioning with `left:0; right:0; top:0; bottom:4px; margin:auto` causes vertical misalignment. Fix: use `left:50%; top:50%; transform:translate(-50%, -60%) rotate(45deg)` for precise centering. In `el-ui.scss`.
21. **Image path missing leading `/`**: DB records with `my-bucket/xxx.jpg` (no `/`) cause URLs like `https://minio.shiganluo.topmy-bucket/xxx.jpg`. `stripUrlPrefix` now ensures result starts with `/`. Existing bad rows need `UPDATE images SET file_path = CONCAT('/', file_path) WHERE file_path NOT LIKE '/%';`
22. **Child route for detail pages**: When adding a detail page under a parent route (e.g. album detail under photo), the child route needs `isHide: true` in meta so it doesn't appear in the sidebar menu.
23. **TypeScript `res.result` is `unknown`**: When API response type isn't narrowed, cast with `res.result as SomeType[]` or `res.result as any`. Common after changing API endpoints.
24. **Don't delete data without asking**: User corrected me for deleting a test record from the database without asking. Always ask before destructive operations.
25. **ArtTable row highlight border**: When table rows have a selection indicator line that appears misaligned (too high), add CSS to remove the bottom border on selected rows: `td.el-table__cell { border-bottom: none !important; }` scoped under `.el-table__body-wrapper .el-table__row`.
26. **Loading indicators**: The "coffee cup" icon the user sees is the project's loading/skeleton indicator, not a bug. Don't report it as an issue.
27. **Route comma syntax**: When replacing commented-out route blocks in `asyncRoutes.ts`, ensure the preceding route object ends with `,` before the new route starts. Missing comma causes `TS1005: ',' expected` at the opening `{` of the new route.
28. **`.env` file corruption**: When appending to `.env` files with `echo >>`, if the last line doesn't end with newline, new content merges with last line (e.g. `VITE_ADMIN_BASE_URL = https://back.shiganluo.topVITE_MINIO_URL = https://minio.shiganluo.top`). Always use `write_file` to rewrite the entire file, or verify newlines before appending.
29. **Page rewrite click handler loss**: When rewriting Vue pages, critical interactive elements (click handlers, router.push calls) can be accidentally omitted. After rewriting, verify ALL user interactions work — not just that the page renders. Pattern: grep for `@click`, `router.push`, `router.replace` in the OLD version before rewriting.
30. **API response format mismatch**: When changing API endpoints, verify the response structure matches what the frontend expects. Example: `getAlbumDetail` returns `{id, albumName, photos: [...]}` but old code expected `{list: [...], total: N}`. Always check the backend controller's return type vs the frontend's `res.result.xxx` access pattern.
31. **Field naming mismatch after API migration**: When switching from old API to new API, field names may differ (e.g. old `photoSrc`/`photoName` vs new `filePath`/`fileName`). After changing API endpoints, grep the template for ALL field references and verify they match the new response structure. Common pattern: old APIs used camelCase DTOs, new APIs may use snake_case DB columns.
32. **Photo management image display**: Images from `getAlbumDetail` API return `filePath` (relative path like `/my-bucket/xxx.jpg`). Template must use `getFullUrl(item.filePath)` not `item.photoSrc`. The `getFullUrl` function prepends `VITE_MINIO_URL` env var.
33. **ImagePicker in photo management**: Adding images from 素材库 to albums requires calling `PhotoAlbumService.addImageToAlbum(albumId, imageId)` after selection, then refreshing the photo list. The ImagePicker emits `{url, id}` — use `image.id` for the association API.
34. **MinIO upload "minimum free drive threshold"**: This is a DISK FULL error on the server, not a MinIO config issue. MinIO refuses writes when the underlying filesystem has too little free space. Diagnose with `df -h /` first. Common cause: Docker volumes and images accumulating over deployments. Fix: `docker volume prune -f` + `docker image prune -a -f`. Verify containers use bind mounts (not named volumes) before pruning. See `references/remote-disk-cleanup.md` for full diagnostic workflow.
35. **MyBatis XML alias/column errors**: SQL error `Unknown column 'c.name' in 'where clause'` means the mapper XML uses a table alias (e.g. `c.name`) but the FROM clause has no alias defined. Fix: either add the alias `FROM tags c` or remove the prefix. Also check for references to columns that don't exist in the table — cross-reference with `<resultMap>` definitions to verify column names. Diagnostic: `grep -rn "c\.\|t\.\|a\." mapper/*.xml` to find all alias usages, then verify each SELECT defines the corresponding alias.
36. **Frontend-backend parameter name mismatch (SILENT FAILURE)**: When the frontend sends `@RequestBody` POST parameters that don't match the backend DTO record field names, Jackson silently deserializes them as `null`. The `<where>` / `<if>` in MyBatis skips null fields, so searches return ALL records instead of filtered results. No error is thrown — the search just "doesn't work". Critical mismatches found in this project:
    - **Tag/Category list pages**: Frontend sent `{current, size, keywords}`, backend DTOs expect `{pageNum, pageSize, keyword}`. Fix: rename frontend `queryParams` fields to match DTO. Also fix pagination bindings: `:current-page="queryParams.pageNum"`, `:page-size="queryParams.pageSize"`.
    - **Article list page**: Frontend sent `{keywords}`, backend `CreateAdminArticlePageRequest` expects `{keyword}`. Note: article DTO uses `current`/`size` (NOT `pageNum`/`pageSize`) — each DTO is different!
    - **Diagnostic**: When search/pagination doesn't work, check backend DTO field names (`grep -A15 "record.*Request" *DTO.java`) vs frontend `queryParams` reactive object. Every field must match exactly.
37. **handleCurrentChange copy-paste bug**: When adding pagination to a list page, `handleCurrentChange` must set `queryParams.pageNum = page` (or `queryParams.current = page` for article DTO), NOT `queryParams.size = page`. This is a common copy-paste error from `handleSizeChange` that silently breaks pagination — clicking next page changes page size instead of page number.
38. **Remote server docker-compose version**: The remote server (39.97.180.240) uses `docker-compose` (hyphen, v1 syntax), not `docker compose` (space, v2). Commands like `docker-compose -f docker-compose-remote.yml up -d web admin` must use the hyphenated form.
39. **SCP "Received message too long"**: Remote `.bashrc` prints output (e.g. `proxy off`) that corrupts SCP protocol. Fix: use pipe transfer: `cat file.tar | ssh -p PORT user@host "cat > /remote/path/file.tar"`.
40. **Incremental single-image deploy**: When only one frontend service changed, skip full `remote_publish.sh`. Build/export/upload/restart only the changed image:
    ```bash
    docker build -t bioplatform-admin ./bioplatform-vue3/bioplatform-admin
    docker save bioplatform-admin -o /tmp/bioplatform-admin.tar
    cat /tmp/bioplatform-admin.tar | ssh -p 20225 user@host "cat > /home/luosg/bioplatform/bioplatform-admin.tar"
    # Remote: docker load -i bioplatform-admin.tar && rm -f bioplatform-admin.tar
    # Remote: docker-compose -f docker-compose-remote.yml up -d admin
    rm -f /tmp/bioplatform-admin.tar
    ```
39. **Admin blank page on first visit from frontend (validateStorageData timing bug)**: When the frontend opens the admin app via `window.open(VITE_ADMIN_BASE_URL)`, the page is blank but works after refresh. Root cause: the admin app's initialization has a timing conflict between the router guard and `App.vue`'s `onMounted`. The flow: (1) Store constructor reads token from frontend's localStorage via `getFrontendToken()` → `accessToken` is valid. (2) Router guard (`beforeEach`) finds the token → calls `getMenuData()` which shows a loading overlay + 300ms `setTimeout` delay. (3) During this 300ms, `App.vue`'s `onMounted` fires → calls `initState()` → `validateStorageData()` → finds no `sys-v*` data in localStorage (first visit) → calls `logOut()` → **clears the token**. (4) After 300ms, guard's `next()` completes navigation, but token is already empty. (5) Next navigation: guard sees no token → redirects to login → blank page. Fix: in `storage.ts`, change `validateStorageData()` to return `true` (not call `logOut()`) when localStorage is empty — empty localStorage is normal on first visit, not an error condition. The data corruption path (`!validate(data, schema)`) still correctly calls `logOut()`.
40. **Blank pages from dual transition blocks**: The Home layout (`views/index/index.vue`) must NOT have two separate `<transition>` blocks for the same `Component` with the same `:key`. The original template split rendering into keepAlive and non-keepAlive branches with `v-if="route.meta.keepAlive"` / `v-if="!route.meta.keepAlive"`, each wrapped in its own `<transition mode="out-in">`. This causes Vue to reuse DOM elements across transitions with the same key, leading to intermittent blank pages. Fix: use a SINGLE transition wrapping a SINGLE keep-alive wrapping the component WITHOUT v-if splits:
   ```vue
   <transition :name="pageTransition" mode="out-in" appear>
     <keep-alive :max="10" :exclude="keepAliveExclude">
       <component :is="Component" :key="route.path" />
     </keep-alive>
   </transition>
   ```
   `keep-alive` naturally skips non-cached components (keepAlive:false in route meta), so no v-if is needed.
41. **asyncRoutes absolute child paths cause blank pages**: In `asyncRoutes.ts`, child route paths that start with `/` are ABSOLUTE in Vue Router 4 — they match `/#/comment` not `/#/message/comment`. But `processRoute()` in `utils/menu.ts` always prepends the parent path when building menu links, generating `/message/comment`. Result: menu link points to `/message/talk` but the route is registered at `/talk` → Vue Router can't match → blank or 404 page. **Rule**: ALL child paths in `asyncRoutes.ts` must be RELATIVE (no leading `/`). Pattern: `path: 'comment'` not `path: '/comment'`. Affected routes: message children (`/comment`→`comment`, `/talk`→`talk`), website children (`/info`→`info`, `/link`→`link`). This also applies to any future routes added to `asyncRoutes.ts`.
42. **getMenuData() ElLoading overlay stuck on error**: `menuService.getMenuList()` creates an `ElLoading.service({lock: true})` overlay and returns `closeLoading` as part of the result. If `registerAsyncRoutes()` throws (e.g., route name conflict or component load failure), the original `getMenuData()` had no try-finally, so `closeLoading()` was never called. The transparent fullscreen overlay stays forever → page appears blank, user can't interact. Fix: wrap the route registration logic in `try { ... } finally { closeLoading() }`. Also fix the original bug where `logOut()` was called but execution continued (no `return` after `logOut()` in the empty-menuList check).
