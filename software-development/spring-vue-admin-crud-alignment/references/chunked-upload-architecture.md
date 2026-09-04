# Chunked Upload with Resume

For files >5MB, HTTP single-request upload is unreliable. Split into chunks, upload in parallel, support resume on failure.

## Backend: Chunk Storage Structure

```
{uploadPath}/_chunks/{uploadId}/
  0          (chunk 0)
  1          (chunk 1)
  ...
  meta.json  ({"fileName":"x.bam","totalChunks":42})
```

## Backend: Three Endpoints

```java
// 1. Upload single chunk
@PostMapping("/upload-chunk")
public ApiResponse uploadChunk(
    @RequestParam("chunk") MultipartFile chunk,
    @RequestParam String uploadId,
    @RequestParam int chunkIndex,
    @RequestParam int totalChunks,
    @RequestParam String fileName) {
    chunkUploadService.uploadChunk(uploadId, chunkIndex, totalChunks, fileName, chunk.getBytes());
}

// 2. Query uploaded chunks (for resume)
@GetMapping("/upload-status")
public ApiResponse uploadStatus(@RequestParam String uploadId) {
    List<Integer> uploadedChunks = chunkUploadService.getUploadedChunks(uploadId);
    return ApiResponse.success(Map.of("uploadedChunks", uploadedChunks));
}

// 3. Merge all chunks into final file
@PostMapping("/merge-chunks")
public ApiResponse mergeChunks(
    @RequestParam String uploadId,
    @RequestParam String fileName,
    @RequestParam Long projectId) {
    DataFile dataFile = chunkUploadService.mergeChunks(uploadId, fileName, projectId, userId);
    return ApiResponse.success(dataFile);
}
```

## Backend: Service Implementation Key Points

- `uploadChunk()`: Write chunk bytes to `{chunkDir}/{chunkIndex}`, save meta.json
- `getUploadedChunks()`: List files matching `\d+` pattern in chunk dir
- `mergeChunks()`: Read chunks in order, stream to target file via `OutputStream`, save DB record, delete chunk dir
- **Security**: Validate `uploadId` doesn't contain `..`, `/`, or `\\` to prevent path traversal

## Frontend: chunkUpload.ts Utility

```ts
const CHUNK_SIZE = 10 * 1024 * 1024  // 10MB
const MAX_CONCURRENT = 3              // parallel uploads
const MAX_RETRIES = 3                 // retry per chunk

function generateUploadId(file: File): string {
  // Hash of name+size+lastModified → deterministic ID for resume
  const raw = `${file.name}_${file.size}_${file.lastModified}`
  let hash = 0
  for (let i = 0; i < raw.length; i++) {
    hash = ((hash << 5) - hash) + raw.charCodeAt(i)
    hash |= 0
  }
  return `chunk_${Math.abs(hash).toString(16)}_${file.size}`
}

async function chunkUpload(options: {
  file: File; projectId: number;
  onProgress?: (p: ProgressInfo) => void
}): Promise<DataFile> {
  const uploadId = generateUploadId(file)
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE)

  // 1. Resume check — query already-uploaded chunks
  const statusRes = await http.get('/upload-status', { params: { uploadId } })
  const uploadedSet = new Set(statusRes.uploadedChunks)

  // 2. Build pending list (skip already uploaded)
  const pending = []
  for (let i = 0; i < totalChunks; i++) {
    if (!uploadedSet.has(i)) pending.push(i)
  }

  // 3. Parallel upload with worker pool
  let nextIdx = 0
  const uploadOne = async () => {
    while (nextIdx < pending.length) {
      const idx = nextIdx++
      const start = pending[idx] * CHUNK_SIZE
      const chunk = file.slice(start, Math.min(start + CHUNK_SIZE, file.size))
      await uploadChunkWithRetry(uploadId, chunk, pending[idx], totalChunks, file.name)
    }
  }
  await Promise.all(Array.from({ length: Math.min(3, pending.length) }, () => uploadOne()))

  // 4. Merge
  return http.post('/merge-chunks', { uploadId, fileName: file.name, projectId })
}
```

## Frontend: Auto-detect Chunk vs Direct Upload

```ts
function shouldUseChunkUpload(file: File): boolean {
  return file.size > 5 * 1024 * 1024  // 5MB threshold
}

// In upload handler:
if (shouldUseChunkUpload(file)) {
  await chunkUpload({ file, projectId, onProgress })
} else {
  await uploadFile(file, projectId)  // original single-request upload
}
```

## How Resume Works

1. User selects file → frontend generates deterministic `uploadId` from file metadata
2. Frontend calls `GET /upload-status?uploadId=xxx` → gets list of already-uploaded chunk indices
3. Only pending chunks are uploaded (skips completed ones)
4. If network fails mid-upload, user retries → same `uploadId` → skips already-uploaded chunks
5. After all chunks uploaded → `POST /merge-chunks` assembles final file

## Pitfalls

- **Chunk upload path traversal**: Validate `uploadId` doesn't contain `..`, `/`, or `\\`. Malicious uploadId could write chunks outside the intended directory.
- **Chunk dir cleanup on failure**: If merge fails (e.g., missing chunks), the chunk directory should be preserved for retry, not deleted. Only delete on successful merge.
- **Chunk size vs network**: 10MB chunks work well for LAN/WAN. For very poor networks, reduce to 5MB. Don't go below 1MB (too much HTTP overhead per chunk).
- **uploadId determinism**: Must be based on file metadata (name+size+lastModified), not random. Otherwise resume can't find the existing chunks.
- **Concurrent upload safety**: Use `isRefreshing`-style flag to prevent multiple simultaneous chunk uploads for the same file. The worker pool pattern handles this naturally.
