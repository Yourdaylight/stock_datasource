#!/usr/bin/env bash
# =============================================================================
# start_receiver.sh — 在订阅节点上启动接收服务 (Go 二进制 rt-receiver)
# 位置: scripts/collection_and_push/start_receiver.sh
#
# 用法:
#   cd /root/stock_datasource  (或 /home/ubuntu/stock_datasource)
#   bash scripts/collection_and_push/start_receiver.sh
#
# 数据清理策略:
#   - 每天 9:00 由 Go 服务自动清理前一天的 spool / SQLite 数据
#   - 当天数据始终保留
#   - 启动脚本不再删除任何数据
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$PROJECT_DIR/logs"
BINARY="$SCRIPT_DIR/rt-receiver"

# ---------------------------------------------------------------------------
# 加载 .env
# ---------------------------------------------------------------------------
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  echo "[INFO] 已加载 $ENV_FILE"
else
  echo "[WARN] 未找到 $ENV_FILE，使用命令行参数或环境变量"
fi

# ---------------------------------------------------------------------------
# 检查二进制
# ---------------------------------------------------------------------------
if [[ ! -x "$BINARY" ]]; then
  echo "[ERROR] 找不到可执行文件: $BINARY"
  echo "        请先在开发机执行: cd go-rt-receiver && make"
  exit 1
fi

# ---------------------------------------------------------------------------
# 准备目录
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/data/received_push"

cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# 清理旧日志（仅清日志文件，数据由 Go 服务 9 点自动清理）
# ---------------------------------------------------------------------------
find "$LOG_DIR" -name "*.log" -mtime +1 -delete 2>/dev/null || true
echo "[OK]   旧日志已清理"

echo "============================================================"
echo "  订阅节点启动 — 接收推送数据 (Go)"
echo "  工作目录: $PROJECT_DIR"
echo "  日志目录: $LOG_DIR"
echo "============================================================"

# ---------------------------------------------------------------------------
# 启动接收服务
# ---------------------------------------------------------------------------
echo "[INFO] 启动接收服务 (端口 9100)..."
nohup "$BINARY" \
  --port 9100 \
  --push-token "${RT_KLINE_CLOUD_PUSH_TOKEN:-}" \
  --policy-token "${RT_STOCK_POLICY_TOKEN:-}" \
  --jwt-public-key-path "${RT_STOCK_JWT_PUBLIC_KEY_PATH:-}" \
  --flush-interval-seconds 5 \
  --data-dir "$PROJECT_DIR/data/received_push" \
  > "$LOG_DIR/receiver.log" 2>&1 &
RECEIVER_PID=$!
echo "[OK]   接收服务已启动 PID=$RECEIVER_PID"

# ---------------------------------------------------------------------------
# 等待启动 + 健康检查
# ---------------------------------------------------------------------------
echo "[INFO] 等待服务就绪..."
sleep 1

if curl -sS --connect-timeout 3 "http://127.0.0.1:9100/health" 2>/dev/null | grep -q '"ok"'; then
  echo "[OK]   健康检查通过"
else
  echo "[WARN] 健康检查未立即通过，可能需要几秒钟启动"
  echo "       请手动检查: curl http://127.0.0.1:9100/health"
fi

echo ""
echo "============================================================"
echo "  接收服务已启动:"
echo "    PID=$RECEIVER_PID"
echo "    端口: 9100"
echo ""
echo "  查看日志:"
echo "    tail -f $LOG_DIR/receiver.log"
echo ""
echo "  健康检查:"
echo "    curl http://127.0.0.1:9100/health"
echo "    curl http://127.0.0.1:9100/stats"
echo ""
echo "  停止进程:"
echo "    bash $SCRIPT_DIR/stop_all.sh"
echo "============================================================"
