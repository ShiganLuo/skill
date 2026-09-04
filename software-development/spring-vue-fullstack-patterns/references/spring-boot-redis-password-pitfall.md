# Spring Boot Redis Password Configuration Pitfall

## Symptom
Spring Boot app starts successfully, HikariPool connects to MySQL, but HTTP requests hang forever (no error, no timeout, just hang with 0 bytes received until client timeout).

## Root Cause
Redis `password` environment variable is set but `application-prod.yml` has no `password` field under `spring.data.redis`. Spring Boot silently ignores the env var for password.

## The Bug Pattern

```yaml
# application-prod.yml — WRONG: no password field
spring:
  data:
    redis:
      host: blog_redis
      port: 6379
      database: 0
      # password field MISSING
```

```yaml
# docker-compose.yml
environment:
  SPRING_DATA_REDIS_PASSWORD: 8978654  # This is SILENTLY IGNORED
```

## The Fix

```yaml
# application-prod.yml — CORRECT: password field exists
spring:
  data:
    redis:
      host: blog_redis
      port: 6379
      password: "8978654"  # Field must exist for env var to work
      database: 0
      timeout: 3000ms
```

## Why This Happens
Spring Boot's relaxed binding works for simple properties (host, port) but `password` requires the field to exist in the YAML. Without the YAML field, the env var is silently ignored and Lettuce tries to connect without authentication.

Redis with `requirepass` rejects unauthenticated commands → Lettuce hangs waiting for a response that never comes.

## Diagnostic
```bash
# 1. Confirm env vars are set
docker exec <container> env | grep REDIS

# 2. Test Redis connectivity from container
docker exec <container> sh -c 'echo PING | timeout 3 nc blog_redis 6379'
# Expected: -NOAUTH Authentication required.
# If empty → Redis not reachable

# 3. Check if app hangs on first HTTP request
curl -v --max-time 10 http://localhost:8080/api/...
# "Operation timed out after 10000 milliseconds with 0 bytes received" = Redis hang
```

## Key Insight
- `SPRING_DATA_REDIS_HOST` and `SPRING_DATA_REDIS_PORT` work without YAML field (simple properties)
- `SPRING_DATA_REDIS_PASSWORD` does NOT work without YAML field (complex binding)
- Always add `password:` field in YAML even if using env vars
