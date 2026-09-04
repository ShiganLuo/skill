# HikariCP + MySQL Connection Timeout Race Condition

## Symptom

Spring Boot backend loses MySQL connectivity after running idle for ~30 minutes. All subsequent requests fail with `Communications link failure` or `Connection reset`. Only restarting the backend container fixes it. MySQL and Redis containers remain healthy.

## Root Cause

MySQL `wait_timeout` (default 1800s = 30min) closes idle connections on the server side. If HikariCP `max-lifetime` is set equal to or greater than `wait_timeout`, a race condition occurs:

1. Connection lives for 30 minutes
2. MySQL closes it server-side (wait_timeout fires)
3. HikariCP still holds a reference in the pool
4. Next request gets a dead connection → exception

The `connection-test-query: SELECT 1` validation helps but cannot prevent ALL cases — there's a timing window where the connection passes checkout validation but MySQL closes it before the actual query executes.

## The Rule

**HikariCP `max-lifetime` MUST be at least 30 seconds shorter than MySQL `wait_timeout`.**

HikariCP official docs:
> "We strongly recommend setting this value, and it should be at least 30 seconds less than any database or infrastructure imposed connection time limit"

## Correct Configuration

### MySQL (docker-compose.yml)
```yaml
mysql:
  command: >
    --wait-timeout=1800
    --interactive-timeout=1800
```

### Spring Boot (application-docker.yml)
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 600000       # 10 min — must be < wait_timeout
      max-lifetime: 1200000      # 20 min — MUST be < wait_timeout - 30s
      connection-timeout: 30000  # 30s
      validation-timeout: 5000   # 5s
      connection-test-query: SELECT 1
```

### Key relationships
```
wait_timeout (MySQL)     = 1800s  (30 min)
max-lifetime (HikariCP)  = 1200s  (20 min)  ← 10 min buffer, safe
idle-timeout (HikariCP)  = 600s   (10 min)  ← connections idle >10min closed by pool
```

## Common Mistake

Setting `max-lifetime: 1800000` (exactly equals MySQL wait_timeout). This is what Spring Boot projects commonly do when someone sets "30 minutes" for both, not realizing they race against each other.

Also: dev environments often omit HikariCP config entirely, falling back to Spring Boot defaults where `max-lifetime = 1800000` — same problem.

## Detection

```bash
# Check MySQL wait_timeout
docker exec <mysql-container> mysql -uroot -p<pass> -e "SHOW VARIABLES LIKE 'wait_timeout';"

# Check HikariCP max-lifetime
grep -r "max-lifetime" <project>/src/main/resources/
```

If both are 1800(000), that's the bug.

## Fix

Reduce HikariCP `max-lifetime` to 1200000 (20 min) in ALL application profiles (dev, docker, prod). Also add `connection-test-query: SELECT 1` and `validation-timeout: 5000` if missing.
