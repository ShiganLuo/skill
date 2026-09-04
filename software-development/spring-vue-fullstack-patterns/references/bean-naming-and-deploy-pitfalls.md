# Spring Bean Naming Conflicts & Deploy Pitfalls

## Bean Naming Conflict with @EnableScheduling

When a class is named `TaskScheduler` (or any name matching Spring Boot's auto-configured bean), and `@EnableScheduling` is active, Spring's `TaskSchedulingConfigurations.TaskSchedulerConfiguration` registers a bean called `taskScheduler`. This conflicts with the user's `@Component` class → `BeanDefinitionOverrideException`.

**Symptom**: `The bean 'taskScheduler' could not be registered. A bean with that name has already been defined`

**Fix**: Rename the class (e.g., `TaskScheduler` → `PipelineTaskDispatcher`). Update ALL references:
- Class declaration and constructor
- `LoggerFactory.getLogger(TaskScheduler.class)` → `getLogger(PipelineTaskDispatcher.class)`
- Import statements in all injecting classes
- Constructor parameter types

**Reserved bean names to avoid**: `taskScheduler`, `taskExecutor`, `dataSource`, `entityManagerFactory`, `transactionManager`

## @ConditionalOnProperty Import Path

`@ConditionalOnProperty` is in `org.springframework.boot.autoconfigure.condition.ConditionalOnProperty`, NOT `org.springframework.context.annotation.ConditionalOnProperty`. The latter doesn't exist.

## deploy.sh JAVA_HOME Rules

1. **Never hardcode JAVA_HOME** — users have `java` in PATH but may not have JAVA_HOME set
2. **Use `java` and `mvn` from PATH** directly
3. **Exception**: if system Maven picks wrong JDK, set `JAVA_HOME` only for the mvn command using the user's existing env var, not a hardcoded path

## Docker Deploy on Memory-Constrained Servers

On servers with <2G RAM, `docker exec mysql ... < large.sql` can OOM-kill MySQL.

**Workaround**: Import tables incrementally (one CREATE TABLE at a time) instead of importing the full SQL dump at once. Or stop other containers first to free memory.

## deploy/ File Structure Convention

User expects Dockerfiles and nginx configs in a structured directory:
```
deploy/
├── dockerfiles/
│   ├── Dockerfile.backend
│   ├── Dockerfile.front
│   └── Dockerfile.admin
└── nginx/
    ├── bioplatform.conf    # nginx-proxy reverse proxy config
    └── default.conf        # container-internal nginx (Vue Router history)
```

Root-level `Dockerfile` should be moved to `deploy/dockerfiles/Dockerfile.backend`.
