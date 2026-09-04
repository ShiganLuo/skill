# Docker Deployment to Remote Server (Build-Locally, Upload, Import)

## Pattern

When deploying Spring Boot to a remote server (e.g., Alibaba Cloud with limited resources), build the Docker image locally, export as tar, upload via SCP, and import on the server. Avoids needing Maven/JDK on the production server.

## Dockerfile

```dockerfile
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY bioplatform-springboot/target/*.jar app.jar
RUN mkdir -p /app/uploads
EXPOSE 8080
ENTRYPOINT ["java", "-Xms256m", "-Xmx512m", "-jar", "app.jar", "--spring.profiles.active=prod"]
```

Key points:
- Use JRE (not JDK) image — smaller footprint
- Alpine variant for minimal image size (~119MB with jar)
- Memory limits via JVM flags, not Docker `--memory` (more predictable)

## Deploy Script Flow

```bash
# 1. Build JAR locally
mvn clean package -q -DskipTests

# 2. Build Docker image
docker build -t bioplatform-backend:latest .

# 3. Export as tar
docker save bioplatform-backend:latest -o /tmp/bioplatform-backend.tar

# 4. Upload to server
scp -i ~/.ssh/key -P PORT /tmp/bioplatform-backend.tar user@host:/tmp/

# 5. Upload SQL
scp -i ~/.ssh/key -P PORT database/bioplatform.sql user@host:/tmp/

# 6. Remote: import, init DB, start
ssh -i ~/.ssh/key -p PORT user@host bash -s << 'EOF'
docker load -i /tmp/bioplatform-backend.tar
docker exec blog_mysql mysql -uroot -pPASS -e "CREATE DATABASE IF NOT EXISTS bioplatform ..."
docker exec -i blog_mysql mysql -uroot -pPASS bioplatform < /tmp/bioplatform.sql
docker run -d --name bioplatform-backend --network blog_net -p 8083:8080 ...
EOF
```

## Multi-Project Docker Network Sharing

When multiple projects share one MySQL container (e.g., blog + bioplatform on same server):

**Option A: Join the existing network (preferred)**
```bash
docker run -d --name bioplatform \
    --network blog_net \
    -p 8083:8080 \
    -e SPRING_DATASOURCE_URL="jdbc:mysql://blog_mysql:3306/bioplatform?..." \
    ...
```
- Uses container name `blog_mysql` as hostname (Docker DNS)
- Port is internal 3306, not host-mapped 3308

**Option B: Use host.docker.internal (unreliable on Linux)**
```bash
docker run -d --add-host=host.docker.internal:host-gateway \
    -e SPRING_DATASOURCE_URL="jdbc:mysql://host.docker.internal:3308/bioplatform?..." \
    ...
```
- `host.docker.internal` does NOT work reliably on Linux Docker
- Requires `--add-host=host.docker.internal:host-gateway`
- Uses host-mapped port (3308)
- **Avoid this approach** — use network sharing instead

## MySQL Init Pitfalls

When importing SQL to a fresh database:
1. Wait for MySQL to be ready (it restarts when containers change)
2. Use `--max-allowed-packet=256M` for large SQL files
3. Always check `docker exec blog_mysql mysql -uroot -pPASS -e 'SELECT 1'` before importing
4. Run ALTER TABLE on the running database — updating the SQL file alone does NOT apply to existing DBs

## Environment Variable Override

Spring Boot properties can be overridden via Docker environment variables:
```bash
-e SPRING_PROFILES_ACTIVE=prod
-e SPRING_DATASOURCE_URL="jdbc:mysql://blog_mysql:3306/bioplatform?..."
-e SPRING_DATASOURCE_USERNAME=root
-e SPRING_DATASOURCE_PASSWORD="password"
```
These override `application-prod.yml` values — no need to bake credentials into the image.
