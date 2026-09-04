# Spring Boot MySQL Connection Timeout Troubleshooting

## Symptom
`MyBatisSystemException` → `CannotGetJdbcConnectionException` → `CommunicationsException: Communications link failure` → `SocketTimeoutException: Read timed out`

## Root Cause
HikariCP connection pool tries to establish a new JDBC connection to MySQL, but the server doesn't respond within the default timeout. Common when:
- MySQL container just restarted and pool has stale connections
- Docker network transient blip
- MySQL momentary overload

## Diagnosis Steps
1. Check Docker container health: `docker compose ps` — look for `(healthy)` status
2. Verify MySQL is reachable: `docker exec <mysql-container> mysql -u<user> -p<pass> -e "SELECT 1"`
3. Check port accessibility from host: `timeout 3 bash -c 'echo > /dev/tcp/127.0.0.1/<port>'`
4. Check MySQL logs for restart events: `docker compose logs mysql --tail 20`

## Fix: HikariCP Connection Pool Tuning
Add to `application-dev.yml` (or active profile) under `spring.datasource`:

```yaml
spring:
  datasource:
    hikari:
      connection-timeout: 30000    # 30s to obtain connection (default 30s)
      validation-timeout: 5000     # 5s for connection validation
      max-lifetime: 1800000        # 30min max connection lifetime
      idle-timeout: 600000         # 10min idle before eviction
```

## Key Config Values
| Property | Default | Recommended | Purpose |
|----------|---------|-------------|---------|
| connection-timeout | 30000 | 30000 | Max wait for connection from pool |
| validation-timeout | 5000 | 5000 | Timeout for connection test query |
| max-lifetime | 1800000 | 1800000 | Force connection renewal before MySQL wait_timeout |
| idle-timeout | 600000 | 600000 | Evict idle connections to avoid stale ones |

## Notes
- If transient (happens once after MySQL restart), the pool self-heals on next request
- If persistent, check MySQL `wait_timeout` and `max_connections` settings
- For production, also configure `minimum-idle` and `maximum-pool-size`
