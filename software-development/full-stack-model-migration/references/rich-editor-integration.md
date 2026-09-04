# Rich Editor Integration Patterns (WangEditor + md-editor-v3)

## WangEditor customUpload

WangEditor has two image upload modes:
- `server` mode: expects `{ errno: 0, data: { url, alt, href } }` response
- `customUpload`: you handle the request yourself and call `insertFn(url, alt, href)`

When the backend returns `{ code: 200, result: { imageUrl } }` (standard ApiResponse), use `customUpload`.

```typescript
const editorConfig = {
  MENU_CONF: {
    uploadImage: {
      maxFileSize: 3 * 1024 * 1024,
      maxNumberOfFiles: 10,
      allowedFileTypes: ['image/*'],
      async customUpload(file: File, insertFn: Function) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          const res = await fetch(server, {
            method: 'POST',
            headers: { Authorization: `Bearer ${accessToken}` },
            body: formData
          }).then(r => r.json())
          if (res.code === 200) {
            insertFn(res.result.imageUrl, '', res.result.imageUrl)
            ElMessage.success('图片上传成功')
          } else {
            ElMessage.error(`图片上传失败: ${res.message}`)
          }
        } catch (err) {
          ElMessage.error('图片上传失败')
        }
      }
    }
  }
}
```

## md-editor-v3 Image Dropdown Extension

The image toolbar button has a built-in dropdown with 3 items: 添加链接, 上传图片, 裁剪上传.
This dropdown is NOT extensible via props, slots, or configuration.

### DOM Injection Approach

Find the menu items by CSS class `.md-editor-menu-item-image` and append a new `<li>`:

```typescript
const injectLibraryOption = () => {
  const editorEl = editorRef.value?.$el
  if (!editorEl) return
  const menuItems = editorEl.querySelectorAll('.md-editor-menu-item-image')
  if (!menuItems.length) return
  const parent = menuItems[0].parentElement
  if (parent?.querySelector('.md-editor-menu-item-library')) return // already injected

  const li = document.createElement('li')
  li.className = 'md-editor-menu-item md-editor-menu-item-image md-editor-menu-item-library'
  li.textContent = '从素材库选择'
  li.setAttribute('role', 'menuitem')
  li.setAttribute('tabindex', '0')
  li.style.cursor = 'pointer'
  li.addEventListener('click', () => { showImagePicker.value = true })
  parent?.appendChild(li)
}

// Must inject AFTER editor renders
watch(() => editorRef.value, () => { nextTick(injectLibraryOption) })
onMounted(() => { nextTick(() => setTimeout(injectLibraryOption, 500)) })
```

### NormalToolbar (standalone buttons)

Props: `title`, `onClick` (function, not event), `trigger` (slot for custom icon).

```vue
<MdEditor ...>
  <template #defToolbars>
    <NormalToolbar title="自定义按钮" :onClick="handler">
      <template #trigger>
        <svg viewBox="0 0 1024 1024" width="20" height="20" fill="currentColor">
          <path d="..."/>
        </svg>
      </template>
    </NormalToolbar>
  </template>
</MdEditor>
```

**Pitfall**: `@onClick` (event syntax) doesn't work — must be `:onClick` (prop syntax).
**Pitfall**: Without `#trigger` slot content, the button is invisible. Always provide an icon.

### DropdownToolbar (custom dropdowns)

Props: `trigger` (button icon), `overlay` (dropdown content), `visible`, `onChange`.

## md-editor-v3 onUploadImg

```typescript
const onUploadImg = async (files: File[], callback: (urls: string[]) => void) => {
  if (!props.action) return
  const formData = new FormData()
  formData.append('file', files[0])
  const res = await fetch(props.action, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: formData
  }).then(r => r.json())

  if (res.code === 200) {
    callback([res.result.imageUrl])
  }
}
```

**Pitfall**: Missing `Bearer ` prefix in Authorization header causes 401.
**Pitfall**: Using `res.data.url` instead of `res.result.imageUrl` — the backend uses `ApiResponse.result`, not `data`.

## MinIO URL Strategy

| Context | URL Type | Example |
|---------|----------|---------|
| Database storage | Relative path | `my-bucket/xxx.jpg` |
| Frontend display | Full URL | `http://localhost:9007/my-bucket/xxx.jpg` |
| Backend return | Full URL | `MinioUtil.getPermanentFileUrl()` |
| ImagePicker emit | Full URL | `getImageDisplayUrl(filePath)` |

When inserting into editor content (Markdown `![]()`, HTML `<img>`), always use full URLs.
When saving to database columns (cover_image, logo, favicon), store relative paths via `UrlNormalizeUtil.stripUrlPrefix()`.

## Backend Auto URL Conversion (@MinioFile)

DTO fields annotated with `@MinioFile` are automatically converted from relative paths to full URLs by `MinioResponseAdvice` (a Spring `ResponseBodyAdvice`). No manual conversion needed in service code.

```java
@Data
public static class SomeFrontInformation {
    @MinioFile  // auto: /my-bucket/xxx.jpg → http://host:port/my-bucket/xxx.jpg
    private String favicon;
}
```

**How it works**: `MinioResponseAdvice` intercepts `ApiResponse` → `MinioUrlConverter.convert()` scans fields via reflection → finds `@MinioFile` → calls `buildPermanentUrl(objectName)` which does `prefix + objectName`.

**Pitfall**: If `UrlNormalizeUtil.stripUrlPrefix` has a broken regex (e.g., `\\\\d` instead of `\\d`), the URL stored in DB is already a full URL. Then `@MinioFile` prepends the prefix AGAIN → double URL like `http://127.0.0.1:9007http://localhost:9007/my-bucket/xxx.jpg`. Always verify `stripUrlPrefix` works correctly after changes.
