#!/bin/bash
# 生信云平台 API 全面测试脚本
# 用法: bash test-api.sh [base_url]
# 默认 base_url=http://localhost:8080

BASE_URL="${1:-http://localhost:8080}"
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_api() {
    local method=$1 url=$2 desc=$3 data=$4 token=$5
    local http_code body

    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        if [ -n "$token" ]; then
            body=$(curl -s -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d "$data" "$url" 2>/dev/null)
        else
            body=$(curl -s -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null)
        fi
    elif [ "$method" = "PUT" ] && [ -n "$data" ]; then
        if [ -n "$token" ]; then
            body=$(curl -s -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d "$data" "$url" 2>/dev/null)
        else
            body=$(curl -s -X PUT -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null)
        fi
    elif [ "$method" = "DELETE" ]; then
        if [ -n "$token" ]; then
            body=$(curl -s -X DELETE -H "Authorization: Bearer $token" "$url" 2>/dev/null)
        else
            body=$(curl -s -X DELETE "$url" 2>/dev/null)
        fi
    else
        if [ -n "$token" ]; then
            body=$(curl -s -X $method -H "Authorization: Bearer $token" "$url" 2>/dev/null)
        else
            body=$(curl -s -X $method "$url" 2>/dev/null)
        fi
    fi

    if [ -n "$token" ]; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -X $method -H "Authorization: Bearer $token" "$url" 2>/dev/null)
    else
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -X $method "$url" 2>/dev/null)
    fi

    local code=$(echo "$body" | grep -o '"code":[0-9]*' | head -1 | cut -d: -f2)

    if [ "$http_code" = "200" ] && [ "$code" = "200" ]; then
        echo -e "${GREEN}✓${NC} $desc (HTTP:${http_code}, code:${code})"
        PASS=$((PASS+1))
    else
        echo -e "${RED}✗${NC} $desc (HTTP:${http_code:-N/A}, code:${code:-N/A})"
        if [ -n "$body" ]; then
            local msg=$(echo "$body" | grep -o '"message":"[^"]*"' | head -1)
            [ -n "$msg" ] && echo -e "    ${YELLOW}→ $msg${NC}"
        fi
        FAIL=$((FAIL+1))
    fi
}

echo "=========================================="
echo "  API 全面测试 - $BASE_URL"
echo "=========================================="
echo ""

# === 登录获取Token ===
echo -e "${YELLOW}[认证]${NC}"
test_api POST "$BASE_URL/api/admin/auth/login" "Admin登录" '{"username":"admin","password":"admin123"}'
TOKEN=$(curl -s -X POST "$BASE_URL/api/admin/auth/login" -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' 2>/dev/null | grep -o '"accessToken":"[^"]*"' | cut -d'"' -f4)
if [ -z "$TOKEN" ]; then
    echo -e "${RED}无法获取Token，终止测试${NC}"; exit 1
fi
test_api GET "$BASE_URL/api/admin/auth/userInfo" "用户信息" "" "$TOKEN"
echo ""

# === 公开接口 ===
echo -e "${YELLOW}[公开接口]${NC}"
test_api GET "$BASE_URL/api/front/projects/list" "公开项目"
test_api GET "$BASE_URL/api/front/pipelines/list" "公开流程"
test_api GET "$BASE_URL/api/front/agent/tools" "Agent工具"
echo ""

# === 管理后台CRUD ===
echo -e "${YELLOW}[CRUD测试]${NC}"
test_api GET "$BASE_URL/api/admin/projects/list?pageNum=1&pageSize=10" "项目列表" "" "$TOKEN"
test_api POST "$BASE_URL/api/admin/projects/create" "创建项目" '{"name":"test","description":"test","ownerId":1}' "$TOKEN"
PID=$(curl -s "$BASE_URL/api/admin/projects/list?pageNum=1&pageSize=1" -H "Authorization: Bearer $TOKEN" 2>/dev/null | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
[ -n "$PID" ] && test_api DELETE "$BASE_URL/api/admin/projects/$PID" "删除项目" "" "$TOKEN"

test_api GET "$BASE_URL/api/admin/pipelines/list?pageNum=1&pageSize=10" "流程列表" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/executions/list?pageNum=1&pageSize=10" "执行列表" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/datafiles/list?projectId=1&pageNum=1&pageSize=10" "数据文件" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/users/list?pageNum=1&pageSize=10" "用户列表" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/roles/list" "角色列表" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/system/configs" "系统配置" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/system/dashboard" "Dashboard" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/agent/tools" "Agent工具" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/agent/conversations" "对话列表" "" "$TOKEN"
test_api GET "$BASE_URL/api/admin/logs/list?pageNum=1&pageSize=10" "操作日志" "" "$TOKEN"
echo ""

echo "========================================="
echo -e "结果: ${GREEN}通过 $PASS${NC} / ${RED}失败 $FAIL${NC} / 总计 $((PASS+FAIL))"
echo "========================================="
[ $FAIL -eq 0 ] && echo -e "${GREEN}🎉 全部通过！${NC}" || echo -e "${RED}有失败项需要修复${NC}"
exit $FAIL
