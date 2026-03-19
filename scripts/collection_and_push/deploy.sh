#!/usr/bin/env bash
# =============================================================================
# deploy.sh — 将 collection_and_push 部署到远程服务器
# 位置: scripts/collection_and_push/deploy.sh
#
# 用法:
#   bash scripts/collection_and_push/deploy.sh [all|proxy|node1|node2|node3]
#
# 功能:
#   1. 通过 sshpass+scp 将脚本同步到目标服务器
#   2. 同步 .env + servers.conf 到目标
#   3. 在目标服务器上安装 Python 依赖
#   4. 不可达节点自动跳过，不中断流程
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载公共函数库
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# Python 依赖列表
# ---------------------------------------------------------------------------
PIP_DEPS_PROXY="pandas tushare requests flask PyJWT numpy"
PIP_DEPS_RECEIVER="flask PyJWT requests"

# ---------------------------------------------------------------------------
# 部署单台服务器
# ---------------------------------------------------------------------------
deploy_one() {
  local name="$1"
  local user_host="${SERVER_USER_HOST[$name]}"
  local base="${SERVER_REMOTE_BASE[$name]}"
  local role="${SERVER_ROLE[$name]}"
  local remote_dir="$base/scripts/collection_and_push"

  # 跳过不可达
  if [[ "${SERVER_REACHABLE[$name]}" != "1" ]]; then
    warn "[$name] 不可达，跳过部署"
    return 0
  fi

  step "部署到 $name ($user_host) [${role}]"

  # 1) 创建远程目录结构
  info "[$name] 创建远程目录..."
  remote_ssh "$name" "mkdir -p '$remote_dir' '$base/data/tushare_csv' '$base/data/received_push' '$base/logs'" || {
    err "[$name] 创建目录失败"
    return 1
  }

  # 2) 清理远程旧脚本（scp 没有 --delete，手动清理保证一致性）
  info "[$name] 清理远程旧脚本..."
  remote_ssh "$name" "rm -f '$remote_dir'/*.py '$remote_dir'/*.sh '$remote_dir'/servers.conf" 2>/dev/null || true

  # 3) 上传脚本文件
  info "[$name] 上传脚本文件..."
  remote_scp_dir "$name" "$SCRIPT_DIR" "$remote_dir" || {
    err "[$name] 文件上传失败"
    return 1
  }

  # 4) 单独上传 servers.conf（如果存在）
  if [[ -f "$SCRIPT_DIR/servers.conf" ]]; then
    remote_scp "$name" "$SCRIPT_DIR/servers.conf" "$remote_dir/servers.conf" || true
  fi

  # 5) 设置执行权限
  remote_ssh "$name" "chmod +x '$remote_dir'/*.sh" 2>/dev/null || true

  # 6) 安装 Python 依赖
  info "[$name] 安装 Python 依赖..."
  local pip_deps
  if [[ "$role" == "proxy" ]]; then
    pip_deps="$PIP_DEPS_PROXY"
  else
    pip_deps="$PIP_DEPS_RECEIVER"
  fi

  # 尝试多种方式安装 pip 依赖
  if ! remote_ssh "$name" "python3 -m pip install --quiet $pip_deps 2>/dev/null" 2>/dev/null; then
    warn "[$name] pip3 安装失败，尝试安装 pip..."
    remote_ssh "$name" "curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py --quiet 2>/dev/null && python3 -m pip install --quiet $pip_deps" 2>/dev/null || {
      err "[$name] Python 依赖安装失败！请手动处理"
      return 1
    }
  fi

  # 7) 验证部署
  info "[$name] 验证文件..."
  local file_count
  file_count=$(remote_ssh "$name" "ls -1 '$remote_dir'/*.py 2>/dev/null | wc -l") || file_count=0
  if [[ "$file_count" -gt 0 ]]; then
    ok "[$name] 部署成功！${file_count} 个 Python 脚本已同步"
  else
    err "[$name] 部署可能失败，未发现 .py 文件"
    return 1
  fi

  echo ""
}

# ---------------------------------------------------------------------------
# 使用说明
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
用法:
  bash scripts/collection_and_push/deploy.sh [targets...]

目标 (可多选):
  all     部署到所有可达服务器（默认）
  proxy   仅部署到代理服务器
  node1   仅部署到订阅节点1
  node2   仅部署到订阅节点2
  node3   仅部署到订阅节点3
  check   仅执行 SSH 连通性检查

示例:
  bash scripts/collection_and_push/deploy.sh             # 部署到所有
  bash scripts/collection_and_push/deploy.sh proxy       # 仅部署代理
  bash scripts/collection_and_push/deploy.sh node2 node3 # 部署到节点2和3
  bash scripts/collection_and_push/deploy.sh check       # 仅检查连通性
EOF
}

# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
main() {
  local args=("$@")

  # 帮助
  for arg in "${args[@]}"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
      usage
      exit 0
    fi
  done

  # 前置检查
  ensure_prerequisites || exit 1

  # 仅检查模式
  for arg in "${args[@]}"; do
    if [[ "$arg" == "check" ]]; then
      probe_all_servers
      exit $?
    fi
  done

  # 解析目标
  local targets
  read -ra targets <<< "$(parse_targets "${args[@]}")"

  # 探测连通性
  probe_all_servers "${targets[@]}" || exit 1

  # 逐台部署
  local success=0
  local fail=0
  local skip=0
  for name in "${targets[@]}"; do
    if [[ "${SERVER_REACHABLE[$name]}" != "1" ]]; then
      ((skip++)) || true
      continue
    fi
    if deploy_one "$name"; then
      ((success++)) || true
    else
      ((fail++)) || true
    fi
  done

  # 汇总
  echo ""
  step "部署汇总"
  ok "成功: $success  失败: $fail  跳过: $skip"
  if [[ $fail -gt 0 ]]; then
    err "有 $fail 台服务器部署失败，请检查日志"
    exit 1
  fi
}

main "$@"
