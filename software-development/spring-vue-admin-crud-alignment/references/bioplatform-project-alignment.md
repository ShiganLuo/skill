# BioPlatform projects module alignment notes

Session: 2026-08-19. Same class of drift as user-management module.

## Backend controller (action-style routes)

`AdminProjectController.java` under `@RequestMapping("/api/admin/projects")`:

| Method | Route | Request | Response |
|--------|-------|---------|----------|
| GET | `/list` | `pageNum`, `pageSize` (RequestParam) | `PageResult` |
| GET | `/{id}` | path variable | `Project` |
| POST | `/create` | `AdminProjectCreateRequest` body | `Project` |
| PUT | `/update` | `AdminProjectUpdateRequest` body (includes `id`) | `void` |
| DELETE | `/{id}` | path variable | `void` |

## Frontend API wrapper drift (admin)

`bioplatform-admin/src/api/projectApi.ts` had:

| Function | Was | Should be |
|----------|-----|-----------|
| `listProjects` | `GET /api/projects` | `GET /api/admin/projects/list` |
| `createProject` | `POST /api/projects` | `POST /api/admin/projects/create` |
| `updateProject` | `PUT /api/admin/projects/${id}` | `PUT /api/admin/projects/update` (id in body) |

`getProject` and `deleteProject` were already correct.

## Key mismatch: update endpoint

Backend uses `@PutMapping("/update")` with `AdminProjectUpdateRequest` that includes `id` in the body.
Frontend was sending `PUT /api/admin/projects/${id}` with id in path — wrong.
Fix: change to `PUT /api/admin/projects/update` with `{ id, ...data }` in body.

## Verification

```bash
# Check all admin API URLs align with backend
grep -n "http\." src/api/projectApi.ts
grep -oP '(Get|Post|Put|Delete)Mapping\("[^"]*"\)' .../AdminProjectController.java
```

## Lesson reinforced

Action-style routes (`/list`, `/create`, `/update`) vs REST-style (`GET /resource`, `PUT /resource/{id}`) —
the same project sometimes mixes both across modules. Always read the controller before assuming route shape.
