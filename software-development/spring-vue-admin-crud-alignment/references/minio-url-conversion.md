# MinIO URL Auto-Conversion with @MinioFile

## Problem

MinIO stores files with relative paths (e.g., `/my-bucket/xxx.png`). API responses need to return full URLs (e.g., `http://minio.example.com/my-bucket/xxx.png`) for the frontend to display images. Manually building URLs in every service method is error-prone and violates DRY.

## Solution: @MinioFile + ResponseBodyAdvice

The project has a `MinioResponseAdvice` (implements `ResponseBodyAdvice<Object>`) that intercepts all `ApiResponse` responses. It uses `MinioUrlConverter` to scan response objects for fields annotated with `@MinioFile` and prepends `file.public-base-url`.

### Components

1. **`@MinioFile` annotation** — marks a String field as a MinIO relative path
   ```java
   @Retention(RetentionPolicy.RUNTIME)
   @Target(ElementType.FIELD)
   public @interface MinioFile {}
   ```

2. **`MinioUrlConverter`** — reflective field scanner with caching
   - Reads `file.public-base-url` from config (e.g., `http://127.0.0.1:9007`)
   - Scans object fields for `@MinioFile` annotation
   - Replaces relative path with `prefix + path`
   - Handles nested objects, collections, Maps, Optional
   - Uses `ConcurrentHashMap` for field caching
   - Supports `@MinioScan` annotation for depth control

3. **`MinioResponseAdvice`** — Spring `ResponseBodyAdvice` that triggers conversion
   ```java
   @Override
   public Object beforeBodyWrite(Object body, ...) {
       if (body instanceof ApiResponse<?> apiResponse) {
           converter.convert(apiResponse.result());
       }
       return body;
   }
   ```

### Usage

Annotate DTO fields that store MinIO relative paths:

```java
@Data
public class SomeFrontInformation {
    private String websiteChineseName;
    @MinioFile
    private String favicon;        // /my-bucket/favicon.png → http://minio:9007/my-bucket/favicon.png
    @MinioFile
    private String authorAvatar;
}
```

### What NOT to do

- Do NOT manually build URLs with `minioUtil.getPermanentFileUrl()` in service code when the DTO is returned via `ApiResponse`
- Do NOT create frontend utility functions (`resolveImageUrl`, `toRelativePath`) when the backend can handle the conversion
- Do NOT store full URLs in the database — always store relative paths, convert at response time

### When @MinioFile is NOT applied

If the response is NOT wrapped in `ApiResponse` (e.g., raw `ResponseEntity`), the `ResponseBodyAdvice` won't trigger. In that case, manually call `minioUtil.getPermanentFileUrl()`.

### Config

```yaml
# application-dev.yml
minio:
  endpoint: http://127.0.0.1:9007
file:
  public-base-url: http://127.0.0.1:9007

# application-prod.yml (Docker internal networking)
minio:
  endpoint: http://minio:9000
file:
  public-base-url: https://minio.shiganluo.top
```

The `file.public-base-url` is the externally accessible URL (what browsers use), while `minio.endpoint` is the internal API URL (what the backend uses for uploads).
