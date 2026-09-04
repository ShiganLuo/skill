# Folder Upload with webkitdirectory (Vue3 + Spring Boot)

## Overview

Browser-based folder upload using `<input webkitdirectory>`. Preserves directory structure from client to server. Used in bioinformatics platforms where users upload analysis result folders (BAM, VCF, FASTQ with subdirectories).

## Frontend (Vue3 + Element Plus)

### HTML Input

```html
<input
  ref="folderInputRef"
  type="file"
  webkitdirectory
  multiple
  style="display: none"
  @change="handleFolderChange"
/>
```

- `webkitdirectory` — browser shows folder picker instead of file picker
- `multiple` — selects ALL files in the folder recursively
- Hidden input triggered by a styled button click

### Reading Files with Relative Paths

```ts
const folderFiles = ref<File[]>([])

const handleFolderChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  if (input.files) {
    folderFiles.value = Array.from(input.files)
  }
}

// Each File has .webkitRelativePath: "folderName/subdir/file.txt"
const folderName = computed(() => {
  if (!folderFiles.value.length) return ''
  return folderFiles.value[0].webkitRelativePath?.split('/')[0] || 'unknown'
})
```

### Building Directory Tree from Flat File List

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
    const relativePath = file.webkitRelativePath || file.name
    const parts = relativePath.split('/')
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

Display with Element Plus `el-tree`:
```html
<el-tree :data="folderTree" :props="{ label: 'name', children: 'children' }" default-expand-all>
  <template #default="{ node, data }">
    <el-icon v-if="data.isDirectory"><Folder /></el-icon>
    <el-icon v-else><Document /></el-icon>
    <span>{{ node.label }}</span>
    <span v-if="!data.isDirectory">{{ formatFileSize(data.size) }}</span>
  </template>
</el-tree>
```

### Batch Upload with Progress

```ts
const handleFolderUpload = async () => {
  const files = folderFiles.value
  const relativePaths = files.map(f => f.webkitRelativePath || f.name)
  const batchSize = 10
  let uploaded = 0

  for (let i = 0; i < files.length; i += batchSize) {
    const batchFiles = files.slice(i, i + batchSize)
    const batchPaths = relativePaths.slice(i, i + batchSize)

    await batchUploadFiles(batchFiles, batchPaths, projectId)
    uploaded += batchFiles.length
    uploadProgress.percent = Math.round((uploaded / files.length) * 100)
  }
}
```

### API Function (axios)

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

## Backend (Spring Boot)

### Controller

```java
@PostMapping("/batch-upload")
public ApiResponse<List<DataFile>> batchUpload(
        @RequestParam("files") MultipartFile[] files,
        @RequestParam("relativePaths") String[] relativePaths,
        @RequestParam Long projectId) {
    if (files.length != relativePaths.length) {
        return ApiResponse.error(400, "文件数量与路径数量不匹配");
    }
    Long userId = LoginUserHolder.getCurrentUserId();
    List<DataFile> result = new ArrayList<>();
    for (int i = 0; i < files.length; i++) {
        DataFile df = dataFileService.uploadFileWithRelativePath(
                files[i], projectId, relativePaths[i], userId);
        result.add(df);
    }
    return ApiResponse.success(result);
}
```

### Service — Preserve Directory Structure

```java
public DataFile uploadFileWithRelativePath(MultipartFile file, Long projectId,
                                           String relativePath, Long userId) {
    String originalFilename = file.getOriginalFilename();
    String subDir = "";
    String fileName = originalFilename;
    if (relativePath != null && relativePath.contains("/")) {
        subDir = relativePath.substring(0, relativePath.lastIndexOf("/"));
        fileName = relativePath.substring(relativePath.lastIndexOf("/") + 1);
    }

    // Create upload directory preserving folder structure
    Path uploadDir = Paths.get(uploadPath, String.valueOf(projectId), subDir);
    Files.createDirectories(uploadDir);

    // Save with original filename (not UUID) to preserve folder semantics
    Path filePath = uploadDir.resolve(fileName);
    file.transferTo(filePath.toFile());

    // Store relativePath as the file name for display
    DataFile dataFile = new DataFile();
    dataFile.setName(relativePath != null ? relativePath : originalFilename);
    dataFile.setPath(filePath.toString());
    // ... set other fields, insert to DB
    return dataFile;
}
```

## Pitfalls

1. **`webkitdirectory` is non-standard**: Works in Chrome, Firefox, Edge, Safari 14.1+. No IE support. Always check `input.webkitdirectory !== undefined` if supporting old browsers.

2. **`webkitRelativePath` format**: Always `folderName/subdir/file.txt` with forward slashes, even on Windows. The first segment is the selected folder name itself.

3. **Large folders**: Don't send all files in one request. Batch with 10-20 files per request. Show progress bar.

4. **Empty folders**: `webkitdirectory` only returns files, not empty directories. Empty subdirectories are lost.

5. **File naming**: When preserving folder structure, use the original filename (not UUID) so the directory tree makes sense. UUID naming is only for single-file uploads.

6. **FormData key reuse**: `formData.append('files', file)` in a loop creates multiple entries under the same key. Spring Boot's `@RequestParam("files") MultipartFile[]` handles this correctly.

7. **Backend `relativePath` parsing**: Split on `/`, not `File.separator`. The browser always uses forward slashes regardless of OS.
