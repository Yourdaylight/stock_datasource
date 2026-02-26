#!/usr/bin/env bash
# =============================================================================
# Chat API curl 测试脚本
# 用于快速验证智能对话模块的各个端点是否正常工作
#
# 用法:
#   bash tests/test_chat_curl.sh [BASE_URL]
#
# 参数:
#   BASE_URL  - API 基础地址, 默认 http://localhost:18080
#
# 环境变量 (可选):
#   TEST_EMAIL    - 测试账号邮箱 (默认自动注册)
#   TEST_PASSWORD - 测试账号密码 (默认自动注册)
#   AUTH_TOKEN    - 直接提供已有的 JWT token, 跳过登录
# =============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:18080}"
API_URL="${BASE_URL}/api"
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; SKIP_COUNT=$((SKIP_COUNT + 1)); }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_section() { echo -e "\n${BLUE}========== $1 ==========${NC}"; }

# 从 JSON 提取字段 (兼容无 jq 环境)
json_get() {
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))" 2>/dev/null
}

# =============================================================================
# 0. 健康检查
# =============================================================================
log_section "0. 服务健康检查"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/auth/me" -H "Authorization: Bearer invalid" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    log_fail "服务不可达: ${BASE_URL}"
    echo "请确认服务已启动。退出。"
    exit 1
else
    log_pass "服务可达 (HTTP $HTTP_CODE)"
fi

# =============================================================================
# 1. 认证 - 注册 & 登录
# =============================================================================
log_section "1. 认证测试"

if [ -n "${AUTH_TOKEN:-}" ]; then
    TOKEN="$AUTH_TOKEN"
    log_info "使用环境变量提供的 AUTH_TOKEN"
else
    TEST_EMAIL="${TEST_EMAIL:-chat_test_$(date +%s)@test.com}"
    TEST_PASSWORD="${TEST_PASSWORD:-TestPass123456}"

    # 注册
    log_info "注册测试账号: $TEST_EMAIL"
    REG_RESP=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"username\":\"chat_tester\"}")

    if echo "$REG_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('success') or '已注册' in d.get('detail','')" 2>/dev/null; then
        log_pass "注册成功或已存在"
    else
        log_fail "注册失败: $REG_RESP"
    fi

    # 登录
    LOGIN_RESP=$(curl -s -X POST "${API_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")

    TOKEN=$(echo "$LOGIN_RESP" | json_get access_token)
    if [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ] && [ "$TOKEN" != "" ]; then
        log_pass "登录成功, token: ${TOKEN:0:20}..."
    else
        log_fail "登录失败: $LOGIN_RESP"
        echo "无法继续测试，退出。"
        exit 1
    fi
fi

AUTH_HEADER="Authorization: Bearer ${TOKEN}"

# 验证 token
ME_RESP=$(curl -s "${API_URL}/auth/me" -H "$AUTH_HEADER")
USER_EMAIL=$(echo "$ME_RESP" | json_get email)
if [ -n "$USER_EMAIL" ] && [ "$USER_EMAIL" != "None" ]; then
    log_pass "Token 验证通过, 用户: $USER_EMAIL"
else
    log_fail "Token 无效: $ME_RESP"
    exit 1
fi

# =============================================================================
# 2. 会话管理
# =============================================================================
log_section "2. 会话管理测试"

# 2.1 创建会话
CREATE_RESP=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"curl自动化测试会话"}')

SESSION_ID=$(echo "$CREATE_RESP" | json_get session_id)
if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "None" ]; then
    log_pass "创建会话: $SESSION_ID"
else
    log_fail "创建会话失败: $CREATE_RESP"
    exit 1
fi

# 2.2 列出会话
LIST_RESP=$(curl -s "${API_URL}/chat/sessions?limit=5" -H "$AUTH_HEADER")
SESSION_COUNT=$(echo "$LIST_RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('sessions',[])))" 2>/dev/null)
if [ "$SESSION_COUNT" -gt 0 ] 2>/dev/null; then
    log_pass "列出会话: 共 $SESSION_COUNT 个"
else
    log_fail "列出会话失败: $LIST_RESP"
fi

# 2.3 更新标题
ENCODED_TITLE=$(python3 -c "import urllib.parse; print(urllib.parse.quote('更新后的标题'))")
TITLE_RESP=$(curl -s -X PUT "${API_URL}/chat/session/${SESSION_ID}/title?title=${ENCODED_TITLE}" \
    -H "$AUTH_HEADER")
