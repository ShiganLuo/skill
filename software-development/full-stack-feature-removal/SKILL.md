---
name: full-stack-feature-removal
version: 1.0.0
author: hermes-curator
license: MIT
description: Use when removing a whole feature across a full-stack repo.
metadata:
  hermes:
    tags: [refactoring, spring-boot, vue3, database, deletion]
    related_skills: [blog-project]
---

# Full-Stack Feature Removal

## When to Use

- The user asks to remove/delete/砍掉 an entire feature (e.g. 分类, an admin module) that spans backend services, one or more frontend apps, and database tables/seed data.
- A previous partial removal left orphaned references and builds or pages are breaking.

Removing a feature cleanly across Spring Boot + Vue apps + database. Removing is harder than adding: every leftover reference is a broken build or a dead link, and the coupling points are invisible until compile/build time.

## Workflow

1. **Triangulate touchpoints before touching anything**
   ```bash
   grep -rliE '<keyword1|keyword2>' backend/src admin-front/src user-front/src
   ```
   Then manually filter false positives. Common ones:
   - echarts `type: 'category'` (axis config, unrelated)
   - iconfont demo files, asset names, unrelated directory names sharing the word
   - the feature's own UI label appearing in resource-nav pages

2. **Delete standalone files first** (controller/service/mapper/entity/DTO per side, view pages, api modules, type files). Keep a list — the record matters for the final commit message.

3. **Clean reference holders file by file**: constructor injections, service methods, endpoint methods, DTO fields, mapper XML `<collection>` sub-selects, `<if>` filters, SQL seed rows (permissions/menus), frontend route entries, nav menu items, query params, display templates, validation checks, orphan CSS.

4. **Grep to zero**, then build every affected module (`mvn clean package`, `npm run build`) — clean builds only; incremental builds mask stale classes.

5. **Database**: schema file (for fresh installs) AND the already-initialized live DB are two separate jobs. Live DROP TABLE / DELETE seed rows are destructive — confirm with the user before executing.

## Pitfalls

- **Indexed column arrays (`columns[N].show` in art-table/element tables) couple template to array by POSITION.** Deleting one column means renumbering every later `columns[N]` in the template. Don't hand-edit: renumber by order of appearance with a script, then verify count matches the array length. Off-by-one here renders wrong column visibility silently.
- **Patch old_string on adjacent similar lines swaps the WRONG line.** Twice in one session: an import deletion removed a neighboring still-used import; a nav-menu replacement replaced the wrong sibling item. Rules: include enough surrounding context to be unique; after any edit to menus/imports/adjacent similar blocks, immediately `grep` to confirm both the deletion AND that neighbors survived.
- **Menu/nav items are duplicated** (desktop + mobile blocks in the same header component, ~90 lines apart). Remove from BOTH; grep the item's `index` value to find all sites.
- **Replaced-URL trap**: when deleting an API method that sits next to a similar one, the surviving method can end up pointing at the deleted endpoint's URL. After cleanup, re-read the whole api file and check each URL against the backend controller.
- **Field removal ripples through BOTH frontend copies of a DTO type** (admin `types/*.d.ts` AND front `types/*.ts`), plus every local `interface ArticleForm`-style inline shape. A missed `categoryNameList`-style field inside a form interface is usually harmless (backend record just ignores it), but a missed field in a fetch-render template silently renders `undefined`. Grep the field name repo-wide, not per-app.
- **Icon cleanup trap**: a feature's nav/menu may reference iconfont glyphs (`icon-sort`, `icon-folder`) that other pages still use — removing the menu item does NOT mean removing the icon; check remaining references before deleting any shared asset.
- **Schema file ≠ live DB**: `schema.sql` changes only affect fresh initialization. Already-initialized databases need manual `DROP TABLE` + seed-data cleanup (`DELETE FROM permissions WHERE permission LIKE 'x%'` plus role_permissions references) — executed only after explicit user confirmation for destructive ops.
- **Destructive step last**: sequence removal as code → build-verify → user-confirm → DB drop → deploy → verify deployed pages. Never drop tables before the code that references them is confirmed building and deployed.