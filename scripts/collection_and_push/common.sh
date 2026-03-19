#!/usr/bin/env bash
# =============================================================================
# common.sh — 公共函数库（所有运维脚本 source 此文件）
# 位置: scripts/collection_and_push/common.sh
#
# 提供:
#   1) 颜色输出: info / ok / warn / err
#   2) 服务器配置加载: load_servers / get_server_*
#   3) sshpass 封装: remote_ssh / remote_scp / remote_scp_dir
#   4) 连通性探测: probe_server / probe_all_servers
# =============================================================================

# 防止重复 source
[[ -n "${_COMMON_SH_LOADED:-}" ]] && return 0
_COMMON_SH_LOADED=1

COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVERS_CONF="${SERVERS_CONF:-$COMMON_DIR/servers.conf}"

# ---------------------------------------------------------------------------
# 颜色输出
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()  { echo -e "${CYAN}${BOLD}==> $*${NC}"; }

# ---------------------------------------------------------------------------
# 服务器配置加载
# ---------------------------------------------------------------------------
# 数组：所有服务器名称列表（按配置文件顺序）
ALL_SERVER_NAMES=()

# 关联数组：按 name 存储各字段
declare -A SERVER_USER_HOST   # user@host
declare -A SERVER_PASSWORD    # password
declare -A SERVER_REMOTE_BASE # remote base path
declare -A SERVER_ROLE        # proxy / receiver
declare -A SERVER_REACHABLE   # 1=reachable, 0=unreachable, ""=unknown

