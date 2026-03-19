#!/usr/bin/env bash
# =============================================================================
# check_status.sh — 检查进程状态 + 健康检查
# 位置: scripts/collection_and_push/check_status.sh
#
# 用法:
#   bash scripts/collection_and_push/check_status.sh           # 检查本机
#   bash scripts/collection_and_push/check_status.sh --remote  # 检查远程（SSH+HTTP）
#   bash scripts/collection_and_push/check_status.sh --all     # 全部
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

CHECK_LOCAL=1
CHECK_REMOTE=0

for arg in "$@"; do
  case "$arg" in
    --remote)
      CHECK_LOCAL=0
      CHECK_REMOTE=1
      ;;
    --all)
      CHECK_LOCAL=1
      CHECK_REMOTE=1
      ;;
    -h|--help)
      echo "用法: $0 [--remote|--all]"
      echo "  默认:    检查本机进程状态"
      echo "  --remote 检查远程服务器（SSH 进程 + HTTP 健康检查）"
      echo "  --all    全部检查"
      exit 0
      ;;
  esac
done

# ---------------------------------------------------------------------------
# 本机进程检查
# ---------------------------------------------------------------------------
if [[ "$CHECK_LOCAL" -eq 1 ]]; then
  echo "============================================================"
  echo "  本机进程状态"
  echo "============================================================"

  PATTERNS=(
    "csv_pipeline.py:采集控制器"
    "collect_tushare_to_csv.py:采集子进程"
    "push_csv_to_cloud.py:推送进程"
    "cleanup_csv.py:清理进程"
    "receive_push_data.py:接收服务"
  )

  for entry in "${PATTERNS[@]}"; do
    pattern="${entry%%:*}"
    label="${entry##*:}"
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      for pid in $pids; do
        cmdline=$(ps -p "$pid" -o args= 2>/dev/null || true)
        if [[ "$cmdline" == *"grep"* ]] || [[ "$cmdline" == *"check_status"* ]]; then
          continue
        fi
        uptime=$(ps -p "$pid" -o etime= 2>/dev/null || echo "unknown")
        echo -e "  ${GREEN}●${NC} $label ($pattern) PID=$pid uptime=$uptime"
      done
    else
      echo -e "  ${RED}○${NC} $label ($pattern) — 未运行"
    fi
  done

  # 检查本机接收服务
  if curl -sS --connect-timeout 2 "http://127.0.0.1:9100/health" 2>/dev/null | grep -q '"ok"'; then
    echo ""
    echo -e "  ${GREEN}●${NC} 本机接收服务 http://127.0.0.1:9100 — 健康"
  fi
  echo ""
fi

# ---------------------------------------------------------------------------
# 远程服务器检查（SSH 进程 + HTTP 健康）
# ---------------------------------------------------------------------------
if [[ "$CHECK_REMOTE" -eq 1 ]]; then
  source "$SCRIPT_DIR/common.sh"
  ensure_prerequisites || exit 1
  probe_all_servers || exit 1

  echo "============================================================"
  echo "  远程服务器状态"
  echo "============================================================"

  REMOTE_PATTERNS=(
    "csv_pipeline.py:采集控制器"
    "collect_tushare_to_csv.py:采集子进程"
    "push_csv_to_cloud.py:推送进程"
    "cleanup_csv.py:清理进程"
    "receive_push_data.py:接收服务"
  )

  for name in "${ALL_SERVER_NAMES[@]}"; do
    local_user_host="${SERVER_USER_HOST[$name]}"
    local_role="${SERVER_ROLE[$name]}"

    echo ""
    echo -e "  ${CYAN}${BOLD}--- $name ($local_user_host) [${local_role}] ---${NC}"

    if [[ "${SERVER_REACHABLE[$name]}" != "1" ]]; then
      echo -e "  ${RED}✗ 不可达，跳过${NC}"
      continue
    fi

    # SSH 进程检查
    for entry in "${REMOTE_PATTERNS[@]}"; do
      pattern="${entry%%:*}"
      label="${entry##*:}"

      pids=$(remote_ssh "$name" "pgrep -f '$pattern' 2>/dev/null" 2>/dev/null || true)
      if [[ -n "$pids" ]]; then
        for pid in $pids; do
          uptime=$(remote_ssh "$name" "ps -p $pid -o etime= 2>/dev/null" 2>/dev/null || echo "unknown")
          echo -e "    ${GREEN}●${NC} $label PID=$pid uptime=$uptime"
        done
      else
        echo -e "    ${RED}○${NC} $label — 未运行"
      fi
    done

    # HTTP 健康检查（仅 receiver 角色）
    if [[ "$local_role" == "receiver" ]]; then
      # 从 user@host 中提取 host
      local_host="${local_user_host#*@}"
      local_health_url="http://${local_host}:9100/health"

      if curl -sS --connect-timeout 3 "$local_health_url" 2>/dev/null | grep -q '"ok"'; then
        echo -e "    ${GREEN}●${NC} HTTP 健康检查: OK ($local_health_url)"
        # 获取统计信息
        stats=$(curl -sS --connect-timeout 3 "http://${local_host}:9100/stats" 2>/dev/null || echo "{}")
        latest_counts=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('latest_counts',{}))" 2>/dev/null || echo "N/A")
        last_flush=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('last_flush_at','N/A'))" 2>/dev/null || echo "N/A")
        echo "      快照记录数: $latest_counts"
        echo "      最近刷盘: $last_flush"
      else
        echo -e "    ${RED}●${NC} HTTP 健康检查: 失败 ($local_health_url)"
      fi
    fi
  done

  echo ""
fi

echo "============================================================"
