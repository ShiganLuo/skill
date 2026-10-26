---
name: spring-boot-rbac-data-isolation
description: "Use for RBAC and data isolation in Spring Boot projects."
tags: [java, spring-boot, vue3, rbac, security, permissions]
---

# RBAC + Data Isolation Pattern for Spring Boot + Vue3

Three-layer permission defense: API layer (@PreAuthorize), Route layer (router guard), View layer (v-permission directive + menu filtering). Plus row-level data isolation (users can only see their own data).

## Prerequisites

- Spring Security 6.x with JWT authentication already configured
- Database tables: `roles`, `permissions`, `user_roles`, `role_permissions`
- `CustomUserDetailsService` loads roles and builds `GrantedAuthority` list

## Backend: Enable Method Security

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity          // enables @PreAuthorize
public class SecurityConfig { ... }
```

## Backend: Return Roles in Login/UserInfo Response

The `FrontUserInfoDTO` must include `roles`:

```java
public record FrontUserInfoDTO(
    Long id, String username, String nickName, String avatarUrl,
    List<String> roles          // NEW
) {}
```

In `getUserInfo()` and `login()`:
```java
List<Role> userRoles = roleMapper.selectByUserId(userId);
List<String> roleNames = userRoles.stream().map(Role::getRoleName).collect(Collectors.toList());
```

Both `AdminAuthController` and `FrontAuthController` need `RoleService` injected.

## Backend: @PreAuthorize on Controllers

Class-level annotation for admin-only controllers:

```java
@RestController
@RequestMapping("/api/admin/users")
@PreAuthorize("hasRole('ADMIN')")
public class AdminUserController { ... }
```

Business controllers (project, pipeline, data, execution, agent) typically do NOT add class-level @PreAuthorize — they allow any authenticated user, with data isolation enforced at query level.

## Backend: AccessDeniedEntryPoint (403 JSON)

Without this, Spring Security returns an HTML white page for 403:

```java
@Component
public class AccessDeniedEntryPoint implements AccessDeniedHandler {
    @Override
    public void handle(HttpServletRequest req, HttpServletResponse res, AccessDeniedException e)
            throws IOException {
        res.setStatus(HttpServletResponse.SC_FORBIDDEN);
        res.setContentType(MediaType.APPLICATION_JSON_VALUE);
        new ObjectMapper().writeValue(res.getOutputStream(), ApiResponse.error(403, "权限不足"));
    }
}
```

Wire in SecurityConfig via **constructor injection** (not @Bean method call):

```java
private final AccessDeniedEntryPoint accessDeniedEntryPoint;  // injected

.exceptionHandling(ex -> ex
    .authenticationEntryPoint(authenticationEntryPoint())
    .accessDeniedHandler(accessDeniedEntryPoint)    // field, NOT method call
)
```

**Pitfall**: Writing `accessDeniedEntryPoint()` (method call) creates a NEW instance bypassing Spring management.

## Backend: Row-Level Data Isolation (OwnershipUtils)

Separate from role-based access: controls which ROWS a user can see, not which endpoints.

```java
public final class OwnershipUtils {
    public static boolean isAdmin() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        return auth.getAuthorities().stream()
            .map(GrantedAuthority::getAuthority)
            .anyMatch("ROLE_ADMIN"::equals);
    }

    public static void checkOwnership(Long ownerId, String resourceName) {
        if (ownerId == null || isAdmin()) return;
        Long currentUserId = LoginUserHolder.getCurrentUserId();
        if (currentUserId == null || !currentUserId.equals(ownerId)) {
            throw new AccessDeniedException("无权访问该" + resourceName);
        }
    }
}
```

**Pattern for list queries**: Controller checks `isAdmin()` → admin sees all, user sees own:

```java
if (OwnershipUtils.isAdmin()) {
    list = mapper.selectAll();
} else {
    list = mapper.selectByOwnerId(currentUserId);
}
```

**Pattern for single-record ops**: Fetch first, then check ownership:

```java
Project existing = service.getById(id);
if (existing == null) return ApiResponse.error(404, "不存在");
OwnershipUtils.checkOwnership(existing.getOwnerId(), "项目");
```

**Cross-entity ownership** (e.g., SampleMeta belongs to Project):

```java
private void checkProjectOwner(Long projectId) {
    Project project = projectService.getProjectById(projectId);
    if (project != null) OwnershipUtils.checkProjectOwnership(project.getOwnerId());
}
```

## Frontend: v-permission Directive

```typescript
// src/directives/permission.ts
export const permissionDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string[]>) {
    const requiredRoles = binding.value
    if (!requiredRoles?.length) return
    const userRoles = useUserStore().userInfo?.roles || []
    if (!requiredRoles.some(r => userRoles.includes(r))) {
      el.parentNode?.removeChild(el)
    }
  },
  updated(el: HTMLElement, binding: DirectiveBinding<string[]>) {
    // same logic for reactivity
  }
}
```

Register in `main.ts`: `app.directive('permission', permissionDirective)`

Usage: `<el-button v-permission="['ROLE_ADMIN']">Delete</el-button>`

## Frontend: Route Guard with Role Check

Add `meta.roles` to admin-only routes:

```ts
{ path: 'system/users', meta: { title: '用户管理', roles: ['ROLE_ADMIN'] } }
```

Guard logic:

```ts
const requiredRoles = to.meta.roles as string[] | undefined
if (requiredRoles?.length) {
  if (!requiredRoles.some(role => userStore.hasRole(role))) {
    next({ path: '/dashboard' })
    return
  }
}
```

## Frontend: Menu Filtering

```vue
<el-sub-menu v-if="userStore.hasRole('ROLE_ADMIN')" index="system">
  <!-- admin-only menu items -->
</el-sub-menu>
```

## Pitfalls

1. **@EnableMethodSecurity missing**: Without it, @PreAuthorize is silently ignored. Always verify.
2. **FrontUserInfoDTO without roles**: Frontend store has `hasRole()` but backend never sends roles → all role checks return false → everything hidden.
3. **Ownership check on write but not read**: Common gap — create() sets ownerId, but getById()/list() don't check it. Users can enumerate IDs to see others' data.
4. **Client-passed userId**: Never trust userId from request parameters for ownership checks. Always get from `SecurityContext` / `LoginUserHolder`.
5. **Missing List import**: When adding `List<String> roles` to code that previously didn't use List, Java won't auto-import `java.util.List`. Always add the import.
