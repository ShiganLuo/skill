# BioPlatform full admin API audit

Session: 2026-08-19. Systematic audit of ALL admin modules after initial project module fix.

## Modules audited and fixed

### pipelineApi.ts
| Function | Was | Fixed to |
|----------|-----|----------|
| `listPipelines` | `GET /api/pipelines` | `GET /api/admin/pipelines/list` |
| `createPipeline` | `POST /api/pipelines` | `POST /api/admin/pipelines/create` |
| `updatePipeline` | `PUT /api/admin/pipelines/${id}` | `PUT /api/admin/pipelines/update` (id in body) |

### executionApi.ts
| Function | Was | Fixed to |
|----------|-----|----------|
| `listExecutions` | `GET /api/executions` | `GET /api/admin/executions/list` |
| `cancelExecution` | `POST .../${id}/cancel` | `PUT .../${id}/cancel` (method changed) |

### dataFileApi.ts
| Function | Was | Fixed to |
|----------|-----|----------|
| `listFiles` | `GET /api/data-files` | `GET /api/admin/datafiles/list` |

### systemApi.ts
| Function | Was | Fixed to |
|----------|-----|----------|
| `updateConfig` | `PUT /api/admin/system/configs/${id}` | `PUT /api/admin/system/configs` (no id in path) |

### Already correct (no change needed)
- loginApi.ts — all 4 endpoints correct
- userApi.ts — all 6 endpoints correct
- agentApi.ts — all 4 endpoints correct
- projectApi.ts — fixed in earlier session

## Missing backend endpoints implemented

Frontend had calls to 4 endpoints that didn't exist in backend:

### 1. POST /api/admin/pipelines/{id}/execute
- `PipelineService.executePipeline()` already existed in service layer
- Only needed controller method: `@PostMapping("/{id}/execute")`
- Accepts optional `Map<String, Object>` body with `projectId` and `inputParams`

### 2. GET /api/admin/executions/{id}/logs
- Added `String getExecutionLogs(Long id)` to `PipelineExecutionService`
- Impl returns `execution.getErrorLog()` or status-based fallback string
- Controller: `@GetMapping("/{id}/logs")` returning `ApiResponse<String>`

### 3. GET /api/admin/datafiles/{id}
- Added `DataFile getFileById(Long id)` to `DataFileService`
- Impl delegates to `dataFileMapper.selectById(id)`
- Controller: `@GetMapping("/{id}")` returning `ApiResponse<DataFile>`

### 4. GET /api/admin/datafiles/{id}/download
- Added `Path getFilePath(Long id)` to `DataFileService`
- Impl validates file exists on disk, returns `java.nio.file.Path`
- Controller returns `ResponseEntity<Resource>` with `FileSystemResource`
- Sets `Content-Disposition: attachment` and `Content-Type: application/octet-stream`

## Implementation pattern for missing endpoints

When frontend calls an endpoint that doesn't exist:

1. Check if service layer method already exists (often does for common operations)
2. If not, add to service interface → service impl → controller
3. For file downloads: use `FileSystemResource` + `ResponseEntity<Resource>`, not `ApiResponse`
4. For log/text returns: use `ApiResponse<String>` (simple wrapper)
5. Always validate entity exists before operating on it

## Systematic audit verification script

```bash
# Extract all frontend API URLs
grep -n "http\.\(get\|post\|put\|delete\)" src/api/*Api.ts

# Extract all backend endpoints
grep -oP '(Get|Post|Put|Delete)Mapping\("[^"]*"\)' .../controller/admin/*.java

# Automated comparison (Node.js)
node -e "
const fs = require('fs');
// ... read files, normalize URLs, compare
// Check all URLs start with /api/admin/<module>
"
```

## sed-based batch fix pattern

When multiple API files have the same class of drift (missing `/api/admin/` prefix):

```bash
cd src/api
sed -i "s|http.get('/api/pipelines'|http.get('/api/admin/pipelines/list'|" pipelineApi.ts
sed -i "s|http.post('/api/pipelines'|http.post('/api/admin/pipelines/create'|" pipelineApi.ts
sed -i 's|http.put(`/api/admin/pipelines/${id}`, data)|http.put(`/api/admin/pipelines/update`, { id, ...data })|' pipelineApi.ts
```

Always verify with `grep -n "http\." <file>` after sed batch.
