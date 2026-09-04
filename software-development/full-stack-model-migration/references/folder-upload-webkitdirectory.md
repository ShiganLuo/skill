# Browser Folder Upload with webkitdirectory

## Overview

HTML `<input webkitdirectory>` lets users select an entire folder. The browser returns all files with relative paths preserved in `File.webkitRelativePath`. Combined with a Spring Boot batch upload endpoint, this enables folder upload with directory structure preservation.

## Frontend: Folder Selection

```html
<input type="file" webkitdirectory multiple @change="handleFolderChange" />
```

Key properties:
- `webkitdirectory` — triggers folder picker instead of file picker
- `multiple` — selects all files in the folder
- `File.webkitRelativePath` — returns `"folderName/subdir/file.txt"` (relative to selected folder)

## Frontend: Building Directory Tree Preview

```ts
interface TreeNode {
  name: string
  isDirectory: boolean
  size?: number
  children?: TreeNode[]
}

const folderTree = computed<TreeNode[]>(() => {
  const root: TreeNode[] = []
  const dirMap = new Map<string, TreeNode>()

  for (const file of folderFiles.value) {
    const parts = (file.webkitRelativePath || file.name).split('/')
    let currentLevel = root
    let currentPath = ''

    for (let i = 1; i < parts.length; i++) {  // skip root folder name
      const part = parts[i]
      currentPath = currentPath ? currentPath + '/' + part : part
      const isLast = i === parts.length - 1

      if (isLast) {
        currentLevel.push({ name: part, isDirectory: false, size: file.size })
      } else {
        let dir = dirMap.get(currentPath)
        if (!dir) {
          dir = { name: part, isDirectory: true, children: [] }
          dirMap.set(currentPath, dir)
          currentLevel.push(dir)
        }
        currentLevel = dir.children!
      }
    }
  }
  return root
})
```

Render with Element Plus `<el-tree>`:
```vue
<el-tree :data="folderTree" :props="{ label: 'name', children: 'children' }" default-expand-all>
  <template #default="{ node, data }">
    <el-icon v-if="data.isDirectory"><Folder /></el-icon>
    <el-icon v-else><Document /></el-icon>
    <span>{{ node.label }}</span>
    <span v-if="!data.isDirectory">{{ formatFileSize(data.size) }}</span>
  </template>
</el-tree>
```

## Frontend: Batch Upload API

```ts
export function batchUploadFiles(files: File[], relativePaths: string[], projectId: number) {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  relativePaths.forEach(p => formData.append('relativePaths', p))
  formData.append('projectId', projectId.toString())
  return http.post('/api/admin/datafiles/batch-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
```

**Important**: FormData appends multiple values with the same key — `files.forEach(f => formData.append('files', f))` creates multiple `files` entries, which Spring binds to `MultipartFile[]`.

## Frontend: Upload with Progress

Batch in groups of 10 to avoid timeout:
```ts
const batchSize = 10
for (let i = 0; i < files.length; i += batchSize) {
  const batch = files.slice(i, i + batchSize)
  const paths = relativePaths.slice(i, i + batchSize)
  await batchUploadFiles(batch, paths, projectId)
  uploaded += batch.length
  progress.percent = Math.round((uploaded / files.length) * 100)
}
```

## Backend: Service Method

```java
public DataFile uploadFileWithRelativePath(MultipartFile file, Long projectId,
                                            String relativePath, Long userId) {
    // Parse relative path: "subdir/file.txt" → subDir="subdir", fileName="file.txt"
    String subDir = "";
    String fileName = relativePath != null ? relativePath : file.getOriginalFilename();
    if (relativePath != null && relativePath.contains("/")) {
        subDir = relativePath.substring(0, relativePath.lastIndexOf("/"));
        fileName = relativePath.substring(relativePath.lastIndexOf("/") + 1);
    }

    // Create directory structure
    Path uploadDir = Paths.get(uploadPath, String.valueOf(projectId), subDir);
    Files.createDirectories(uploadDir);

    // Save file (use original filename, not UUID — preserves folder semantics)
    Path filePath = uploadDir.resolve(fileName);
    file.transferTo(filePath.toFile());

    // Save record with relative path as name
    DataFile dataFile = new DataFile();
    dataFile.setName(relativePath);  // "subdir/file.txt"
    dataFile.setPath(filePath.toString());
    // ...
}
```

## Backend: Controller Endpoint

```java
@PostMapping("/batch-upload")
public ApiResponse<List<DataFile>> batchUpload(
        @RequestParam("files") MultipartFile[] files,
        @RequestParam("relativePaths") String[] relativePaths,
        @RequestParam Long projectId) {
    if (files.length != relativePaths.length) {
        return ApiResponse.error(400, "文件数量与路径数量不匹配");
    }
    // ... validate storage quota before uploading ...
    Long userId = LoginUserHolder.getCurrentUserId();
    List<DataFile> result = new ArrayList<>();
    for (int i = 0; i < files.length; i++) {
        result.add(dataFileService.uploadFileWithRelativePath(
                files[i], projectId, relativePaths[i], userId));
    }
    return ApiResponse.success(result);
}
```

## Pitfalls

- **`webkitRelativePath` is read-only** — the browser sets it, you cannot override it.
- **Root folder name is included** in `webkitRelativePath` — skip index 0 when building tree, or strip it when sending to backend.
- **Large folders** — batch upload in groups (10-20 files per request) to avoid timeout. Show progress bar.
- **Empty folders** — `webkitdirectory` only returns files, not empty directories. Empty dirs are lost.
- **Hidden files** — `.DS_Store`, `Thumbs.db`, etc. are included. Filter them out if unwanted.
- **FormData append order** — `files` and `relativePaths` must be appended in the same order, or the backend mapping breaks.
- **Spring `MultipartFile[]` binding** — multiple `formData.append('files', file)` calls with the same key bind to `MultipartFile[]`. Do NOT use `formData.append('files[0]', file)` — that creates nested binding.
