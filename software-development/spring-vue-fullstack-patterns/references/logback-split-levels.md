# Spring Boot Logging: Stdout INFO + File DEBUG

By default, Spring Boot logs everything to stdout at the root level. To split levels (console=INFO, file=DEBUG), use `logback-spring.xml`.

## logback-spring.xml

Place at `src/main/resources/logback-spring.xml`. This file takes precedence over `application.yml` logging config.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>

    <!-- Console: INFO only -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <filter class="ch.qos.logback.classic.filter.ThresholdFilter">
            <level>INFO</level>
        </filter>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- File: DEBUG level with rotation -->
    <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>logs/bioplatform.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>logs/bioplatform.%d{yyyy-MM-dd}.%i.log</fileNamePattern>
            <maxFileSize>50MB</maxFileSize>
            <maxHistory>30</maxHistory>
            <totalSizeCap>1GB</totalSizeCap>
        </rollingPolicy>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Per-profile root levels -->
    <springProfile name="dev">
        <root level="DEBUG">
            <appender-ref ref="CONSOLE"/>
            <appender-ref ref="FILE"/>
        </root>
    </springProfile>

    <springProfile name="prod">
        <root level="INFO">
            <appender-ref ref="CONSOLE"/>
            <appender-ref ref="FILE"/>
        </root>
    </springProfile>

    <!-- Default (no active profile) -->
    <root level="DEBUG">
        <appender-ref ref="CONSOLE"/>
        <appender-ref ref="FILE"/>
    </root>

</configuration>
```

## Key Points

- **ThresholdFilter on CONSOLE**: `<level>INFO</level>` means only INFO and above reach stdout. DEBUG is filtered out at the appender level.
- **Root level is DEBUG**: Both appenders receive all DEBUG+ logs, but CONSOLE filters them. FILE gets everything.
- **Per-profile overrides**: `prod` can set root to INFO (file also gets INFO only). `dev`/`docker` keep DEBUG for the file.
- **File rotation**: SizeAndTimeBasedRollingPolicy rotates daily AND when file hits 50MB. 30-day retention, 1GB total cap.

## application.yml Cleanup

When `logback-spring.xml` exists, Spring Boot ignores `logging.level.*` in `application.yml`. Remove the conflicting block to avoid confusion:

```yaml
## 日志配置（控制台 INFO，文件 DEBUG，详见 logback-spring.xml）
```

## Verification

```bash
# XML validity
python3 -c "import xml.etree.ElementTree as ET; ET.parse('src/main/resources/logback-spring.xml')"

# YAML validity (no leftover logging block)
python3 -c "import yaml; yaml.safe_load(open('src/main/resources/application.yml'))"

# Compile
mvn compile -q
```
