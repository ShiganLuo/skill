# MySQL/HikariCP Connection Timeout Debugging

## Symptom

Spring Boot app logs `SocketTimeoutException: Read timed out` when connecting to MySQL via HikariCP.
Root cause chain: `MyBatisSystemException` → `CannotGetJdbcConnectionException` → `CommunicationsException` → `SocketTimeoutException`.

## Common triggers

1. MySQL container restarted — old TCP connections in HikariCP pool become stale.
2. MySQL `wait_timeout` (default 8 hours) exceeds HikariCP `max-lifetime` — connection silently dies.
3. Docker network blip — TCP connection established but MySQL handshake never completes.

## Diagnosis sequence

```bash
# 1. Check MySQL container health
docker compose ps
docker exec <mysql-container> mysql -uroot -p<pass> -e "SELECT 1"

# 2. Check host port reachability
timeout 3 bash -c 'echo > /dev/tcp/127.0.0.1/<port>' && echo "open" || echo "closed"

# 3. Check MySQL timeout settings
docker exec <mysql-container> mysql -uroot -p<pass> -e "SHOW VARIABLES LIKE '%timeout%';"

# 4. Check which Spring profile is active (CRITICAL — see pitfall below)
grep "profiles.active" src/main/resources/application.yml
# Then check docker-compose.yml for SPRING_PROFILES_ACTIVE env var
```

## CRITICAL RULE: max-lifetime vs wait_timeout

**HikariCP `max-lifetime` MUST be at least 30 seconds LESS than MySQL `wait_timeout`.**

When they are equal (e.g., both 1800s), a race condition occurs:
1. Connection reaches 30 min age — both HikariCP and MySQL want to close it
2. If MySQL closes first, the connection is dead on the server side
3. HikariCP pool still holds a reference to the dead connection
4. Next checkout throws `Communications link failure` or `Connection reset`
5. `SELECT 1` validation cannot catch this timing window

HikariCP official docs: "We strongly recommend setting this value, and it should be at least 30 seconds less than any database or infrastructure imposed connection time limit."

## Fix: HikariCP config (in the CORRECT profile file)

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 600000       # 10 min
      max-lifetime: 1200000      # 20 min — MUST be < wait_timeout (1800s) by ≥30s
      connection-timeout: 30000  # 30 sec
      validation-timeout: 5000   # 5 sec — fast dead-connection detection
      connection-test-query: SELECT 1
```

Set this in ALL profile files (dev, docker, prod) — not just the one you're currently debugging.

## Fix: MySQL server-side timeout

```yaml
# docker-compose.yml MySQL command
command: >
  --wait-timeout=1800
  --interactive-timeout=1800
```

Or set dynamically (lost on restart):
```sql
SET GLOBAL wait_timeout=1800;
SET GLOBAL interactive_timeout=1800;
```

## Symptom pattern

"Every ~30 minutes, first request fails, then works on retry" = classic max-lifetime == wait_timeout race.
"Works after container restart, fails again later" = same root cause — restart resets all connection ages to 0.

## PITFALL: Wrong profile file edited

Spring Boot `application.yml` sets `profiles.active: dev` as default.
But Docker Compose may override with `SPRING_PROFILES_ACTIVE: docker`.

**Always check docker-compose.yml `environment` section before editing config files.**

The dev profile uses `localhost:3308` (host-mapped port).
The docker profile uses `mysql:3306` (Docker internal network).

Editing the dev profile when the app runs on docker profile = changes have zero effect.
