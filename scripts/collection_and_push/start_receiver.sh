#!/usr/bin/env bash
# =============================================================================
# start_receiver.sh — 在订阅节点上启动接收服务
# 位置: scripts/collection_and_push/start_receiver.sh
#
# 用法:
#   cd /root/stock_datasource  (或 /home/ubuntu/stock_datasource)
#   bash scripts/collection_and_push/start_receiver.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_DIR="$PROJECT_DIR/logs"

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
# 准备目录
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/data/received_push"

cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# 清理前一天的旧数据（spool / snapshot / checkpoint / 旧日志）
# ---------------------------------------------------------------------------
echo "[INFO] 清理前一天的旧数据..."
DATA_DIR="$PROJECT_DIR/data/received_push"

# 清理 spool 目录中的 .jsonl 文件（按日期命名，如 20260317.jsonl）
if [[ -d "$DATA_DIR/spool" ]]; then
  find "$DATA_DIR/spool" -name "*.jsonl" -mtime +0 -delete 2>/dev/null || true
  # 删除空目录
  find "$DATA_DIR/spool" -mindepth 1 -type d -empty -delete 2>/dev/null || true
  echo "[OK]   spool 旧文件已清理"
fi

# 清理 snapshot 中的 SQLite 数据库（直接删除重建更干净）
if [[ -f "$DATA_DIR/snapshot/rt_snapshot.db" ]]; then
  rm -f "$DATA_DIR/snapshot/rt_snapshot.db" \
        "$DATA_DIR/snapshot/rt_snapshot.db-shm" \
        "$DATA_DIR/snapshot/rt_snapshot.db-wal" \
        "$DATA_DIR/snapshot/.builder.lock" 2>/dev/null || true
  echo "[OK]   snapshot 旧数据库已清理"
fi

# 清理旧的 CSV 快照
find "$DATA_DIR/snapshot" -name "*.csv" -mtime +0 -delete 2>/dev/null || true

# 清理旧日志
find "$LOG_DIR" -name "*.log" -mtime +0 -delete 2>/dev/null || true
echo "[OK]   旧日志已清理"

echo "============================================================"
echo "  订阅节点启动 — 接收推送数据"
echo "  工作目录: $PROJECT_DIR"
echo "  日志目录: $LOG_DIR"
echo "============================================================"

# ---------------------------------------------------------------------------
# 启动接收服务
# ---------------------------------------------------------------------------
echo "[INFO] 启动接收服务 (端口 9100, spool 自动清理)..."
nohup python3 "$SCRIPT_DIR/receive_push_data.py" \
  --port 9100 \
  --push-token "${RT_KLINE_CLOUD_PUSH_TOKEN:-}" \
  --flush-interval-seconds 5 \
  --spool-max-age-days 1 \
  --data-dir "$PROJECT_DIR/data/received_push" \
  > "$LOG_DIR/receiver.log" 2>&1 &
RECEIVER_PID=$!
echo "[OK]   接收服务已启动 PID=$RECEIVER_PID"

# ---------------------------------------------------------------------------
# 等待启动 + 健康检查
# ---------------------------------------------------------------------------
echo "[INFO] 等待服务就绪..."
sleep 2

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
