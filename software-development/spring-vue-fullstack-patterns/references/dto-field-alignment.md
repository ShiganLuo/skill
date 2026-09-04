# DTO Field Alignment Between Frontend and Backend

## Problem

When the backend list endpoint returns a limited DTO but the frontend component expects more fields, the UI shows "未知" or empty values.

**Symptom**: Status tag shows "未知", species/genome tags missing, owner shows "-" — even though data exists in DB.

## Root Cause

The list endpoint maps entity to a reduced DTO that drops fields the frontend needs. The search endpoint may return raw entity (with all fields), causing inconsistent behavior between list and search.

## Fix

### Option 1: Add fields to DTO (preferred)

Update the Java record to include all fields the frontend displays. If associated data is needed (e.g., owner name from user table), inject the mapper and query in the service:

```java
// DTO
public record FrontProjectListDTO(
    Long id, String name, String description,
    String organism, String genomeVersion, Integer status,
    String ownerNickName, LocalDateTime createdAt
) {}

// Service - query associated entity
List<FrontProjectListDTO> dtoList = projects.stream()
    .map(p -> {
        String ownerNickName = null;
        if (p.getOwnerId() != null) {
            User owner = userMapper.selectById(p.getOwnerId());
            if (owner != null) ownerNickName = owner.getNickName();
        }
        return new FrontProjectListDTO(...);
    }).collect(Collectors.toList());
```

### Option 2: Hide UI for missing fields

Use `v-if` on template tags to hide when field is undefined.

## Checklist

- [ ] Compare frontend TypeScript interface fields vs backend DTO record fields
- [ ] Check BOTH list AND search endpoints use same DTO
- [ ] Verify frontend component uses `||` fallback for optional fields
- [ ] Test: list page shows correct status/tags, search shows same
