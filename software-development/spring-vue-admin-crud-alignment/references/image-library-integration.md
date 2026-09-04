# Image Library (素材库) Integration Pattern

## Overview

For Spring Boot + Vue3 admin projects with MinIO image storage, implementing an image library allows users to browse and reuse previously uploaded images instead of always uploading new ones.

## Architecture

### Backend

1. **API endpoint**: `GET /api/admin/image/list?keyword=xxx` — returns paginated image list
2. **Mapper**: `selectImagesWithPage` query with optional keyword filter on `file_name`
3. **Service**: `listImages(keyword)` wraps the mapper call
4. **Response**: Returns `ImageItem[]` with `id, filePath, fileName, fileSize, mimeType, createdAt`

### Frontend

1. **ImagePicker component**: Modal dialog with search, grid preview, upload, and selection
2. **API method**: `PhotoService.listImages(keyword?)` in `photoApi.ts`
3. **URL resolution**: `getImageDisplayUrl(filePath)` prepends `VITE_MINIO_URL` for display
4. **Selection emit**: Returns `{ url: fullUrl, id: imageId }` to parent

## Integration Points

Each image upload point in the admin should get a "从素材库选择" button:

| Page | Upload Point | Integration |
|------|-------------|-------------|
| Article publish | Cover image | Button next to upload area |
| Website settings | Logo/favicon/avatar/QR codes (8 fields) | Button next to each upload |
| Friend links | Site logo | Button next to upload |
| Photo albums | Album cover | Button next to upload |
| Talk/说说 | Images | Button next to upload |
| Rich text editor (wangEditor) | Toolbar image button | Via `customUpload` |
| Markdown editor (md-editor-v3) | Toolbar image dropdown | DOM injection into dropdown |

## Integration Pattern

For each upload point:

```vue
<template>
  <!-- Existing upload -->
  <el-upload ... />
  <!-- Add picker button -->
  <el-button type="primary" link @click="showImagePicker = true">
    <el-icon><FolderOpened /></el-icon> 从素材库选择
  </el-button>
  <!-- Picker dialog -->
  <ImagePicker v-model="showImagePicker" @select="handleImageSelect" />
</template>

<script setup>
import ImagePicker from '@/components/Widgets/ImagePicker/index.vue'

const showImagePicker = ref(false)
const handleImageSelect = (image: { url: string; id: number }) => {
  // Update the form field with the selected image URL
  form.value.coverImage = image.url
}
</script>
```

## Key Decisions

- **Emit full URLs, not relative paths.** The ImagePicker should emit `getImageDisplayUrl(filePath)` (full URL) so editors can preview images. The backend's `UrlNormalizeUtil.stripUrlPrefix()` handles converting back to relative paths before database storage.
- **DOM injection for md-editor-v3.** The built-in image dropdown is not extensible. Use `onMounted` + `nextTick` to inject a `<li>` element into the dropdown menu. Match the existing item class structure.
- **Single ImagePicker instance per page.** Use `currentImageField` to track which form field is being edited when multiple upload points share one picker dialog.