load_servers() {
  if [[ ! -f "$SERVERS_CONF" ]]; then
    err "服务器配置文件不存在: $SERVERS_CONF"
    err "请从 servers.conf.example 复制并填写密码"
    return 1
  fi

  ALL_SERVER_NAMES=()
  while IFS='|' read -r name user_host password remote_base role; do
    # 跳过注释和空行
    [[ -z "$name" || "$name" == \#* ]] && continue
    # 去除首尾空白
    name="$(echo "$name" | xargs)"
    user_host="$(echo "$user_host" | xargs)"
    password="$(echo "$password" | xargs)"
    remote_base="$(echo "$remote_base" | xargs)"
    role="$(echo "$role" | xargs)"

    ALL_SERVER_NAMES+=("$name")
    SERVER_USER_HOST["$name"]="$user_host"
    SERVER_PASSWORD["$name"]="$password"
    SERVER_REMOTE_BASE["$name"]="$remote_base"
    SERVER_ROLE["$name"]="$role"
    SERVER_REACHABLE["$name"]=""
  done < "$SERVERS_CONF"

  if [[ ${#ALL_SERVER_NAMES[@]} -eq 0 ]]; then
    err "servers.conf 中没有找到有效的服务器配置"
    return 1
  fi
}

# 获取指定角色的服务器列表
get_servers_by_role() {
  local target_role="$1"
  local result=()
  for name in "${ALL_SERVER_NAMES[@]}"; do
    if [[ "${SERVER_ROLE[$name]}" == "$target_role" ]]; then
      result+=("$name")
    fi
  done
  echo "${result[@]}"
}

# 获取所有可达服务器
get_reachable_servers() {
  local role="${1:-}"  # 可选角色过滤
  local result=()
  for name in "${ALL_SERVER_NAMES[@]}"; do
    if [[ "${SERVER_REACHABLE[$name]}" == "1" ]]; then
      if [[ -z "$role" || "${SERVER_ROLE[$name]}" == "$role" ]]; then
        result+=("$name")
      fi
    fi
  done
  echo "${result[@]}"
}

# ---------------------------------------------------------------------------
# sshpass 封装
# ---------------------------------------------------------------------------
SSH_TIMEOUT="${SSH_TIMEOUT:-15}"
SSH_OPTS="-o ConnectTimeout=${SSH_TIMEOUT} -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no"

# remote_ssh NAME "command..."
remote_ssh() {
  local name="$1"; shift
  local user_host="${SERVER_USER_HOST[$name]}"
  local password="${SERVER_PASSWORD[$name]}"
  sshpass -p "$password" ssh $SSH_OPTS "$user_host" "$@"
}

# remote_scp NAME local_file remote_path
remote_scp() {
  local name="$1"
  local local_file="$2"
  local remote_path="$3"
  local user_host="${SERVER_USER_HOST[$name]}"
  local password="${SERVER_PASSWORD[$name]}"
  sshpass -p "$password" scp $SSH_OPTS "$local_file" "${user_host}:${remote_path}"
}

# remote_scp_dir NAME local_dir remote_dir
# 上传整个目录的内容（非递归，只传文件）
remote_scp_dir() {
  local name="$1"
  local local_dir="$2"
  local remote_dir="$3"
  local user_host="${SERVER_USER_HOST[$name]}"
  local password="${SERVER_PASSWORD[$name]}"

  # 收集要上传的文件
  local files=()
  for f in "$local_dir"/*.py "$local_dir"/*.sh "$local_dir"/.env; do
    [[ -f "$f" ]] && files+=("$f")
  done

  if [[ ${#files[@]} -eq 0 ]]; then
    warn "[$name] 没有找到需要上传的文件"
    return 1
  fi

  sshpass -p "$password" scp $SSH_OPTS "${files[@]}" "${user_host}:${remote_dir}/"
}

# ---------------------------------------------------------------------------
# 连通性探测
# ---------------------------------------------------------------------------

# probe_server NAME  → 设置 SERVER_REACHABLE[NAME] 并返回 0/1
probe_server() {
  local name="$1"
  local user_host="${SERVER_USER_HOST[$name]}"
  local password="${SERVER_PASSWORD[$name]}"

  if sshpass -p "$password" ssh $SSH_OPTS "$user_host" "echo ok" >/dev/null 2>&1; then
    SERVER_REACHABLE["$name"]=1
    return 0
  else
    SERVER_REACHABLE["$name"]=0
    return 1
  fi
}

# probe_all_servers [name1 name2 ...]
# 不指定参数时探测所有服务器；指定时只探测指定的
probe_all_servers() {
  local targets=("$@")
  if [[ ${#targets[@]} -eq 0 ]]; then
    targets=("${ALL_SERVER_NAMES[@]}")
  fi

  local total=${#targets[@]}
  local reachable=0
  local unreachable=0

  step "探测服务器连通性 (${total} 台)..."
  for name in "${targets[@]}"; do
    local user_host="${SERVER_USER_HOST[$name]}"
    printf "  %-8s %-25s " "$name" "$user_host"
    if probe_server "$name"; then
      echo -e "${GREEN}✓ 可达${NC}"
      ((reachable++))
    else
      echo -e "${RED}✗ 不可达${NC}"
      ((unreachable++))
    fi
  done

  echo ""
  info "可达: ${reachable}/${total}  不可达: ${unreachable}/${total}"

  if [[ $reachable -eq 0 ]]; then
    err "没有任何可达的服务器！"
    return 1
  fi

  if [[ $unreachable -gt 0 ]]; then
    warn "以下服务器不可达，将被跳过:"
    for name in "${targets[@]}"; do
      if [[ "${SERVER_REACHABLE[$name]}" == "0" ]]; then
        warn "  - $name (${SERVER_USER_HOST[$name]})"
      fi
    done
  fi

  echo ""
  return 0
}

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

# 检查 sshpass 是否安装
check_sshpass() {
  if ! command -v sshpass &>/dev/null; then
    err "sshpass 未安装！请先安装: apt-get install -y sshpass"
    return 1
  fi
}

# 确保必要的前置条件
ensure_prerequisites() {
  check_sshpass || return 1
  load_servers || return 1
}

# 过滤目标服务器列表：从参数列表中解析出有效的服务器名称
# 用法: parse_targets "$@"  → 输出过滤后的名称列表
parse_targets() {
  local targets=("$@")
  local result=()

  if [[ ${#targets[@]} -eq 0 ]] || [[ "${targets[0]}" == "all" ]]; then
    result=("${ALL_SERVER_NAMES[@]}")
  else
    for t in "${targets[@]}"; do
      local found=0
      for name in "${ALL_SERVER_NAMES[@]}"; do
        if [[ "$name" == "$t" ]]; then
          result+=("$name")
          found=1
          break
        fi
      done
      if [[ $found -eq 0 ]]; then
        # 也支持按角色过滤
        if [[ "$t" == "proxy" || "$t" == "receiver" ]]; then
          for name in "${ALL_SERVER_NAMES[@]}"; do
            if [[ "${SERVER_ROLE[$name]}" == "$t" ]]; then
              result+=("$name")
            fi
          done
        else
          warn "未知目标: $t (跳过)"
        fi
      fi
    done
  fi

  echo "${result[@]}"
}
