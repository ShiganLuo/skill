# Worker One-Click Deployment Script

For compute nodes (bioplatform-worker) deployed on internal servers without Docker/sudo.

## Script Template

Location: `bioplatform-worker/deploy.sh`

```bash
#!/bin/bash
set -e
WORKER_DIR="$(cd "$(dirname "$0")" && pwd)"
JAR_NAME="bioplatform-worker.jar"
PID_FILE="$WORKER_DIR/worker.pid"
LOG_FILE="$WORKER_DIR/worker.log"
JAVA="java"  # Use PATH — never hardcode JAVA_HOME; users always have java in PATH but not JAVA_HOME

build() {
    cd "$WORKER_DIR" && mvn clean package -q -DskipTests
}

start() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null && { echo "Already running"; return; }
    [ ! -f "$WORKER_DIR/target/$JAR_NAME" ] && build
    nohup $JAVA -Xms128m -Xmx512m -jar "$WORKER_DIR/target/$JAR_NAME" \
        --server.port=18081 > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
}

stop() {
    [ -f "$PID_FILE" ] && { kill "$(cat $PID_FILE)" 2>/dev/null; rm -f "$PID_FILE"; }
}

case "$1" in
    build) build ;;
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null && echo "Running" || echo "Stopped" ;;
    *) echo "Usage: $0 {build|start|stop|restart|status}" ;;
esac
```

## Key Points

- Worker listens on port 18081 (distinct from Gateway's 8080)
- No root required — runs under user account
- Uses `java` from PATH — never hardcode JAVA_HOME; users always have java in PATH but not JAVA_HOME
- `mvn` also from PATH
- PID file for clean stop/restart
- Health check: `curl http://localhost:18081/worker/health`

## Deployment Steps on Internal Server

1. Install JDK 17 to `~/jdk/jdk-17` (tar.gz, no sudo needed)
2. Clone repo or copy `bioplatform-worker/` directory
3. `bash deploy.sh build` to compile
4. `bash deploy.sh start` to launch
5. In Gateway admin UI, add the node via SSH tunnel address (e.g., `http://localhost:18081`)