if echo "$TITLE_RESP" | python3 -c "import sys,json; assert json.load(sys.stdin).get('success')" 2>/dev/null; then
    log_pass "更新会话标题"
else
    log_fail "更新标题失败: $TITLE_RESP"
fi

# =============================================================================
# 3. 流式对话测试 (核心)
# =============================================================================
log_section "3. 流式对话测试 (SSE)"

# --- 测试用例函数 ---
# 参数: $1=测试名称, $2=消息内容, $3=session_id, $4=超时秒数, $5=期望的agent(可选)
test_stream() {
    local test_name="$1"
    local message="$2"
    local sid="$3"
    local timeout="${4:-90}"
    local expected_agent="${5:-}"

    log_info "测试: $test_name (超时: ${timeout}s)"

    local tmpfile
    tmpfile=$(mktemp)

    curl -s -N -X POST "${API_URL}/chat/stream" \
        -H "Content-Type: application/json" \
        -H "$AUTH_HEADER" \
        -d "{\"session_id\":\"${sid}\",\"content\":\"${message}\"}" \
        --max-time "$timeout" > "$tmpfile" 2>&1

    local exit_code=$?

    # 检查是否收到 done 事件
    if grep -q '"type": "done"' "$tmpfile" || grep -q '"type":"done"' "$tmpfile"; then
        log_pass "$test_name - 收到 done 终止事件"
    else
        log_fail "$test_name - 未收到 done 事件 (exit_code=$exit_code)"
        log_info "最后几行输出:"
        tail -5 "$tmpfile" | head -5
        rm -f "$tmpfile"
        return 1
    fi

    # 检查是否有 content
    if grep -q '"type": "content"' "$tmpfile" || grep -q '"type":"content"' "$tmpfile"; then
        local content_events
        content_events=$(grep -c '"content"' "$tmpfile" || echo 0)
        log_pass "$test_name - 收到内容 ($content_events 个 content 事件)"
    else
        log_fail "$test_name - 没有收到任何内容"
    fi

    # 检查是否有错误 (有 done+content 的情况下 error 只是工具级警告, 不算失败)
    if grep -q '"type": "error"' "$tmpfile" || grep -q '"type":"error"' "$tmpfile"; then
        local error_msg
        error_msg=$(grep '"error"' "$tmpfile" | head -1 | python3 -c "import sys,json; line=sys.stdin.readline().strip(); d=json.loads(line.replace('data: ','')); print(d.get('error',''))" 2>/dev/null || echo "unknown")
        local has_done has_content
        has_done=$(grep -c '"type": "done"\|"type":"done"' "$tmpfile" || echo 0)
        has_content=$(grep -c '"type": "content"\|"type":"content"' "$tmpfile" || echo 0)
        if [ "$has_done" -gt 0 ] && [ "$has_content" -gt 0 ]; then
            log_info "$test_name - 包含工具级错误 (不影响整体): $error_msg"
        else
            log_fail "$test_name - 包含致命错误事件: $error_msg"
        fi
    fi

    # 检查路由到的 agent
    if [ -n "$expected_agent" ]; then
        if grep -q "\"$expected_agent\"" "$tmpfile"; then
            log_pass "$test_name - 正确路由到 $expected_agent"
        else
            log_fail "$test_name - 未路由到期望的 $expected_agent"
        fi
    fi

    rm -f "$tmpfile"
}

# 3.1 简单问候 -> ChatAgent
test_stream "简单问候" "你好" "$SESSION_ID" 60 "ChatAgent"

# 3.2 创建新会话测试港股分析 -> MarketAgent + HKReportAgent
HK_SESSION=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"港股分析测试"}' | json_get session_id)

if [ -n "$HK_SESSION" ] && [ "$HK_SESSION" != "None" ]; then
    test_stream "港股分析 (00700.HK)" "分析腾讯控股 00700.HK" "$HK_SESSION" 120 "MarketAgent"
else
    log_skip "港股分析测试 - 创建会话失败"
fi

# 3.3 市场概览 -> OverviewAgent
OV_SESSION=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"市场概览测试"}' | json_get session_id)

if [ -n "$OV_SESSION" ] && [ "$OV_SESSION" != "None" ]; then
    test_stream "市场概览" "A股今天行情怎么样" "$OV_SESSION" 90 "OverviewAgent"
else
    log_skip "市场概览测试 - 创建会话失败"
fi

# 3.4 个股技术分析 -> MarketAgent
MA_SESSION=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"个股分析测试"}' | json_get session_id)

