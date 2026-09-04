#!/bin/bash
# Pre-deploy config sync checker
# Usage: bash verify-deploy-config.sh <project-root>
# Checks Redis/MinIO/MySQL passwords are consistent across all config sources
set -e
ROOT="${1:-.}"
PASS=0; FAIL=0

check() {
  if eval "$1"; then
    echo "PASS: $2"; PASS=$((PASS+1))
  else
    echo "FAIL: $2"; FAIL=$((FAIL+1))
  fi
}

# Find config files
DEV_YML=$(find "$ROOT" -name 'application-dev.yml' -not -path '*/target/*' | head -1)
PROD_YML=$(find "$ROOT" -name 'application-prod.yml' -not -path '*/target/*' | head -1)
REDIS_CONF=$(find "$ROOT" -name 'redis.conf' -not -path '*/database/*' | head -1)
COMPOSE_REMOTE=$(find "$ROOT" -name 'docker-compose-remote.yml' | head -1)

if [ -z "$PROD_YML" ]; then echo "ERROR: application-prod.yml not found"; exit 1; fi

# --- Redis ---
if [ -n "$REDIS_CONF" ]; then
  PROD_REDIS_PW=$(grep 'password:' "$PROD_YML" | head -2 | tail -1 | awk '{print $2}')
  CONF_REDIS_PW=$(awk '/^requirepass/{print $2}' "$REDIS_CONF")
  check '[ "$PROD_REDIS_PW" = "$CONF_REDIS_PW" ]' \
    "Redis: prod.yml [$PROD_REDIS_PW] == redis.conf [$CONF_REDIS_PW]"

  if [ -n "$DEV_YML" ]; then
    DEV_REDIS_PW=$(grep 'password:' "$DEV_YML" | head -2 | tail -1 | awk '{print $2}')
    echo "INFO: dev Redis password = $DEV_REDIS_PW (may differ from prod)"
  fi
else
  echo "SKIP: redis.conf not found"
fi

# --- MinIO (remote compose) ---
if [ -n "$COMPOSE_REMOTE" ]; then
  MKEY=$(grep MINIO_SECRET_KEY "$COMPOSE_REMOTE" | head -1 | cut -d= -f2)
  MPW=$(grep MINIO_ROOT_PASSWORD "$COMPOSE_REMOTE" | head -1 | awk -F': ' '{print $2}' | awk '{print $1}')
  check '[ "$MKEY" = "$MPW" ]' \
    "MinIO: SECRET_KEY [$MKEY] == ROOT_PASSWORD [$MPW]"
else
  echo "SKIP: docker-compose-remote.yml not found"
fi

# --- MySQL ---
if [ -n "$COMPOSE_REMOTE" ] && [ -n "$PROD_YML" ]; then
  PROD_MYSQL_PW=$(grep 'password:' "$PROD_YML" | head -1 | awk '{print $2}')
  COMPOSE_MYSQL_PW=$(grep MYSQL_ROOT_PASSWORD "$COMPOSE_REMOTE" | head -1 | awk -F': ' '{print $2}' | awk '{print $1}')
  check '[ "$PROD_MYSQL_PW" = "$COMPOSE_MYSQL_PW" ]' \
    "MySQL: prod.yml [$PROD_MYSQL_PW] == compose [$COMPOSE_MYSQL_PW]"
fi

echo "---"
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
