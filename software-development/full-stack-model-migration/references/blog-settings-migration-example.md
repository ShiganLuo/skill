# Blog Settings Multi-User Migration — Concrete Example

## What Changed

Converted `blog_settings` table from single-site (1 record, hardcoded id=1) to multi-user (1 record per user).

## Backend Changes (10 files)

### Entity
- `BlogSetting.java`: added `userId` field, fixed `multiLanguage` type String→Integer

### Mapper
- `BlogSettingMapper.java`: removed duplicate `getSettingById(long)`, added `getSettingByUserId(Long)`, `updateSettingFull()`, `deleteSettingByUserId(Long)`
- `BlogSettingMapper.xml`: added `userId` to resultMap, added `getSettingByUserId` select, added `updateSettingFull` (全量更新), added `deleteSettingByUserId`

### SQL
- `blog.sql`: added `user_id BIGINT NOT NULL`, UNIQUE KEY, FOREIGN KEY ON DELETE CASCADE

### DTO
- `AdminBlogSettingDTO.java`: fixed typo `authroPersonalSay` → `authorPersonalSay`

### Service
- `BlogSettingServiceImpl.java`: 
  - Added `getCurrentUserId()` helper using SecurityContext + UserMapper.getIdByUsername
  - All hardcoded `1L` replaced with current user's ID
  - Added null-safety checks everywhere
  - `updateSetting` now uses `updateSettingFull` (allows clearing fields)
  - Added `getSettingByCurrentUserAdmin()` for admin endpoints
  - Added `getSomeFrontInformationById(Long)` and `getFrontBackgroudById(Long)` for front endpoints
- `BlogSettingService.java`: added new method declarations

### Controller
- `AdminBlogSettingController.java`: `getBlogConfig` now calls `getSettingByCurrentUserAdmin()`, removed duplicate `addView`
- `FrontBlogSettingController.java`: all endpoints now accept `@PathVariable userId`

## Frontend Changes (17 files)

### API Layer
- `configApi.ts`: all methods now accept `userId` parameter, URLs include `/{userId}`

### Types
- `types/config.ts`: added `userCount`, `blog_intro`, `ali_pay`, `we_chat_pay`, `icpFilingNumber`, `psbFilingNumber`
- `back/src/types/website/website.d.ts`: added `authorPersonalSay`, `bilibili`, `qqGroup`, `wechatGroup`, `touristAvatar`, `websiteIntro`; removed `isReward`

### Views (14 files)
- All `.vue` files calling `ConfigService.getFrontBackground()` → `getFrontBackground(userId)`
- Files without store import: added `import { useUserStore }` + `const userStore = useUserStore()`
- `app-init.ts`: added store import, skip if userId not available
- `link-list.vue`: updated both `homeGetConfig` and `getFrontBackground` calls

## Key Patterns
- Admin endpoints: use `SecurityContextHolder.getContext().getAuthentication()` → `userMapper.getIdByUsername(username)`
- Front endpoints: accept `@PathVariable userId` in URL path
- Frontend: `userStore.getUserInfo.id || 1` as fallback for userId
- Selective update (null = skip) vs Full update (null = clear to empty)
- **UI fallback defaults**: When backend data may be null/empty, add a local default asset (e.g., `import defaultBg from "@/assets/img/background.jpg"`) and use `data || defaultBg` in templates. Prevents broken image icons.

## Bugs Found During Migration
- **AdminFriendLinkController**: `@GetMapping` with `@RequestBody` → "Required request body is missing". GET has no body. Fixed: `@RequestBody` → `@ModelAttribute`. Frontend uses `params: query` (URL query string), so backend must bind with `@ModelAttribute`.
- **BlogSettingMapper.java**: duplicate `getSettingById(long)` and `getSettingById(Long)` — MyBatis can't distinguish primitive vs wrapper. Fixed: removed one, kept `Long` version.
- **Vue SFC corruption**: `write_file` in `execute_code` loop emptied 8 `.vue` files. Fixed with `git checkout -- .`. Prevention: always use `patch` for existing files, never `write_file` in loops.
- **Semantic parameter mismatch in getSettingByIdFront**: After adding `userId` column, `FrontBlogSettingController.getBlogConfig(@PathVariable userId)` called `getSettingByIdFront(userId)`, but that method internally used `blogSettingMapper.getSettingById(id)` — querying by table primary key `id` with a `userId` value. Silently returned null. Fix: changed to `getSettingByUserId(userId)`. Root cause: the method parameter was named `id` and the caller passed `userId`, a semantic mismatch that compiles fine but queries the wrong column. Always audit: does the service method query method match what the controller actually passes?
- **Background services with hardcoded IDs**: `RssService.generateRss()` used `getSettingById(1L)`, `VisitCountSyncTask.syncSiteVisitCount()` hardcoded `blogSettingId = 1L`, `RedisVisitCounter` hardcoded `blogSettingId = 1L`. None of these go through controllers, so they survive initial migration audits. Fix: accept userId parameter (RSS controller adds `@PathVariable`), scheduled tasks iterate `getAllSettings()`, Redis counters key by userId. Always grep background services after migration: `grep -rn "1L\|blogSettingId" src/main/java/ --include="*.java"`
