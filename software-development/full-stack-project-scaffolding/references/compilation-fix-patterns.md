# Compilation Fix Patterns — BioPlatform Session

## Entity Annotation Fix (MyBatis → Plain MyBatis)

**Before** (wrong — uses MyBatis-Plus):
```java
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

@Data
@TableName("t_user")
public class User {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String username;
}
```

**After** (correct — plain MyBatis):
```java
@Data
public class User {
    private Long id;
    private String username;
}
```

**Batch fix script** (Python):
```python
import os, re

entity_dir = "src/main/java/com/bioplatform/entity"
for fname in os.listdir(entity_dir):
    if not fname.endswith('.java'):
        continue
    path = os.path.join(entity_dir, fname)
    with open(path, 'r') as f:
        content = f.read()
    # Remove baomidou imports
    lines = [l for l in content.split('\n') if 'baomidou' not in l]
    content = '\n'.join(lines)
    # Remove @TableName lines
    lines = [l for l in content.split('\n') if '@TableName(' not in l]
    content = '\n'.join(lines)
    with open(path, 'w') as f:
        f.write(content)
```

## JJWT Version Fix

**pom.xml** — update all three jjwt artifacts:
```xml
<!-- From 0.11.5 to 0.12.6 -->
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-api</artifactId>
    <version>0.12.6</version>
</dependency>
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-impl</artifactId>
    <version>0.12.6</version>
    <scope>runtime</scope>
</dependency>
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-jackson</artifactId>
    <version>0.12.6</version>
    <scope>runtime</scope>
</dependency>
```

## AOP Dependency Fix

Add to pom.xml:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
```

## OkHttp Version Fix

```xml
<dependency>
    <groupId>com.squareup.okhttp3</groupId>
    <artifactId>okhttp</artifactId>
    <version>4.12.0</version>
</dependency>
```

## tsconfig.node.json Fix

Replace `"noEmit": true` with `"composite": true`.

## pinia-plugin-persistedstate Fix

Use `"pinia-plugin-persistedstate": "^3.2.3"` for pinia 2.x projects.
Or use `npm install --legacy-peer-deps` as workaround.

## Missing Asset Fix

Create placeholder SVG:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <circle cx="100" cy="100" r="90" fill="#409EFF" opacity="0.1"/>
  <text x="100" y="100" text-anchor="middle" font-size="32" fill="#409EFF">BP</text>
</svg>
```

## YAML Duplicate Key Fix

When Spring Boot fails with `DuplicateKeyException`, read the YAML and merge duplicate keys:

```bash
# Find duplicate keys in YAML
python3 -c "
import yaml, sys
with open('application-dev.yml') as f:
    try:
        yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(e)
"
```

Manual fix: merge two `servlet:` blocks into one:
```yaml
# WRONG (two servlet: keys)
spring:
  servlet:
    multipart: ...
  servlet:
    static-path-pattern: ...

# RIGHT (merged)
spring:
  servlet:
    multipart: ...
    static-path-pattern: ...
```

## JDBC URL Fix

```yaml
# WRONG (utf8mb4 is MySQL charset, not Java charset)
url: jdbc:mysql://localhost:3308/db?characterEncoding=utf8mb4

# RIGHT
url: jdbc:mysql://localhost:3308/db?characterEncoding=UTF-8
```

## Frontend-Backend Contract Fix

When API returns 200 but frontend shows empty/undefined:

1. Check the response shape with curl:
```bash
curl -s -X POST http://localhost:8080/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# Returns: {"code":200,"result":{"accessToken":"...","refreshToken":"..."}}
```

2. Fix the Pinia store to unwrap ApiResponse:
```typescript
const res = await loginApi(params)
const data = res.result || res  // Unwrap ApiResponse wrapper
token.value = data.accessToken  // camelCase, not snake_case
```

3. Fix axios baseURL for local dev (no proxy):
```typescript
const http = axios.create({
  baseURL: 'http://localhost:8080',  // Not '/api'
})
```

## SPA Static Server Fix

```bash
# WRONG - Python http.server doesn't handle SPA routes
python3 -m http.server 5173 --bind 0.0.0.0

# RIGHT - serve with -s flag for SPA mode
npx serve dist -l 5173 -s
```

## Security Whitelist Extraction

After creating all controllers, extract public endpoints:
```bash
grep -rn '@PostMapping.*login\|@PostMapping.*register\|@GetMapping.*public' \
  src/main/java/com/bioplatform/controller/ | \
  sed 's/.*@RequestMapping("\([^"]*\)").*/\1/'
```

Then build the whitelist matching actual paths.

## Bcrypt Password Generation

