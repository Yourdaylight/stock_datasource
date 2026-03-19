#!/usr/bin/env bash
# =============================================================================
# start_proxy.sh — 在代理服务器上启动采集 + 推送进程
# 位置: scripts/collection_and_push/start_proxy.sh
#
# 用法:
#   cd /root/stock_datasource
#   bash scripts/collection_and_push/start_proxy.sh
#
# 启动内容:
#   1) 采集进程 (csv_pipeline.py --disable-push)
#   2) 推送进程1 → 节点1+节点3 (A股，多目标合并推送)
#   3) 推送进程2 → 节点2 (ETF)
#   4) 推送进程3 → 节点1+节点2+节点3 (港股，三节点推送)
#
# 优化 v3: 节点1和节点3都推A股，合并为一个进程（多目标推送），
#           CPU 降低约 30%（省掉一个完整 Python 进程的 pandas 序列化开销）
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
  echo "[ERROR] 未找到 $ENV_FILE，请先创建配置文件"
  exit 1
fi

# ---------------------------------------------------------------------------
# 校验必要变量
# ---------------------------------------------------------------------------
if [[ -z "${TUSHARE_TOKEN:-}" ]]; then
  echo "[ERROR] TUSHARE_TOKEN 未设置"
  exit 1
fi
if [[ -z "${RT_KLINE_CLOUD_PUSH_TOKEN:-}" ]]; then
  echo "[ERROR] RT_KLINE_CLOUD_PUSH_TOKEN 未设置"
  exit 1
fi

# ---------------------------------------------------------------------------
# 节点地址（从 .env 读取）
# ---------------------------------------------------------------------------
if [[ -z "${NODE1_URL:-}" ]]; then
  echo "[ERROR] NODE1_URL 未设置，请在 .env 中配置"
  exit 1
fi
if [[ -z "${NODE2_URL:-}" ]]; then
  echo "[ERROR] NODE2_URL 未设置，请在 .env 中配置"
  exit 1
fi
if [[ -z "${NODE3_URL:-}" ]]; then
  echo "[ERROR] NODE3_URL 未设置，请在 .env 中配置"
  exit 1
fi

# ---------------------------------------------------------------------------
# 准备目录
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/data/tushare_csv"

cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# 清理前一天的旧数据（CSV 文件 / checkpoint / 旧日志）
# ---------------------------------------------------------------------------
echo "[INFO] 清理前一天的旧数据..."

# 清理旧 CSV 文件（超过1天的）
find "$PROJECT_DIR/data/tushare_csv" -name "*.csv" -mtime +0 -delete 2>/dev/null || true
echo "[OK]   旧 CSV 文件已清理"

# 清理推送断点文件（新一天需要全量重推）
rm -f "$PROJECT_DIR/data/push_ckpt_node1_3.json" \
      "$PROJECT_DIR/data/push_ckpt_node2.json" \
      "$PROJECT_DIR/data/push_ckpt_hk_all.json" \
      "$PROJECT_DIR/data/push_ckpt_node1.json" \
      "$PROJECT_DIR/data/push_ckpt_node3.json" \
      "$PROJECT_DIR/data/push_ckpt_local.json" \
      "$PROJECT_DIR/data/push_checkpoint.json" 2>/dev/null || true
echo "[OK]   推送断点已清理"

# 清理旧日志
find "$LOG_DIR" -name "*.log" -mtime +0 -delete 2>/dev/null || true
echo "[OK]   旧日志已清理"

echo "============================================================"
echo "  代理服务器启动 — CSV 采集 + 多节点推送 (优化 v3)"
echo "  工作目录: $PROJECT_DIR"
echo "  日志目录: $LOG_DIR"
echo "============================================================"

# ---------------------------------------------------------------------------
# CPU 保护：所有 Python 进程以最低优先级运行（nice 19）
# 确保 SSH/系统进程永远能抢到 CPU，不会因为 Python 打满而断连
# ---------------------------------------------------------------------------
NICE="nice -n 19 ionice -c 3"

# ---------------------------------------------------------------------------
# 1) 采集进程（仅采集，不推送）
#    优化：--market-inner-concurrency 2 限制市场内并行查询数，减少 CPU 峰值
# ---------------------------------------------------------------------------
echo "[INFO] 启动采集进程（nice 19 低优先级）..."
nohup $NICE python3 "$SCRIPT_DIR/csv_pipeline.py" \
  --env-file "$ENV_FILE" \
  --disable-push \
  --markets a_stock,etf,index,hk \
  --collect-interval 3.0 \
  --cleanup-interval 7200 \
  --max-age-days 1 \
  > "$LOG_DIR/collect.log" 2>&1 &