if [ -n "$MA_SESSION" ] && [ "$MA_SESSION" != "None" ]; then
    test_stream "个股技术分析" "分析贵州茅台 600519 的K线走势" "$MA_SESSION" 120 "MarketAgent"
else
    log_skip "个股技术分析测试 - 创建会话失败"
fi

# 3.5 智能选股 -> ScreenerAgent
SC_SESSION=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"选股测试"}' | json_get session_id)

if [ -n "$SC_SESSION" ] && [ "$SC_SESSION" != "None" ]; then
    test_stream "智能选股" "帮我筛选市盈率低于20且ROE大于15%的股票" "$SC_SESSION" 120 "ScreenerAgent"
else
    log_skip "智能选股测试 - 创建会话失败"
fi

# 3.6 GET 方式的流式请求
log_info "测试: GET 方式流式请求"
GET_SESSION=$(curl -s -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"title":"GET流式测试"}' | json_get session_id)

if [ -n "$GET_SESSION" ] && [ "$GET_SESSION" != "None" ]; then
    GET_TMP=$(mktemp)
    ENCODED_CONTENT=$(python3 -c "import urllib.parse; print(urllib.parse.quote('上证指数最新点位'))")
    curl -s -N "${API_URL}/chat/stream?session_id=${GET_SESSION}&content=${ENCODED_CONTENT}" \
        -H "$AUTH_HEADER" \
        --max-time 90 > "$GET_TMP" 2>&1

    if grep -q '"type": "done"' "$GET_TMP" || grep -q '"type":"done"' "$GET_TMP"; then
        log_pass "GET 流式请求 - 收到 done 事件"
    else
        log_fail "GET 流式请求 - 未收到 done 事件"
    fi
    rm -f "$GET_TMP"
else
    log_skip "GET 流式请求 - 创建会话失败"
fi

# =============================================================================
# 4. 历史记录
# =============================================================================
log_section "4. 历史记录测试"

HISTORY_RESP=$(curl -s "${API_URL}/chat/history?session_id=${SESSION_ID}" -H "$AUTH_HEADER")
MSG_COUNT=$(echo "$HISTORY_RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('messages',[])))" 2>/dev/null)
if [ "$MSG_COUNT" -gt 0 ] 2>/dev/null; then
    log_pass "获取历史记录: $MSG_COUNT 条消息"
else
    log_fail "获取历史记录失败: $HISTORY_RESP"
fi

# =============================================================================
# 5. 权限测试
# =============================================================================
log_section "5. 权限测试"

# 5.1 无 token 访问
NOAUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" -d '{"title":"test"}')
if [ "$NOAUTH_CODE" = "403" ] || [ "$NOAUTH_CODE" = "401" ]; then
    log_pass "无 token 访问被拒绝 (HTTP $NOAUTH_CODE)"
else
    log_fail "无 token 访问未被拒绝 (HTTP $NOAUTH_CODE)"
fi

# 5.2 无效 token 访问
BADAUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/chat/session" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer invalid_token_12345" \
    -d '{"title":"test"}')
if [ "$BADAUTH_CODE" = "403" ] || [ "$BADAUTH_CODE" = "401" ]; then
    log_pass "无效 token 被拒绝 (HTTP $BADAUTH_CODE)"
else
    log_fail "无效 token 未被拒绝 (HTTP $BADAUTH_CODE)"
fi

# =============================================================================
# 6. 清理 - 删除测试会话
# =============================================================================
log_section "6. 清理测试数据"

for sid in "$SESSION_ID" "${HK_SESSION:-}" "${OV_SESSION:-}" "${MA_SESSION:-}" "${SC_SESSION:-}" "${GET_SESSION:-}"; do
    if [ -n "$sid" ] && [ "$sid" != "None" ]; then
        DEL_RESP=$(curl -s -X DELETE "${API_URL}/chat/session/${sid}" -H "$AUTH_HEADER")
        if echo "$DEL_RESP" | python3 -c "import sys,json; assert json.load(sys.stdin).get('success')" 2>/dev/null; then
            log_pass "删除会话: $sid"
        else
            log_fail "删除会话失败: $sid - $DEL_RESP"
        fi
    fi
done

# =============================================================================
# 结果汇总
# =============================================================================
log_section "测试结果汇总"
echo -e "通过: ${GREEN}${PASS_COUNT}${NC}"
echo -e "失败: ${RED}${FAIL_COUNT}${NC}"
echo -e "跳过: ${YELLOW}${SKIP_COUNT}${NC}"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}存在失败的测试用例！${NC}"
    exit 1
else
    echo -e "${GREEN}所有测试通过！${NC}"
    exit 0
fi
