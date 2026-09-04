# Vue SFC Corruption Incident — Blog Multi-User Migration

## Date
2026-06-14

## What Happened

During a multi-user blog migration, batch file modifications using
`execute_code` with `write_file` inside a loop silently emptied 9 files:

### Corrupted Files (0 lines after edit)
1. `src/views/article/article-list.vue` (was 202 lines)
2. `src/views/category/category.vue` (was 123 lines)
3. `src/views/archives/archives.vue` (was 101 lines)
4. `src/views/photo/photo-album.vue` (was 152 lines)
5. `src/views/tag/tag.vue` (was 129 lines)
6. `src/views/photo/photos.vue` (was 263 lines)
7. `src/views/resources/site-list.vue` (was 262 lines)
8. `src/views/resources/category-list.vue` (was 236 lines)
9. `src/app-init.ts` (was 12 lines)

### Files Modified Safely (using patch)
- `src/api/configApi.ts` — OK
- `src/types/config.ts` — OK
- `src/views/home/HomeView.vue` — OK (used patch)
- `src/layout/footer/blog-footer.vue` — OK (used patch)
- `src/components/PageHeader/home-header.vue` — OK (used patch, then
  write_file corrupted it, then git checkout restored it, then patch fixed it)

## Error Symptoms

Vite dev server error:
```
At least one <template> or <script> is required in a single file component.
/home/.../home-header.vue
```

## Root Cause

The `write_file` tool, when called from within `execute_code` Python loops,
can fail to serialize the content properly and writes an empty file instead.
This is especially common with:
- `.vue` files (contain mixed HTML/JS/CSS with special characters)
- Large files (>100 lines)
- Files with template literals or complex string content

## Recovery

```bash
# Restore all corrupted files
git checkout -- src/views/article/article-list.vue \
  src/views/category/category.vue \
  src/views/archives/archives.vue \
  src/views/photo/photo-album.vue \
  src/views/tag/tag.vue \
  src/views/photo/photos.vue \
  src/views/resources/site-list.vue \
  src/views/resources/category-list.vue \
  src/app-init.ts
```

## Correct Approach Used After Recovery

All modifications done with `patch` tool:
```python
# Each file: 3 patch calls
patch(f, 'import line', 'import line + useUserStore import')
patch(f, 'first const', 'userStore init + first const')
patch(f, 'ConfigService.getFrontBackground()', 
      'ConfigService.getFrontBackground(userStore.getUserInfo.id || 1)')
```

## Prevention Rule

NEVER use `write_file` in a loop inside `execute_code`. Always use `patch`.
