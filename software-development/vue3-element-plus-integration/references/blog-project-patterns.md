# Blog Project Patterns

## Tech Stack
- Backend: Spring Boot 3.4 + MyBatis + MySQL + Redis + MinIO
- Frontend: Vue3 + Pinia + Element Plus + md-editor-v3 + wangEditor
- Deploy: Docker Compose, SSH -p 20225 luosg@39.97.180.240

## Deployment Workflow
1. `cd /home/luosg/Work/luosg/Code/blog && bash publish/remote.sh` (build + export + SCP)
2. `ssh -p 20225 luosg@39.97.180.240 "cd ~/blog && bash remote_publish.sh"` (load + restart)
3. NEVER forget step 2 — push ≠ deploy

## Multi-Level Comment Design
- `type='post'` — article root comment
- `type='comment'` — child comment (any depth)
- `type='talk'` — talk entity itself (NOT a comment)
- `type='talk_comment'` — root comment on a talk
- `type='message'` — message board entry

`CommentConvertUtil.buildCommentTree` must handle all root types: `post`, `talk`, `talk_comment`.

## URL Path Convention
- DB stores relative paths: `/my-bucket/uuid.png` (MUST start with `/`)
- `UrlNormalizeUtil.stripUrlPrefix` strips domain, must ensure `/` prefix
- `@MinioFile` annotation + `MinioResponseAdvice` auto-prepends base URL on response
- Frontend: use `VITE_MINIO_URL` env var for display
- Java regex: `\\\\d` in source = `\\d` in string = `\d` in regex (digit)

## Frontend Image Upload Points
All `el-upload` with `:action` need `:headers="authHeaders"`:
- `website/info/index.vue` — 8 uploaders (logo, favicon, avatars, QR codes)
- `website/link/index.vue` — friend link cover
- `photo/index.vue` — album cover
- `message/talk/index.vue` — talk images

ImagePicker component emits full URL (not relative path).

## White-list Config
- `/api/admin/**` should NOT be in whitelist — admin endpoints need auth for `getCurrentUserId()`
- Only specific public endpoints should be whitelisted (login, register, captcha, front/**)
