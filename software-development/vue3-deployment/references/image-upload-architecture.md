# Image Upload Architecture & Image Library

## Storage Strategy

The database stores relative paths (`my-bucket/xxx.png` in `images.file_path`, `/my-bucket/xxx.png` in `articles.cover_image`). The backend `MinioUtil` has two methods:
- `getPermanentRelativeFileUrl(name)` → `/my-bucket/xxx.png` (for DB storage)
- `getPermanentFileUrl(name)` → `http://host:9007/my-bucket/xxx.png` (for API response)

The `ImageServiceImpl.uploadImage` returns `imageUrl` (full URL) to the frontend. Editors use this full URL directly in content. The `VITE_MINIO_URL` env var handles display in non-upload contexts (ImagePicker preview, article list thumbnails).

**Do NOT add `resolveImageUrl()` wrappers to display components** — the backend already returns full URLs where needed. Only add `VITE_MINIO_URL`-based resolution for components that read raw `filePath` from the database (like ImagePicker's preview grid).

## The Response Format Problem

Backend returns: `{ code: 200, result: { imageUrl, imageId } }`

Different editors expect different formats:
- **WangEditor** (`@wangeditor/editor`): expects `{ errno: 0, data: { url } }`
- **md-editor-v3**: expects whatever the `onUploadImg` callback receives — no built-in format

Both fail when using the default upload mechanism. Fix: use custom upload callbacks.

## WangEditor `customUpload` Integration

In `Editor.vue`, replace `server` mode with `customUpload`:

```ts
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
          })
          const data = await res.json()
          if (data.code === 200) {
            insertFn(data.result.imageUrl, '', data.result.imageUrl)
            ElMessage.success('图片上传成功')
          } else {
            ElMessage.error(`图片上传失败: ${data.message}`)
          }
        } catch (err) {
          ElMessage.error('图片上传失败')
        }
      }
    }
  }
}
```

**Key**: `insertFn(url, alt, href)` — first arg goes into `<img src>`. Pass `data.result.imageUrl` which is already a full URL from the backend.

## md-editor-v3 `onUploadImg` Integration

In `MarkdownEditor.vue`, fix the `onUploadImg` callback:

```ts
const onUploadImg = async (files: File[], callback: (urls: string[]) => void) => {
  if (!props.action) return
  const formData = new FormData()
  formData.append('file', files[0])
  try {
    const res = await fetch(props.action, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData
    }).then(r => r.json())

    if (res.code === 200) {
      callback([res.result.imageUrl])
      ElMessage.success('图片上传成功')
    } else {
      throw new Error(res.message)
    }
  } catch (e) {
    ElMessage.error('图片上传失败')
  }
}
```

Common mistakes:
- Using `res.errno === 0` instead of `res.code === 200`
- Using `res.data.url` instead of `res.result.imageUrl`
- Missing `Bearer ` prefix in Authorization header (must be `Bearer ${accessToken}`, not just `accessToken`)

## Image Library (ImagePicker Component)

To avoid re-uploading the same image, add an image library feature.

### Backend API

`GET /api/admin/image/list?fileName=xxx` — returns all images (searchable by filename).

Add to `ImageMapper.java`:
```java
List<Image> selectImagesWithPage(@Param("fileName") String fileName);
```

Add to `ImageMapper.xml`:
```xml
<select id="selectImagesWithPage" resultMap="ImageResultMap">
    SELECT * FROM images
    <where>
        <if test="fileName != null and fileName != ''">
            AND file_name LIKE CONCAT('%', #{fileName}, '%')
        </if>
    </where>
    ORDER BY created_at DESC
</select>
```

Add to `ImageService.java` / `ImageServiceImpl.java` and `AdminImageController.java` (`@GetMapping("/list")`).

### Frontend Component: `ImagePicker.vue`

Location: `src/components/Widgets/ImagePicker/index.vue`

Props: `v-model` (show/hide dialog)
Emits: `@select` with `{ url: fullUrl, id: number }`

**CRITICAL**: The `@select` emit MUST return the FULL URL (via `getImageDisplayUrl(filePath)`), NOT the raw database `filePath`. The database stores relative paths (like `my-bucket/xxx.jpg`), but editors (Markdown, WangEditor) need full URLs for preview to work. The `getImageDisplayUrl` helper prepends `VITE_MINIO_URL`.

The `VITE_MINIO_URL` env var is needed for both displaying image previews in the picker grid AND for constructing full URLs on select.

### Integration Points (Comprehensive Audit)

Add "从素材库选择" button next to EVERY image upload area:

| File | Upload Point | Status |
|------|-------------|--------|
| `views/blog/article/publish.vue` | Article cover | Required |
| `components/Form/Editor.vue` | WangEditor toolbar | Required |
| `components/Form/MarkdownEditor.vue` | Markdown toolbar | Required |
| `views/website/info/index.vue` | 8 uploads: logo/favicon/avatar/background/QR codes | Required |
| `views/website/link/index.vue` | Friend link cover | Required |
| `views/photo/index.vue` | Album cover | Required |
| `views/message/talk/index.vue` | Talk images | Optional (batch upload) |
| `views/photo/photo.vue` | Photo upload | Skip (batch upload, new photos) |
| `views/system/user/index.vue` | Excel import | Skip (not images) |

**When adding ImagePicker to a new page:**
1. Add `import ImagePicker` in `<script setup>`
2. Add `const showImagePicker = ref(false)` state
3. Add `const handleImageSelect` handler that sets the form field
4. Add `<el-button>` next to the upload area
5. Add `<ImagePicker v-model="showImagePicker" @select="handleImageSelect" />` in template
6. If the form uses `reactive()` with `null` initial values, cast: `form.field = image.url as any`

## Pitfalls

- **MinIO port mapping**: Docker maps `9007->9000` (API). The `application-dev.yml` must use `9007`, NOT `9000`. The prod profile uses Docker internal networking (`minio:9000`), so no port mapping needed there.
- **`VITE_MINIO_URL` missing**: If not set, ImagePicker falls back to `http://localhost:9007`. In production, always set the env var.
- **Mixed old/new URLs**: Existing articles may have full URLs. Both `resolveImageUrl()` and direct path usage work — no migration needed.
- **`write_file` on .vue files**: ALWAYS use `patch` tool, never `write_file` — .vue files get corrupted by write_file.
