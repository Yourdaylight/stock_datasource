#!/usr/bin/env bash
# =============================================================================
# stop_all.sh — 停止 CSV 流水线进程
# 位置: scripts/collection_and_push/stop_all.sh
#
# 用法:
#   bash scripts/collection_and_push/stop_all.sh              # 停止本机
#   bash scripts/collection_and_push/stop_all.sh --remote     # 停止所有远程服务器
#   bash scripts/collection_and_push/stop_all.sh --all        # 停止本机 + 远程
#   bash scripts/collection_and_push/stop_all.sh node2 node3  # 停止指定远程服务器
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 要匹配的进程关键词
PATTERNS=(
  "csv_pipeline.py"
  "collect_tushare_to_csv.py"
  "push_csv_to_cloud.py"
  "cleanup_csv.py"
  "receive_push_data.py"
  "rt-receiver"
)

# ---------------------------------------------------------------------------
# 颜色（独立定义，不依赖 common.sh，本地模式也能用）
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# 停止本机进程
# ---------------------------------------------------------------------------
stop_local() {
  echo "============================================================"
  echo "  停止本机所有 CSV 流水线进程"
  echo "============================================================"

  local killed=0
  for pattern in "${PATTERNS[@]}"; do
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      for pid in $pids; do
        local cmdline
        cmdline=$(ps -p "$pid" -o args= 2>/dev/null || true)
        if [[ "$cmdline" == *"grep"* ]] || [[ "$cmdline" == *"stop_all"* ]]; then
          continue
        fi
        echo -e "${YELLOW}[STOP]${NC} 停止 $pattern (PID=$pid)"
        kill "$pid" 2>/dev/null || true
        ((killed++)) || true
      done
    fi
  done

  if [[ "$killed" -eq 0 ]]; then
    echo -e "${GREEN}[INFO]${NC} 没有发现运行中的流水线进程"
  else
    echo ""
    echo "[INFO] 等待进程退出..."
    sleep 2

    # 检查残留并强杀
    for pattern in "${PATTERNS[@]}"; do
      local pids
      pids=$(pgrep -f "$pattern" 2>/dev/null || true)
      if [[ -n "$pids" ]]; then
        for pid in $pids; do
          local cmdline
          cmdline=$(ps -p "$pid" -o args= 2>/dev/null || true)
          if [[ "$cmdline" == *"grep"* ]] || [[ "$cmdline" == *"stop_all"* ]]; then
            continue
          fi
          echo -e "${RED}[KILL]${NC} 强制杀死 $pattern (PID=$pid)"
          kill -9 "$pid" 2>/dev/null || true
        done
      fi
    done

    echo ""
    echo -e "${GREEN}[OK]${NC} 已停止 $killed 个进程"
  fi
  echo "============================================================"
}

# ---------------------------------------------------------------------------
# 远程停止（通过 sshpass SSH 远程执行 stop_all.sh）
# ---------------------------------------------------------------------------
stop_remote() {
  local targets=("$@")

  # 加载公共函数
  source "$SCRIPT_DIR/common.sh"
  ensure_prerequisites || return 1

  if [[ ${#targets[@]} -eq 0 ]]; then
    targets=("${ALL_SERVER_NAMES[@]}")
  fi

  probe_all_servers "${targets[@]}" || return 1

  for name in "${targets[@]}"; do
    if [[ "${SERVER_REACHABLE[$name]}" != "1" ]]; then
      echo -e "${YELLOW}[WARN]${NC}  [$name] 不可达，跳过"
      continue
    fi

    local base="${SERVER_REMOTE_BASE[$name]}"
    local remote_script="$base/scripts/collection_and_push/stop_all.sh"

    echo ""
    echo -e "${CYAN}${BOLD}==> 停止 $name (${SERVER_USER_HOST[$name]})${NC}"

    # 先检查远程 stop_all.sh 是否存在，不存在则用 pkill 兜底
    if remote_ssh "$name" "test -f '$remote_script'" 2>/dev/null; then
      remote_ssh "$name" "cd '$base' && bash '$remote_script'" 2>&1 | sed "s/^/  [$name] /"
    else
      echo "  [$name] 远程 stop_all.sh 不存在，使用 pkill 兜底"
      for pattern in "${PATTERNS[@]}"; do
        remote_ssh "$name" "pkill -f '$pattern' 2>/dev/null || true" 2>/dev/null
      done
      sleep 1
      for pattern in "${PATTERNS[@]}"; do
        remote_ssh "$name" "pkill -9 -f '$pattern' 2>/dev/null || true" 2>/dev/null
      done
      echo -e "  [$name] ${GREEN}[OK]${NC} 已发送停止信号"
    fi
  done
}

# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
main() {
  local mode="local"
  local remote_targets=()

  for arg in "$@"; do
    case "$arg" in
      -h|--help)
        cat <<'EOF'
用法:
  stop_all.sh                     # 停止本机进程
  stop_all.sh --remote            # 停止所有远程服务器
  stop_all.sh --all               # 停止本机 + 所有远程
  stop_all.sh node2 node3         # 停止指定远程服务器
  stop_all.sh proxy               # 停止远程代理服务器
EOF
        exit 0
        ;;
      --remote)
        mode="remote"
        ;;
      --all)
        mode="all"
        ;;
      proxy|node1|node2|node3)
        mode="remote"
        remote_targets+=("$arg")
        ;;
    esac
  done

  case "$mode" in
    local)
      stop_local
      ;;
    remote)
      stop_remote "${remote_targets[@]}"
      ;;
    all)
      stop_local
      echo ""
      stop_remote "${remote_targets[@]}"
      ;;
  esac
}

main "$@"
