#!/bin/bash
# =============================================================================
# 回滚脚本 — 回滚到上一个部署版本
# 使用 .deploy-backup/ 中的镜像标签记录恢复上一版本
#
# 用法:
#   bash scripts/rollback.sh              # 回滚到上一个版本
#   bash scripts/rollback.sh --list       # 列出可回滚的版本
#   bash scripts/rollback.sh --version <N> # 回滚到第 N 个备份（从新到旧）
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/.deploy-backup"

cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    log_error "Neither docker-compose nor docker compose found!"
    exit 1
fi

# =============================================================================
# 列出可回滚版本
# =============================================================================
list_backups() {
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR"/images_*.txt 2>/dev/null)" ]; then
        log_warn "没有找到备份记录"
        exit 0
    fi

    echo -e "${BLUE}可回滚的部署版本:${NC}"
    echo ""
    local i=1
    for f in $(ls -t "$BACKUP_DIR"/images_*.txt); do
        local ts
        ts=$(basename "$f" | sed 's/images_\(.*\)\.txt/\1/')
        echo -e "  ${GREEN}#${i}${NC}  时间: ${ts}"
        cat "$f" | while read -r line; do
            echo "      $line"
        done
        echo ""
        ((i++)) || true
    done
}

# =============================================================================
# 执行回滚
# =============================================================================
do_rollback() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi

    log_info "回滚到以下镜像版本:"
    cat "$backup_file" | while read -r line; do
        echo "  $line"
    done
    echo ""

    # 读取备份中的镜像信息
    local backend_image=""
    local frontend_image=""

    while read -r line; do
        local svc="${line%%=*}"
        local img="${line#*=}"
        case "$svc" in
            backend) backend_image="$img" ;;
            frontend) frontend_image="$img" ;;
        esac
    done < "$backup_file"

    # 回滚 backend + worker
    if [[ -n "$backend_image" && "$backend_image" != "unknown" ]]; then
        log_info "回滚后端 (backend + worker) 到 ${backend_image}..."
        docker tag "$backend_image" "$backend_image" 2>/dev/null || true
        $COMPOSE_CMD up -d --force-recreate --no-build backend worker
    fi

    # 回滚 frontend
    if [[ -n "$frontend_image" && "$frontend_image" != "unknown" ]]; then
        log_info "回滚前端到 ${frontend_image}..."
        docker tag "$frontend_image" "$frontend_image" 2>/dev/null || true
        $COMPOSE_CMD up -d --force-recreate --no-build frontend
    fi

    # 等待健康检查
    log_info "等待服务启动..."
    echo -n "等待后端健康检查"
    for i in {1..60}; do
        if $COMPOSE_CMD ps backend | grep -q "healthy"; then
            echo ""
            log_info "后端启动成功"
            break
        fi
        echo -n "."
        sleep 2
    done

    if ! $COMPOSE_CMD ps backend | grep -q "healthy"; then
        echo ""
        log_error "回滚后后端启动超时！请手动检查"
        $COMPOSE_CMD logs --tail=20 backend
        exit 1
    fi

    echo ""
    log_info "回滚完成！"
    $COMPOSE_CMD ps backend frontend worker
}

# =============================================================================
# 主逻辑
# =============================================================================
case "${1:-}" in
    --list|-l)
        list_backups
        ;;
    --version|-v)
        if [ -z "${2:-}" ]; then
            log_error "请指定备份编号，如: $0 --version 2"
            list_backups
            exit 1
        fi
        backup_file=$(ls -t "$BACKUP_DIR"/images_*.txt 2>/dev/null | sed -n "${2}p")
        if [ -z "$backup_file" ]; then
            log_error "备份编号 ${2} 不存在"
            list_backups
            exit 1
        fi
        do_rollback "$backup_file"
        ;;
    "")
        # 默认回滚到上一个版本
        backup_file=$(ls -t "$BACKUP_DIR"/images_*.txt 2>/dev/null | head -1)
        if [ -z "$backup_file" ]; then
            log_error "没有找到备份记录，无法回滚"
            exit 1
        fi
        do_rollback "$backup_file"
        ;;
    -h|--help)
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  (无参数)           回滚到上一个部署版本"
        echo "  --list, -l        列出可回滚的版本"
        echo "  --version N, -v N 回滚到第 N 个备份（从新到旧）"
        echo "  -h, --help        显示帮助"
        ;;
    *)
        log_error "未知参数: $1"
        exit 1
        ;;
esac
