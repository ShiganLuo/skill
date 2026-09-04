# BioPlatform user-management alignment notes

Session pattern captured:
- Backend controller used action-style admin routes:
  - `/api/admin/users/list`
  - `/api/admin/users/create`
  - `/api/admin/users/update`
  - `/api/admin/users/status`
  - `/api/admin/users/reset-password`
- Frontend admin API wrapper had drifted to mixed routes:
  - `/api/users`
  - `/api/admin/users/{id}`
  - `/api/admin/users/{id}/status`

Key concrete mismatches fixed:
1. Reset password body was `{ id, password }` on frontend but backend DTO expected `newPassword`.
2. Backend pagination returned Spring `PageResult(total, pageNum, pageSize, list)` while admin TS wrapper/view expected `{ records, page, size }`.
3. Service layer accepted `pageNum/pageSize/keyword/status` in controller but ignored them, using hardcoded `PageHelper.startPage(1, 10)`.
4. User list response needed frontend-facing fields:
   - `nickname`
   - `phone`
   - `roles`
   - `createTime`
5. User delete needed join-table cleanup via `user_roles` before deleting the user.
6. Role assignment had been hardcoded to `1L`; safer fix was resolve by `role_name`.
7. Admin DTO edits must not be copied into front register flow. Front register still used `FrontRegisterRequest(username, email, password, nickName)` and broke Docker build when admin fields were assumed.

Verification pattern that proved useful:
- `mvn -q -DskipTests compile`
- admin frontend build
- front frontend build
- targeted `docker compose build backend`
- only then full runtime/API verification when services are actually up

Important reporting nuance:
- If compile/build/Docker smoke pass but app services are not listening, report it as successful ad-hoc build verification, not full end-to-end success.
