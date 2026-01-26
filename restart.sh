#!/bin/bash

# Restart backend and frontend servers (safe for remote SSH port-forwarding)

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$LOG_DIR/pids"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

mkdir -p "$LOG_DIR" "$PID_DIR"

ACTION="${1:-restart}"

pid_exists() {
  local pid="$1"
  [[ -n "$pid" ]] && [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

pid_cmdline() {
  local pid="$1"
  if [[ -r "/proc/$pid/cmdline" ]]; then
    tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
  else
    ps -p "$pid" -o args= 2>/dev/null || true
  fi
}

pid_cwd() {
  local pid="$1"
  readlink -f "/proc/$pid/cwd" 2>/dev/null || true
}

# 尝试优雅停止进程：先 TERM，超时再 KILL
stop_pid() {
  local pid="$1"
  local label="$2"

  if ! pid_exists "$pid"; then
    return 0
  fi

  echo -e "  ${YELLOW}停止 ${label} (PID: $pid)${NC}"
  kill "$pid" 2>/dev/null || true

  for _ in {1..10}; do
    sleep 0.5
    if ! pid_exists "$pid"; then
      return 0
    fi
  done

  echo -e "  ${YELLOW}  ↳ 进程未退出，强制停止 ${label} (PID: $pid)${NC}"
  kill -9 "$pid" 2>/dev/null || true
}

# 仅当 pid 确认是“本项目服务进程”时才停止，避免误杀 ssh 端口转发
stop_pid_if_matches() {
  local pid="$1"
  local label="$2"
  local expected_substr="$3"
  local expected_cwd_prefix="$4"

  if ! pid_exists "$pid"; then
    return 1
  fi

  local cmd cwd
  cmd="$(pid_cmdline "$pid")"
  cwd="$(pid_cwd "$pid")"

  if [[ -n "$expected_substr" ]] && [[ "$cmd" == *"$expected_substr"* ]]; then
    stop_pid "$pid" "$label"
    return 0
  fi

  if [[ -n "$expected_cwd_prefix" ]] && [[ -n "$cwd" ]] && [[ "$cwd" == "$expected_cwd_prefix"* ]]; then
    # CWD 在项目目录下，再做一层命令过滤，避免把任意进程都停掉
    if [[ "$cmd" == *"python"*"stock_datasource"* ]] || [[ "$cmd" == *"uv "*"stock_datasource"* ]] || [[ "$cmd" == *"vite"* ]] || [[ "$cmd" == *"npm"*"dev"* ]]; then
      stop_pid "$pid" "$label"
      return 0
    fi
  fi

  return 1
}

# 通过 pidfile 停止（更可靠）
stop_by_pidfile() {
  local pidfile="$1"
  local label="$2"
  local expected_substr="$3"
  local expected_cwd_prefix="$4"

  if [[ ! -f "$pidfile" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"

  if [[ -z "$pid" ]]; then
    rm -f "$pidfile" || true
    return 0
  fi

  if stop_pid_if_matches "$pid" "$label" "$expected_substr" "$expected_cwd_prefix"; then
    rm -f "$pidfile" || true
    return 0
  fi

  # pidfile 可能过期或被复用，清掉避免后续误判
  if ! pid_exists "$pid"; then
    rm -f "$pidfile" || true
  fi
}

# 通过端口兜底停止：只停“看起来属于本项目”的进程，绝不按端口盲杀
stop_by_port_safely() {
  local port="$1"
  local label="$2"
  local expected_substr="$3"
  local expected_cwd_prefix="$4"

  local pids
  pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    return 0
  fi

  local any_stopped=false
  for pid in $pids; do
    if stop_pid_if_matches "$pid" "$label" "$expected_substr" "$expected_cwd_prefix"; then
      any_stopped=true
    else
      local cmd
      cmd="$(pid_cmdline "$pid")"
      echo -e "  ${YELLOW}端口 $port 被占用 (PID: $pid)${NC}"
      echo -e "    ${YELLOW}未自动停止（避免影响 SSH/其它服务）：${NC}$cmd"
    fi
  done

  if [[ "$any_stopped" == true ]]; then
    sleep 1
  fi
}

stop_legacy_workers() {
  local pids
  pids=$(pgrep -f "stock_datasource.services.task_worker" 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    return 0
  fi

  local any_stopped=false
  for pid in $pids; do
    if ! pid_exists "$pid"; then
      continue
    fi

    local cmd cwd
    cmd="$(pid_cmdline "$pid")"
    cwd="$(pid_cwd "$pid")"

    if [[ -n "$cwd" ]] && [[ "$cwd" == "$SCRIPT_DIR"* ]]; then
      continue
    fi

    if [[ "$cmd" == *"python"* ]] || [[ "$cmd" == *"uv "* ]]; then
      stop_pid "$pid" "旧 Worker"
      any_stopped=true
    fi
  done

  if [[ "$any_stopped" == true ]]; then
    sleep 1
  fi
}

print_header() {
  echo "=========================================="
  echo "  重启服务"
  echo "=========================================="
  echo ""
}

stop_services() {
  echo -e "${YELLOW}[1/4]${NC} 停止现有进程..."

  # 先按 pidfile 停（最安全）
  stop_by_pidfile "$BACKEND_PID_FILE" "后端服务" "stock_datasource.services.http_server" "$SCRIPT_DIR"
  stop_by_pidfile "$FRONTEND_PID_FILE" "前端服务" "vite" "$SCRIPT_DIR/frontend"

  stop_legacy_workers

  # 再按端口兜底（带白名单校验，避免误杀 ssh 端口转发）
  stop_by_port_safely 8000 "后端服务" "stock_datasource.services.http_server" "$SCRIPT_DIR"

  for port in 3000 3001 3002 3003 3004 3005 5173; do
    stop_by_port_safely "$port" "前端服务" "vite" "$SCRIPT_DIR/frontend"
  done

  echo ""
}

prepare_env() {
  echo -e "${YELLOW}[2/4]${NC} 准备环境..."
  echo -e "  ${GREEN}✓ 日志目录已准备${NC}"
  echo ""
}

start_backend() {
  echo -e "${YELLOW}[3/4]${NC} 启动后端服务..."
  cd "$SCRIPT_DIR"

  # 后台启动后端
  nohup uv run python -m stock_datasource.services.http_server > "$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
  echo "  后端PID: $BACKEND_PID"

  # 等待后端启动并验证（考虑初始化耗时较长）
  MAX_BACKEND_WAIT=150
  for i in $(seq 1 "$MAX_BACKEND_WAIT"); do
    sleep 1
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
      echo -e "  ${GREEN}✓ 后端已启动 (http://0.0.0.0:8000)${NC}"
      echo ""
      return 0
    fi
    if [[ "$i" -eq "$MAX_BACKEND_WAIT" ]]; then
      echo -e "  ${RED}✗ 后端启动超时（已等待 ${MAX_BACKEND_WAIT}s）${NC}"
      echo "  查看日志: tail -f $LOG_DIR/backend.log"
      exit 1
    fi
  done
}

start_frontend() {
  echo -e "${YELLOW}[4/4]${NC} 启动前端服务..."
  cd "$SCRIPT_DIR/frontend"

  nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"
  echo "  前端PID: $FRONTEND_PID"

  # 等待前端启动并获取实际端口
  FRONTEND_PORT=""
  for i in {1..25}; do
    sleep 1
    for port in 3000 3001 3002 3003 3004 3005 5173; do
      if lsof -t -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then
        # 进一步确认是我们这个 frontend 目录下启动的（避免识别到 SSH 端口转发）
        local_pid=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)
        if [[ -n "$local_pid" ]]; then
          cwd="$(pid_cwd "$local_pid")"
          cmd="$(pid_cmdline "$local_pid")"
          if [[ "$cwd" == "$SCRIPT_DIR/frontend"* ]] && [[ "$cmd" == *"vite"* ]]; then
            FRONTEND_PORT=$port
            break 2
          fi
        fi
      fi
    done
    if [[ "$i" -eq 25 ]]; then
      echo -e "  ${YELLOW}⚠ 前端启动较慢，请稍后检查${NC}"
    fi
  done

  if [[ -n "$FRONTEND_PORT" ]]; then
    echo -e "  ${GREEN}✓ 前端已启动 (http://0.0.0.0:$FRONTEND_PORT)${NC}"
  fi
  echo ""

  # 完成
  echo "=========================================="
  echo -e "${GREEN}  ✓ 所有服务已成功重启！${NC}"
  echo "=========================================="
  echo ""
  echo -e "${BLUE}后端 API:${NC} http://0.0.0.0:8000"
  echo -e "${BLUE}前端界面:${NC} http://0.0.0.0:${FRONTEND_PORT:-5173}"
  echo ""
  echo -e "${BLUE}查看日志:${NC}"
  echo "  后端: tail -f $LOG_DIR/backend.log"
  echo "  前端: tail -f $LOG_DIR/frontend.log"
  echo ""
  echo -e "${BLUE}停止服务:${NC}"
  echo "  停止全部: $SCRIPT_DIR/restart.sh stop"
  echo ""
}

print_header

case "$ACTION" in
  stop)
    stop_services
    echo -e "${GREEN}✓ 已停止（仅停止本项目相关进程，避免影响 SSH）${NC}"
    ;;
  start)
    prepare_env
    start_backend
    start_frontend
    ;;
  restart|*)
    stop_services
    prepare_env
    start_backend
    start_frontend
    ;;
esac
