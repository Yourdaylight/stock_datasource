#!/usr/bin/env bash
# =============================================================================
# run.sh — 一键全流程运维入口
# 位置: scripts/collection_and_push/run.sh
#
# 用法:
#   bash scripts/collection_and_push/run.sh deploy          # 部署到所有可达服务器
#   bash scripts/collection_and_push/run.sh start            # 启动全部（先 receiver 后 proxy）
#   bash scripts/collection_and_push/run.sh stop             # 停止全部远程进程
#   bash scripts/collection_and_push/run.sh restart          # 停止 → 启动
#   bash scripts/collection_and_push/run.sh status           # 检查所有远程状态
#   bash scripts/collection_and_push/run.sh verify           # 验证数据流
#   bash scripts/collection_and_push/run.sh full             # 部署 → 启动 → 验证（完整流程）
#   bash scripts/collection_and_push/run.sh deploy+start     # 部署 → 启动
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载公共函数库
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# 子命令: deploy
# ---------------------------------------------------------------------------
cmd_deploy() {
  step "======== 部署 ========"
  bash "$SCRIPT_DIR/deploy.sh" "${@:-all}"
}

# ---------------------------------------------------------------------------
# 子命令: start — 先启动 receiver 节点，再启动 proxy
# ---------------------------------------------------------------------------
cmd_start() {
  step "======== 启动服务 ========"

  ensure_prerequisites || return 1
  probe_all_servers || return 1

  # 1) 启动所有可达的 receiver 节点
  local receivers
  read -ra receivers <<< "$(get_reachable_servers receiver)"

  if [[ ${#receivers[@]} -eq 0 ]]; then
    err "没有可达的 receiver 节点！"
    return 1
  fi

  for name in "${receivers[@]}"; do
    local base="${SERVER_REMOTE_BASE[$name]}"
    local remote_script="$base/scripts/collection_and_push/start_receiver.sh"

    step "启动 receiver: $name (${SERVER_USER_HOST[$name]})"

    # 先停止旧进程
    remote_ssh "$name" "pkill -f receive_push_data.py 2>/dev/null || true" 2>/dev/null || true
    sleep 1

    # 启动
    if remote_ssh "$name" "test -f '$remote_script'" 2>/dev/null; then
      remote_ssh "$name" "cd '$base' && bash '$remote_script'" 2>&1 | sed "s/^/  [$name] /" || {
        err "[$name] receiver 启动失败"
        continue
      }
    else
      # 脚本不存在，直接启动 python
      warn "[$name] start_receiver.sh 不存在，直接启动 python..."
      remote_ssh "$name" "cd '$base' && mkdir -p logs data/received_push && nohup python3 scripts/collection_and_push/receive_push_data.py --port 9100 --push-token '${RT_KLINE_CLOUD_PUSH_TOKEN:-csv_pipeline_push_token_2026}' --flush-interval-seconds 5 --data-dir data/received_push > logs/receiver.log 2>&1 &" 2>&1 || true
    fi

    # 等待启动 + 健康检查
    sleep 3
    local host="${SERVER_USER_HOST[$name]#*@}"
    if curl -sS --connect-timeout 5 "http://${host}:9100/health" 2>/dev/null | grep -q '"ok"'; then
      ok "[$name] 健康检查通过 ✓"
    else
      warn "[$name] 健康检查暂未通过（可能需要更多时间启动）"
    fi
    echo ""
  done

  # 2) 启动 proxy
  local proxies
  read -ra proxies <<< "$(get_reachable_servers proxy)"

  if [[ ${#proxies[@]} -eq 0 ]]; then
    err "没有可达的 proxy 服务器！"
    return 1
  fi

  for name in "${proxies[@]}"; do
    local base="${SERVER_REMOTE_BASE[$name]}"
    local remote_script="$base/scripts/collection_and_push/start_proxy.sh"

    step "启动 proxy: $name (${SERVER_USER_HOST[$name]})"

    # 先停止旧进程
    remote_ssh "$name" "pkill -f csv_pipeline.py 2>/dev/null; pkill -f push_csv_to_cloud.py 2>/dev/null; pkill -f collect_tushare_to_csv.py 2>/dev/null; true" 2>/dev/null || true
    sleep 1

    # 启动
    if remote_ssh "$name" "test -f '$remote_script'" 2>/dev/null; then
      remote_ssh "$name" "cd '$base' && bash '$remote_script'" 2>&1 | sed "s/^/  [$name] /" || {
        err "[$name] proxy 启动失败"
        continue
      }
    else
      err "[$name] start_proxy.sh 不存在！请先运行 deploy"
      continue
    fi

    ok "[$name] proxy 启动完成"
    echo ""
  done

  ok "======== 所有服务已启动 ========"
}

# ---------------------------------------------------------------------------
# 子命令: stop
# ---------------------------------------------------------------------------
cmd_stop() {
  step "======== 停止服务 ========"
  bash "$SCRIPT_DIR/stop_all.sh" --remote
}

# ---------------------------------------------------------------------------
# 子命令: restart
# ---------------------------------------------------------------------------
cmd_restart() {
  cmd_stop
  echo ""
  sleep 2
  cmd_start
}

# ---------------------------------------------------------------------------
# 子命令: status
# ---------------------------------------------------------------------------
cmd_status() {
  step "======== 检查状态 ========"
  bash "$SCRIPT_DIR/check_status.sh" --remote
}

# ---------------------------------------------------------------------------
# 子命令: verify — 对所有可达的 receiver 执行验证
# ---------------------------------------------------------------------------
cmd_verify() {
  step "======== 验证数据流 ========"

  ensure_prerequisites || return 1

  # 加载 .env 获取 token
  local env_file="$SCRIPT_DIR/.env"
  if [[ -f "$env_file" ]]; then
    set -a
    source "$env_file"
    set +a
  fi

  local push_token="${RT_KLINE_CLOUD_PUSH_TOKEN:-csv_pipeline_push_token_2026}"

  # 探测 receiver 节点
  probe_all_servers || return 1

  local receivers
  read -ra receivers <<< "$(get_reachable_servers receiver)"

  for name in "${receivers[@]}"; do
    local host="${SERVER_USER_HOST[$name]#*@}"
    local base_url="http://${host}:9100"

    echo ""
    step "验证 $name ($base_url)"

    # 健康检查
    local health
    health=$(curl -sS --connect-timeout 5 "$base_url/health" 2>/dev/null || echo "FAILED")
    if echo "$health" | grep -q '"ok"'; then
      ok "健康检查: $health"
    else
      err "健康检查失败: $health"
      continue
    fi

    # 统计
    local stats
    stats=$(curl -sS --connect-timeout 5 "$base_url/stats" 2>/dev/null || echo "{}")
    info "统计: $stats"

    # 推送测试数据
    info "推送测试数据..."
    local push_result
    push_result=$(curl -sS --connect-timeout 5 \
      -X POST "$base_url/api/v1/rt-kline/push" \
      -H "Authorization: Bearer $push_token" \
      -H "Content-Type: application/json" \
      -d '{"schema_version":"v2","mode":"raw_tick_batch","batch_seq":999999,"event_time":"2026-03-17T10:00:00Z","market":"a_stock","source_api":"run_sh_verify","count":1,"first_stream_id":"999999-0","last_stream_id":"999999-0","items":[{"stream_id":"999999-0","ts_code":"000001.SZ","version":"1","shard_id":0,"tick":{"ts_code":"000001.SZ","market":"a_stock","close":10.52,"trade_date":"20260317"}}]}' 2>/dev/null || echo "FAILED")
    if echo "$push_result" | grep -qi "ok\|accept\|success\|ack"; then
      ok "推送测试: $push_result"
    else
      warn "推送测试响应: $push_result"
    fi

    # 查询快照
    sleep 1
    local latest
    latest=$(curl -sS --connect-timeout 5 "$base_url/api/v1/rt-kline/latest?ts_code=000001.SZ" 2>/dev/null || echo "FAILED")
    info "快照查询(000001.SZ): $latest"

    echo ""
  done

  ok "======== 验证完成 ========"
}

# ---------------------------------------------------------------------------
# 子命令: full — 完整流程: 部署 → 启动 → 验证
# ---------------------------------------------------------------------------
cmd_full() {
  step "======== 开始完整流程: 部署 → 启动 → 验证 ========"
  echo ""

  cmd_deploy
  echo ""
  sleep 2

  cmd_start
  echo ""
  sleep 3

  cmd_verify
  echo ""

  ok "======== 完整流程执行完毕 ========"
}

# ---------------------------------------------------------------------------
# 使用说明
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
用法:
  bash scripts/collection_and_push/run.sh <command>

命令:
  deploy         部署脚本到所有可达服务器
  start          启动全部服务（先 receiver 后 proxy）
  stop           停止所有远程服务器上的进程
  restart        停止 → 等待 → 启动
  status         检查所有远程服务器状态（SSH 进程 + HTTP 健康检查）
  verify         对所有可达 receiver 推送测试数据并验证
  full           完整流程: 部署 → 启动 → 验证
  deploy+start   部署 → 启动

示例:
  bash scripts/collection_and_push/run.sh full      # 一键搞定全流程
  bash scripts/collection_and_push/run.sh restart    # 快速重启
  bash scripts/collection_and_push/run.sh status     # 看看各节点状态
EOF
}

# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
main() {
  if [[ $# -eq 0 ]]; then
    usage
    exit 0
  fi

  local cmd="$1"
  shift

  case "$cmd" in
    deploy)
      cmd_deploy "$@"
      ;;
    start)
      cmd_start "$@"
      ;;
    stop)
      cmd_stop "$@"
      ;;
    restart)
      cmd_restart "$@"
      ;;
    status)
      cmd_status "$@"
      ;;
    verify)
      cmd_verify "$@"
      ;;
    full)
      cmd_full "$@"
      ;;
    deploy+start)
      cmd_deploy "$@"
      echo ""
      sleep 2
      cmd_start "$@"
      ;;
    -h|--help)
      usage
      ;;
    *)
      err "未知命令: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "$@"
