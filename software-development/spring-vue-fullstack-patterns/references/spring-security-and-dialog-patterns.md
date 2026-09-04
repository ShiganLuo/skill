# Spring Security & Vue3 Dialog Patterns

## Spring Security JSON Error Responses

Default returns HTML for 401/403. For API backends, add custom `AuthenticationEntryPoint`:

```java
@Bean
public AuthenticationEntryPoint authenticationEntryPoint() {
    return (request, response, authException) -> {
        response.setContentType("application/json;charset=UTF-8");
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        String tokenHeader = request.getHeader("Authorization");
        String message;
        if (tokenHeader == null || tokenHeader.isBlank()) {
            message = "未提供认证令牌，请先登录";
        } else if (!tokenHeader.startsWith("Bearer ")) {
            message = "认证头格式错误，应为: Bearer <token>";
        } else {
            message = "认证令牌无效或已过期，请重新登录";
        }
        Map<String, Object> body = new HashMap<>();
        body.put("code", 401);
        body.put("message", message);
        body.put("path", request.getRequestURI());
        new ObjectMapper().writeValue(response.getOutputStream(), body);
    };
}
```

Configure: `.exceptionHandling(ex -> ex.authenticationEntryPoint(authenticationEntryPoint()))`

## Vue3 el-dialog @close for Draft Save

`el-dialog` with `v-model`: clicking X/overlay doesn't trigger cancel button handler. Fix with `@close` + `submitted` flag:

```typescript
const submitted = ref(false)
const handleCreate = () => { submitted.value = false /* ... */ }
const handleCancel = () => {
  if (!isEdit.value && !submitted.value) saveDraft()
  dialogVisible.value = false
}
const handleDialogClose = () => {
  if (!isEdit.value && !submitted.value) saveDraft()
}
const handleSubmit = async () => {
  // ... submit success ...
  submitted.value = true
  clearDraft()
  dialogVisible.value = false
}
```

Template: `<el-dialog v-model="dialogVisible" @close="handleDialogClose" ...>`

## DTO Field Alignment

When backend returns reduced DTO, frontend shows "未知"/empty. Fix: add missing fields to DTO and populate in service layer. For user-related fields like `ownerNickName`, inject `UserMapper` and query by `ownerId`.

Test: `docker exec <container> wget -q -O- http://backend:8080/api/...`