```bash
pip install bcrypt
python3 -c "
import bcrypt
pwd = 'admin123'.encode('utf-8')
h = bcrypt.hashpw(pwd, bcrypt.gensalt(10))
print(h.decode('utf-8'))
"
# Then: UPDATE users SET password='<hash>' WHERE username='admin';
```

## Spring Security CORS Fix

When frontend (port 5173) can't reach backend (port 8080) despite WebMvcConfigurer CORS being configured:

**SecurityConfig.java** — add CORS bean and enable in filter chain:
```java
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import java.util.Arrays;
import java.util.List;

// Add bean:
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration configuration = new CorsConfiguration();
    configuration.setAllowedOriginPatterns(List.of("*"));
    configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"));
    configuration.setAllowedHeaders(List.of("*"));
    configuration.setExposedHeaders(Arrays.asList("Authorization", "X-Token"));
    configuration.setAllowCredentials(true);
    configuration.setMaxAge(3600L);
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", configuration);
    return source;
}

// In SecurityFilterChain:
http.cors(cors -> cors.configurationSource(corsConfigurationSource()))
```

**Verification**:
```bash
curl -sv -X OPTIONS http://localhost:8080/api/xxx \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" 2>&1 | grep "Access-Control-Allow-Origin"
# Should return: Access-Control-Allow-Origin: http://localhost:5173
```

## Stale Target Directory Fix

When `mvn compile` fails on Lombok-generated methods but `@Data` is present:
```bash
mvn clean compile  # Full clean rebuild
```

## Frontend Data Mapping Fix

When API returns correct data but UI shows blank/zero:
```typescript
// Check what API actually returns:
const res = await getDashboard()
console.log('API response:', JSON.stringify(res))
// Returns: {code: 200, result: {userCount: 1, projectCount: 0, ...}}

// Fix: map API fields to template bindings:
const data = res.result || res
dashboardData.value = {
  totalUsers: data.userCount || 0,      // NOT totalUsers from API
  totalProjects: data.projectCount || 0,
  totalPipelines: data.pipelineCount || 0,
  totalExecutions: data.executionCount || 0,
}
```

## Test Data Decoupling Pattern

When creating API test suites, ALWAYS separate test data from test logic:

**Wrong** (data mixed with logic):
```python
def test_login():
    resp = requests.post("http://localhost:8080/api/admin/auth/login",
                         json={"username": "admin", "password": "admin123"})
    assert resp.json()["code"] == 200
```

**Right** (data decoupled):
```python
# test_data.py — all endpoint definitions
ENDPOINTS = {
    "auth.login": Endpoint(method="POST", path="/api/admin/auth/login",
        body={"username": "{username}", "password": "{password}"}, ...),
}

# test_api.py — logic only, reads from test_data
for name, endpoint in ENDPOINTS.items():
    runner.run_test(name, endpoint)
```

**Benefits**: Add tests by adding dict entries, no logic changes. Change URLs/credentials in one place.

## Database Column Length for Audit Tables

When creating operation_logs or audit tables, use `VARCHAR(255)` or `TEXT` for method/class columns:
```sql
-- WRONG (too short for fully-qualified Java class names)
`method` VARCHAR(16)

-- RIGHT
`method` VARCHAR(255)
```

## Lombok @Slf4j Duplicate Field Fix

**Symptom**: `Field 'log' already exists` or `variable log is already defined` during compilation.

**Root cause**: Class has BOTH `@Slf4j` annotation (auto-generates `private static final Logger log = ...`) AND a manually declared `private static final Logger log = LoggerFactory.getLogger(...)` field. Lombok cannot generate the field because one already exists with the same name.

**Fix**: Remove the manual Logger declaration AND the unused imports:

```java
// BEFORE (broken):
import org.slf4j.Logger;           // ← remove
import org.slf4j.LoggerFactory;    // ← remove
import lombok.extern.slf4j.Slf4j;

@Component
@Slf4j
public class MyTask {
    private static final Logger log = LoggerFactory.getLogger(MyTask.class); // ← remove
}

// AFTER (fixed):
import lombok.extern.slf4j.Slf4j;

@Component
@Slf4j  // ← handles everything
public class MyTask {
    // no manual Logger field
}
```

**Scan entire project** for this conflict:
```bash
for f in $(grep -rl '@Slf4j' src/ --include='*.java'); do
    grep -q 'private static final Logger log' "$f" && echo "CONFLICT: $f"
done
```

**Verification**:
```bash
# Syntax check
bash -n <script>
# Runtime check
<script> help
# Compile check
mvn compile
```

**Prevention**: When using `@Slf4j`, never also declare a `Logger log` field. When migrating from manual Logger to `@Slf4j`, always remove the manual declaration AND the `org.slf4j.*` imports in the same commit.
