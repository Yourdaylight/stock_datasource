#!/bin/bash
# =============================================================================
# 港股智能分析端到端测试脚本
# 
# 使用方式:
#   1. 确保后端服务运行中: python -m stock_datasource.services.http_server
#   2. 设置环境变量或修改下方默认值
#   3. 运行: bash scripts/test_hk_smart_analysis.sh
#
# 环境变量:
#   BASE_URL   - API基础地址 (默认 http://localhost:8000)
#   USER_EMAIL - 测试用户邮箱
#   USER_PASS  - 测试用户密码
#   TOKEN      - 直接指定JWT Token（跳过登录步骤）
# =============================================================================

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
USER_EMAIL="${USER_EMAIL:-test@example.com}"
USER_PASS="${USER_PASS:-test123456}"

echo "============================================"
echo " 港股智能分析 - 端到端测试"
echo " BASE_URL: ${BASE_URL}"
echo "============================================"
echo ""

# ---------------------------
# Step 0: Login to get token
# ---------------------------
if [ -z "$TOKEN" ]; then
  echo ">>> Step 0: 登录获取Token..."
  LOGIN_RESP=$(curl -s -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${USER_EMAIL}\", \"password\": \"${USER_PASS}\"}")
  
  TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || true)
  
  if [ -z "$TOKEN" ]; then
    echo "❌ 登录失败，响应: $LOGIN_RESP"
    echo ""
    echo "请设置 TOKEN 环境变量直接跳过登录:"
    echo "  export TOKEN=your_jwt_token"
    echo "  bash scripts/test_hk_smart_analysis.sh"
    exit 1
  fi
  echo "✅ 登录成功，Token: ${TOKEN:0:20}..."
else
  echo ">>> 使用已有Token: ${TOKEN:0:20}..."
fi
echo ""

AUTH_HEADER="Authorization: Bearer ${TOKEN}"

# ---------------------------
# Step 1: Create chat session
# ---------------------------
echo ">>> Step 1: 创建聊天会话..."
SESSION_RESP=$(curl -s -X POST "${BASE_URL}/api/chat/session" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d '{"title": "港股分析测试"}')

SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', ''))" 2>/dev/null || true)

if [ -z "$SESSION_ID" ]; then
  echo "❌ 创建会话失败: $SESSION_RESP"
  exit 1
fi
echo "✅ 会话ID: ${SESSION_ID}"
echo ""

# =============================================================================
# 测试场景 1: 港股技术指标分析
# 用户提问: "分析 00700.HK 的技术指标"
# 预期: MarketAgent 返回 MACD/RSI/KDJ 等技术指标
# =============================================================================
echo "============================================"
echo " 测试场景 1: 港股技术指标分析"
echo " 问题: 分析 00700.HK 的技术指标"
echo "============================================"

echo '--- curl 命令 (可复用) ---'
cat << 'CURL_CMD'
curl -N -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"session_id": "${SESSION_ID}", "content": "分析 00700.HK 的技术指标"}'
CURL_CMD
echo '--- 执行中 ---'

curl -N -s -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"content\": \"分析 00700.HK 的技术指标\"}" \
  --max-time 120 2>&1 | head -100

echo ""
echo ">>> 等待 3 秒后继续..."
sleep 3
echo ""

# =============================================================================
# 测试场景 2: 港股财报分析（纯财报，不应触发MarketAgent）
# 用户提问: "00700.HK 财报分析"
# 预期: HKReportAgent 返回三大报表分析
# =============================================================================
echo "============================================"
echo " 测试场景 2: 港股财报分析"
echo " 问题: 00700.HK 财报分析"
echo "============================================"

echo '--- curl 命令 (可复用) ---'
cat << 'CURL_CMD'
curl -N -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"session_id": "${SESSION_ID}", "content": "00700.HK 财报分析"}'
CURL_CMD
echo '--- 执行中 ---'

curl -N -s -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"content\": \"00700.HK 财报分析\"}" \
  --max-time 120 2>&1 | head -100

echo ""
echo ">>> 等待 3 秒后继续..."
sleep 3
echo ""

