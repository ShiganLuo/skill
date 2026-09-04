# Import Batch Failures & Debugging

## Import Loop Silent Skip Problem

When a batch import scans a directory and processes files, missing per-file try-catch causes one file's error to abort the entire loop. Files processed before the error are imported; files after are silently skipped.

**Symptom**: Some expected items missing from import, no error shown to user.

**Fix**: Always wrap individual file processing in try-catch inside the loop:

```java
for (Path jsonFile : stream) {
    try {
        // read, parse, insert
        count++;
    } catch (Exception e) {
        log.error("导入 {} 失败，跳过: {}", workflowName, e.getMessage(), e);
    }
}
```

## Debug Scan Endpoint Pattern

When diagnosing why certain files aren't imported, add a GET endpoint that returns what the scan **would** process without touching the DB:

```java
@GetMapping("/debug-scan")
public ApiResponse<Object> debugScan(@RequestParam String dir) {
    List<String> willImport = new ArrayList<>();
    List<String> willSkip = new ArrayList<>();
    // Same glob/filter logic as import, but collect names instead of inserting
    Map<String, Object> result = new HashMap<>();
    result.put("willImport", willImport);
    result.put("willSkip", willSkip);
    return ApiResponse.success(result);
}
```

Compare `willImport` with actual DB rows to identify the gap. This avoids needing access to server logs.

## guessCategory Substring Pitfall

Broad substring matches in categorization functions cause false positives:

```java
// BAD — "ms" is too short, matches unrelated names
if (lower.contains("ms")) return "蛋白质组";

// GOOD — use distinctive substrings
if (lower.contains("quantms")) return "蛋白质组";
```

## DirectoryStream Ordering

Java `DirectoryStream` does NOT guarantee alphabetical order — it returns files in filesystem (inode) order. Don't assume processing order. If debugging, use `sorted()` or log each file's name.

## MySQL JSON Column Constraints

MySQL's JSON type rejects `NaN` and `Infinity` (unlike JavaScript). Validate JSON before inserting:
- No null bytes (`\x00`)
- No `NaN` or `Infinity` literals
- Valid UTF-8 encoding

If a JSON file is valid in Python/JS but fails MySQL insert, check for these.