COLLECT_PID=$!
echo "[OK]   采集进程已启动 PID=$COLLECT_PID (nice 19)"

# ---------------------------------------------------------------------------
# 2) 推送进程1 → 节点1+节点3 (A股，多目标合并推送)
#    v3 优化：一份数据序列化一次，并行推到两个节点
#    频率不变：--interval 5.0
# ---------------------------------------------------------------------------
echo "[INFO] 启动推送进程 → 节点1+节点3 (A股，多目标合并，nice 19)..."
nohup $NICE python3 "$SCRIPT_DIR/push_csv_to_cloud.py" \
  --markets a_stock \
  --push-url "$NODE1_URL,$NODE3_URL" \
  --push-token "$RT_KLINE_CLOUD_PUSH_TOKEN" \
  --batch-size 3000 \
  --loop --interval 5.0 \
  --checkpoint-file "$PROJECT_DIR/data/push_ckpt_node1_3.json" \
  > "$LOG_DIR/push_node1_3.log" 2>&1 &
PUSH1_PID=$!
echo "[OK]   推送进程1 已启动 PID=$PUSH1_PID → $NODE1_URL + $NODE3_URL"

# ---------------------------------------------------------------------------
# 3) 推送进程2 → 节点2 (ETF)
#    频率不变：--interval 5.0
# ---------------------------------------------------------------------------
echo "[INFO] 启动推送进程 → 节点2 (ETF，nice 19)..."
nohup $NICE python3 "$SCRIPT_DIR/push_csv_to_cloud.py" \
  --markets etf \
  --push-url "$NODE2_URL" \
  --push-token "$RT_KLINE_CLOUD_PUSH_TOKEN" \
  --batch-size 3000 \
  --loop --interval 5.0 \
  --checkpoint-file "$PROJECT_DIR/data/push_ckpt_node2.json" \
  > "$LOG_DIR/push_node2.log" 2>&1 &
PUSH2_PID=$!
echo "[OK]   推送进程2 已启动 PID=$PUSH2_PID → $NODE2_URL"

# ---------------------------------------------------------------------------
# 4) 推送进程3 → 三个节点 (港股，多目标合并推送)
#    港股推送到所有三个节点
#    频率不变：--interval 5.0
# ---------------------------------------------------------------------------
echo "[INFO] 启动推送进程 → 节点1+节点2+节点3 (港股，三节点，nice 19)..."
nohup $NICE python3 "$SCRIPT_DIR/push_csv_to_cloud.py" \
  --markets hk \
  --push-url "$NODE1_URL,$NODE2_URL,$NODE3_URL" \
  --push-token "$RT_KLINE_CLOUD_PUSH_TOKEN" \
  --batch-size 3000 \
  --loop --interval 5.0 \
  --checkpoint-file "$PROJECT_DIR/data/push_ckpt_hk_all.json" \
  > "$LOG_DIR/push_hk_all.log" 2>&1 &
PUSH3_PID=$!
echo "[OK]   推送进程3 已启动 PID=$PUSH3_PID → $NODE1_URL + $NODE2_URL + $NODE3_URL"

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  所有进程已启动 (4个进程, nice 19 低优先级保护):"
echo "    采集进程       PID=$COLLECT_PID (nice 19)"
echo "    推送→节点1+3   PID=$PUSH1_PID (A股，多目标, nice 19)"
echo "    推送→节点2     PID=$PUSH2_PID (ETF, nice 19)"
echo "    推送→三节点    PID=$PUSH3_PID (港股→节点1+2+3, nice 19)"
echo ""
echo "  CPU 保护: nice -n 19 + ionice -c 3 (SSH/系统进程优先)"
echo "  推送频率: 不变 (interval=5.0s)"
echo ""
echo "  查看日志:"
echo "    tail -f $LOG_DIR/collect.log"
echo "    tail -f $LOG_DIR/push_node1_3.log"
echo "    tail -f $LOG_DIR/push_node2.log"
echo "    tail -f $LOG_DIR/push_hk_all.log"
echo ""
echo "  停止所有进程:"
echo "    bash $SCRIPT_DIR/stop_all.sh"
echo "============================================================"
