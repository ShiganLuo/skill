# WangEditor customUpload for Spring Boot Backends

## Problem

WangEditor's `uploadImage.server` mode expects this response format:

```json
{ "errno": 0, "data": { "url": "https://...", "alt": "", "href": "" } }
```

But Spring Boot backends typically return:

```json
{ "code": 200, "result": { "imageUrl": "https://...", "imageId": 1 } }
```

The image uploads successfully (200 OK, file stored in MinIO) but never appears in the editor because WangEditor can't parse the response.

## Solution: customUpload

Replace `server` + `headers` config with `customUpload`:

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
          })
          const data = await res.json()
          if (data.code === 200) {
            // insertFn(url, alt, href) — inserts at cursor position
            insertFn(data.result.imageUrl, '', '')
            ElMessage.success('图片上传成功')
          } else {
            ElMessage.error(`上传失败: ${data.message}`)
          }
        } catch (err) {
          ElMessage.error('图片上传失败')
        }
      }
    }
  }
}
```

## Key differences from `server` mode

| Aspect | `server` mode | `customUpload` |
|--------|--------------|----------------|
| Response format | Must be `{ errno, data: { url } }` | You parse it yourself |
| Auth header | Via `headers` config | Manual in `fetch` |
| URL transform | Not possible | Transform before `insertFn` |
| Error handling | Generic | Custom error messages |

## insertFn signature

```typescript
insertFn(url: string, alt?: string, href?: string)
```

- `url`: Image src (required) — can be relative path or full URL
- `alt`: Alt text (optional, default: '')
- `href`: Link URL (optional, default: '') — if set, image is wrapped in `<a>`

## Storing relative paths

If the project stores relative paths in the database (e.g., `/my-bucket/xxx.jpg`), use `customUpload` to strip the base URL before inserting:

```typescript
const url = new URL(data.result.imageUrl)
insertFn(url.pathname) // stores /my-bucket/xxx.jpg instead of full URL
```

This way, changing the MinIO/server address only requires updating the environment variable, not batch-updating all article content.

## Project context (blog project)

- Backend `ImageResponse.imageUrl` returns full URL from `getPermanentFileUrl()`
- Database stores relative path in `images.file_path` (e.g., `my-bucket/xxx.jpg`)
- Frontend displays images by prepending `VITE_MINIO_URL` env var
- ImagePicker component handles the MinIO URL resolution for display
