# Full-Stack File Management Architecture

Pattern for Spring Boot + Vue3 file management with folder upload, storage quota, and rsync import.

## Architecture Overview

```
Web Upload (small files)     rsync (large files)
        │                           │
        ▼                           ▼
  POST /upload              rsync → server disk
  POST /batch-upload                     │
        │                               ▼
        ▼                    POST /import-local
  Storage check ◄────────────────────────┘
  (disk + user quota)
        │
        ▼
  data_files table (metadata only)
```

## Backend: Storage Quota Check

### DTO

```java
@Data
public class StorageInfo {
    private long diskTotal;
    private long diskUsed;
    private long diskFree;
    private long userQuota;
    private long userUsed;
    private long userRemaining;
    private long pendingSize;
    private boolean canUpload;
    private String reason;
}
```

### Database: Add quota column to users

```sql
ALTER TABLE users ADD COLUMN upload_quota BIGINT NOT NULL DEFAULT 10737418240
    COMMENT 'Upload quota in bytes, default 10GB' AFTER status;
```

**PITFALL**: After altering the running container's table, also update `database/bioplatform.sql` schema file AND the MyBatis mapper XML (`UserMapper.xml`) to include the new column in `Base_Column_List` and `resultMap`.

### Service: checkStorage method

```java
public StorageInfo checkStorage(Long userId, long pendingSize) {
    StorageInfo info = new StorageInfo();
    // 1. Disk space
    File partition = new File(uploadPath).exists() ? new File(uploadPath) : new File("/");
    info.setDiskTotal(partition.getTotalSpace());
    info.setDiskFree(partition.getUsableSpace());

    // 2. User quota
    User user = userMapper.selectById(userId);
    long quota = (user != null && user.getUploadQuota() != null) ? user.getUploadQuota() : 10737418240L;
    info.setUserQuota(quota);

    // 3. User used (sum from data_files table)
    long userUsed = dataFileMapper.sumFileSizeByUser(userId);
    info.setUserUsed(userUsed);

    // 4. Decision
    if (partition.getUsableSpace() < pendingSize) {
        info.setCanUpload(false);
        info.setReason("服务器磁盘空间不足");
    } else if (userUsed + pendingSize > quota) {
        info.setCanUpload(false);
        info.setReason("超出个人上传配额");
    } else {
        info.setCanUpload(true);
    }
    return info;
}
```

### Mapper: Sum queries

```xml
<select id="sumFileSizeByUser" resultType="long">
    SELECT COALESCE(SUM(`file_size`), 0) FROM `data_files` WHERE `uploaded_by` = #{userId}
</select>
```

## Backend: Folder Upload (Batch with Relative Paths)

### Controller

```java
@PostMapping("/batch-upload")
public ApiResponse<List<DataFile>> batchUpload(
        @RequestParam("files") MultipartFile[] files,
        @RequestParam("relativePaths") String[] relativePaths,
        @RequestParam Long projectId) {
    // Validate storage
    long totalSize = Arrays.stream(files).mapToLong(MultipartFile::getSize).sum();
    StorageInfo storage = dataFileService.checkStorage(userId, totalSize);
    if (!storage.isCanUpload()) return ApiResponse.error(400, storage.getReason());

    // Upload preserving directory structure
    List<DataFile> result = new ArrayList<>();
    for (int i = 0; i < files.length; i++) {
        result.add(dataFileService.uploadFileWithRelativePath(files[i], projectId, relativePaths[i], userId));
    }
    return ApiResponse.success(result);
}
```

### Service: Preserve directory structure

```java
public DataFile uploadFileWithRelativePath(MultipartFile file, Long projectId, String relativePath, Long userId) {
    String subDir = "";
    String fileName = relativePath;
    if (relativePath.contains("/")) {
        subDir = relativePath.substring(0, relativePath.lastIndexOf("/"));
        fileName = relativePath.substring(relativePath.lastIndexOf("/") + 1);
    }
    Path uploadDir = Paths.get(uploadPath, String.valueOf(projectId), subDir);
    Files.createDirectories(uploadDir);
    Path filePath = uploadDir.resolve(fileName);
    file.transferTo(filePath.toFile());
    // ... save metadata to DB
}
```

## Backend: Import Local Files (rsync → DB)

```java
@PostMapping("/import-local")
public ApiResponse<Map<String, Object>> importLocal(
        @RequestParam String dirPath, @RequestParam Long projectId) {
    int count = dataFileService.importLocalFiles(dirPath, projectId, userId);
    return ApiResponse.success(Map.of("count", count, "dirPath", dirPath));
}
```

Service recursively scans directory, creates DataFile records with relative paths as names. Files stay on disk — only metadata is written to DB.

## Frontend: Folder Upload with webkitdirectory

```html
<input type="file" webkitdirectory multiple @change="handleFolderChange" />
```

Key: `webkitdirectory` attribute makes the browser select a folder. Each `File` has `webkitRelativePath` property (e.g., `my_folder/sub/file.bam`).

### Build folder tree for preview

```ts
const folderTree = computed(() => {
  // Parse webkitRelativePath into tree structure for el-tree display
  // Each file: relativePath.split('/') → traverse/create nodes
})
```

### Batch upload with progress

```ts
// Upload in batches of 10
for (let i = 0; i < files.length; i += 10) {
    const batch = files.slice(i, i + 10)
    const paths = relativePaths.slice(i, i + 10)
    await batchUploadFiles(batch, paths, projectId)
    progress.current = Math.min(i + 10, files.length)
    progress.percent = Math.round((progress.current / files.length) * 100)
}
```

## Frontend: Storage Check Before Upload

```ts
// Check when files are selected
const handleFileChange = (file: UploadFile) => {
    selectedFile.value = file.raw
    if (selectedFile.value) checkStorageSpace(selectedFile.value.size)
}

// Show in dialog: quota bar + disk bar + warning if insufficient
// Disable upload button when !storageInfo.canUpload
```

## Frontend: rsync Command Generation

```ts
// Backend returns host, port, uploadPath
// Frontend displays copyable rsync commands:
// rsync -avz --progress ./data/ user@host:/path/{projectId}/
```

## PITFALLS

- **webkitdirectory browser support**: Works in Chrome, Edge, Firefox. Safari support is partial. Always provide a fallback single-file upload option.
- **Large batch uploads**: Don't send all files in one request. Batch in groups of 10-20 to avoid request timeout and memory issues.
- **Import vs Upload**: Import only writes metadata (DB records pointing to existing files). Upload physically copies files. Don't confuse the two — imported files don't count against quota since they already exist on disk.
- **Relative path separators**: Browser uses `/` in `webkitRelativePath`. Java `Path.relativize()` may use `\` on Windows. Always normalize: `relativePath.replace('\\', '/')`.
- **ALTER TABLE on running container**: After `docker exec ... ALTER TABLE`, the change persists in the volume. But `database/bioplatform.sql` must also be updated for fresh deployments.