# =============================================================================
# 测试场景 3: 港股综合分析（技术面+基本面）
# 用户提问: "全面分析腾讯 00700.HK 的技术面和财务情况"
# 预期: MarketAgent + HKReportAgent 并发执行
# =============================================================================
echo "============================================"
echo " 测试场景 3: 港股综合分析（技术面+基本面）"
echo " 问题: 全面分析腾讯 00700.HK 的技术面和财务情况"
echo "============================================"

echo '--- curl 命令 (可复用) ---'
cat << 'CURL_CMD'
curl -N -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"session_id": "${SESSION_ID}", "content": "全面分析腾讯 00700.HK 的技术面和财务情况"}'
CURL_CMD
echo '--- 执行中 ---'

curl -N -s -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"content\": \"全面分析腾讯 00700.HK 的技术面和财务情况\"}" \
  --max-time 120 2>&1 | head -150

echo ""
echo ">>> 等待 3 秒后继续..."
sleep 3
echo ""

# =============================================================================
# 测试场景 4: A股分析不受影响
# 用户提问: "分析 600519.SH 的技术指标和财务情况"
# 预期: MarketAgent + ReportAgent 并发执行（原有逻辑不变）
# =============================================================================
echo "============================================"
echo " 测试场景 4: A股分析不受影响"
echo " 问题: 分析 600519.SH 的技术指标和财务情况"
echo "============================================"

echo '--- curl 命令 (可复用) ---'
cat << 'CURL_CMD'
curl -N -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"session_id": "${SESSION_ID}", "content": "分析 600519.SH 的技术指标和财务情况"}'
CURL_CMD
echo '--- 执行中 ---'

curl -N -s -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"content\": \"分析 600519.SH 的技术指标和财务情况\"}" \
  --max-time 120 2>&1 | head -100

echo ""
echo ">>> 等待 3 秒后继续..."
sleep 3
echo ""

# =============================================================================
# 测试场景 5: 跨市场对比（进阶场景）
# 用户提问: "对比分析 600519.SH 和 00700.HK"
# 预期: 正确路由到各自市场的 Agent
# =============================================================================
echo "============================================"
echo " 测试场景 5: 跨市场对比"
echo " 问题: 对比分析 600519.SH 和 00700.HK 的走势"
echo "============================================"

echo '--- curl 命令 (可复用) ---'
cat << 'CURL_CMD'
curl -N -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"session_id": "${SESSION_ID}", "content": "对比分析 600519.SH 和 00700.HK 的走势"}'
CURL_CMD
echo '--- 执行中 ---'

curl -N -s -X POST "${BASE_URL}/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "${AUTH_HEADER}" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"content\": \"对比分析 600519.SH 和 00700.HK 的走势\"}" \
  --max-time 120 2>&1 | head -100

echo ""
echo ""
echo "============================================"
echo " 所有测试场景执行完毕！"
echo "============================================"
echo ""
echo "可复用的单独 curl 命令（替换 TOKEN 和 SESSION_ID 即可）："
echo ""
echo "# 场景1: 港股技术指标"
echo "curl -N -X POST '${BASE_URL}/api/chat/stream' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "  -d '{\"session_id\": \"YOUR_SESSION_ID\", \"content\": \"分析 00700.HK 的技术指标\"}'"
echo ""
echo "# 场景2: 港股财报"
echo "curl -N -X POST '${BASE_URL}/api/chat/stream' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "  -d '{\"session_id\": \"YOUR_SESSION_ID\", \"content\": \"00700.HK 财报分析\"}'"
echo ""
echo "# 场景3: 港股综合分析"
echo "curl -N -X POST '${BASE_URL}/api/chat/stream' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "  -d '{\"session_id\": \"YOUR_SESSION_ID\", \"content\": \"全面分析腾讯 00700.HK 的技术面和财务情况\"}'"
echo ""
echo "# 场景4: A股不受影响"
echo "curl -N -X POST '${BASE_URL}/api/chat/stream' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "  -d '{\"session_id\": \"YOUR_SESSION_ID\", \"content\": \"分析 600519.SH 的技术指标和财务情况\"}'"
echo ""
