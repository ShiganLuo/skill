# Pre-Upload Storage Validation

## Pattern

Before allowing file uploads, check two constraints:
1. **Server disk space** — is there enough room on the partition?
2. **User upload quota** — has the user exceeded their allocation?

Show results to the user BEFORE they click upload. Disable the upload button if constraints are violated.

## Backend: StorageInfo DTO

```java
@Data
public class StorageInfo {
    private long diskTotal;      // partition total bytes
    private long diskUsed;       // partition used bytes
    private long diskFree;       // partition usable bytes

    private long userQuota;      // user's upload limit (from DB)
    private long userUsed;       // sum of user's uploaded file sizes
    private long userRemaining;  // quota - used

    private long pendingSize;    // size of files about to be uploaded
    private boolean canUpload;   // false if either constraint violated
    private String reason;       // human-readable reason when canUpload=false
}
```

## Backend: Disk Space Check

```java
File uploadDir = new File(uploadPath);
File partition = uploadDir.exists() ? uploadDir : new File("/");
long totalSpace = partition.getTotalSpace();
long usableSpace = partition.getUsableSpace();
```

`getUsableSpace()` accounts for OS-level reserved blocks — more accurate than `getFreeSpace()`.

## Backend: User Quota Check

```java
// User table has upload_quota column (BIGINT, default 10GB)
User user = userMapper.selectById(userId);
long quota = (user != null && user.getUploadQuota() != null)
    ? user.getUploadQuota() : 10737418240L;

// Sum file sizes from data_files table
long userUsed = dataFileMapper.sumFileSizeByUser(userId);
```

Mapper XML:
```xml
<select id="sumFileSizeByUser" resultType="long">
    SELECT COALESCE(SUM(`file_size`), 0)
    FROM `data_files`
    WHERE `uploaded_by` = #{userId}
</select>
```

## Backend: Check Endpoint + Upload Validation

```java
// Pre-check endpoint (frontend calls before showing upload dialog)
@GetMapping("/storage-check")
public ApiResponse<StorageInfo> storageCheck(
        @RequestParam(defaultValue = "0") long pendingSize) {
    Long userId = LoginUserHolder.getCurrentUserId();
    return ApiResponse.success(dataFileService.checkStorage(userId, pendingSize));
}

// Upload endpoint — also validates server-side
@PostMapping("/upload")
public ApiResponse<DataFile> upload(@RequestParam("file") MultipartFile file, ...) {
    StorageInfo storage = dataFileService.checkStorage(userId, file.getSize());
    if (!storage.isCanUpload()) {
        return ApiResponse.error(400, storage.getReason());
    }
    // proceed with upload
}
```

**Always validate server-side** — the pre-check is for UX, but a malicious client can skip it.

## Frontend: Three Touch Points

1. **Dialog open** — call `storageCheck(0)` to show current usage
2. **File selected** — call `storageCheck(fileSize)` to check if specific file fits
3. **Upload button** — `:disabled="storageInfo && !storageInfo.canUpload"`

```ts
const checkStorageSpace = async (pendingSize: number) => {
  const res = await storageCheck(pendingSize)
  storageInfo.value = res
}
```

## Display

Show two progress bars: user quota usage and disk usage. When `canUpload=false`, show `el-alert` with the reason and disable the upload button.

## Pitfalls

- **User quota requires DB column**: Add `upload_quota BIGINT DEFAULT 10737418240` to users table. Without it, the check falls back to a hardcoded default.
- **Disk space varies by partition**: If `uploadPath` doesn't exist yet, fall back to `/` (root partition). This may not be the partition where uploads actually land after `Files.createDirectories` creates the path.
- **Race condition**: Between `storageCheck` and actual upload, disk space could change. Server-side validation in the upload endpoint is the true gate.
- **Batch upload**: Sum all file sizes before checking, not one-by-one. Check once with total size, then proceed with the batch.
