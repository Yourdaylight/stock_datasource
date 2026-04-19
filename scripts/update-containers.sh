#!/bin/bash
# =============================================================================
# 容器代码更新脚本
# 适用场景：宿主机已有 langfuse-clickhouse-1 和 Langfuse，只需更新应用容器
# 架构说明：MCP 服务器内嵌于 backend 容器中，无需单独构建 stock-mcp 容器
#
# 用法:
#   $0                           # 快速重启（使用现有镜像）
#   $0 --build                   # 重新构建并更新
#   $0 --version v1.2.3          # 从 DockerHub 拉取指定版本镜像
#   $0 --backend --build         # 只重新构建后端
#   $0 --version v1.2.3 --backend # 拉取指定版本后端镜像
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/.deploy-backup"

cd "$PROJECT_DIR"

# DockerHub 镜像仓库
DOCKERHUB_REPO="zl3n22/stock_datasource"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Determine docker compose command (v1 vs v2)
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    log_error "Neither docker-compose nor docker compose found!"
    exit 1
fi

# =============================================================================
# 备份当前镜像标签（用于回滚）
# =============================================================================
backup_current_images() {
    mkdir -p "$BACKUP_DIR"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/images_${timestamp}.txt"

    for svc in backend frontend worker; do
        local image
        image=$(docker inspect --format='{{.Config.Image}}' "stock-${svc}" 2>/dev/null || echo "unknown")
        echo "${svc}=${image}" >> "$backup_file"
    done

    # 只保留最近 5 个备份
    ls -t "$BACKUP_DIR"/images_*.txt 2>/dev/null | tail -n +6 | xargs -r rm --
    log_info "当前镜像已备份到 $backup_file"
}

# =============================================================================
# 参数解析
# =============================================================================
BUILD_FLAG=""
SERVICE="all"  # backend, frontend, worker, all
VERSION=""     # DockerHub 版本号，如 v1.2.3

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG="--build"
            shift
            ;;
        --backend)
            SERVICE="backend"
            shift
            ;;
        --frontend)
            SERVICE="frontend"
            shift
            ;;
        --worker)
            SERVICE="worker"
            shift
            ;;
        --no-cache)
            BUILD_FLAG="--build --no-cache"
            shift
            ;;
        --version)
            shift
            VERSION="$1"
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --build            重新构建镜像"
            echo "  --no-cache         重新构建镜像（不使用缓存）"
            echo "  --version <tag>    从 DockerHub 拉取指定版本镜像 (如 v1.2.3)"
            echo "  --backend          只更新后端"
            echo "  --frontend         只更新前端"
            echo "  --worker           只更新 Worker"
            echo "  -h, --help         显示帮助"
            echo ""
            echo "示例:"
            echo "  $0                           # 快速重启（使用现有镜像）"
            echo "  $0 --build                   # 重新构建并更新"
            echo "  $0 --version v1.2.3          # 拉取 v1.2.3 版本镜像"
            echo "  $0 --backend --build         # 只重新构建后端"
            echo "  $0 --version v1.2.3 --backend # 拉取指定版本后端镜像"
            echo "  $0 --worker --build          # 只重新构建 Worker"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# 使用 DockerHub 版本镜像
# =============================================================================
if [[ -n "$VERSION" ]]; then
    log_info "从 DockerHub 拉取版本 ${VERSION} 镜像..."

    # 拉取镜像
    for svc in backend frontend; do
        if [[ "$SERVICE" == "all" || "$SERVICE" == "$svc" ]]; then
            local_tag="${DOCKERHUB_REPO}:${svc}-${VERSION}"
            latest_tag="${DOCKERHUB_REPO}:${svc}-latest"
            log_info "拉取 ${local_tag}..."
            docker pull "$local_tag"
            # 同时更新 latest 标签
            docker tag "$local_tag" "$latest_tag"
        fi
    done

    # Worker 使用 backend 镜像
    if [[ "$SERVICE" == "all" || "$SERVICE" == "worker" ]]; then
        local_tag="${DOCKERHUB_REPO}:backend-${VERSION}"
        latest_tag="${DOCKERHUB_REPO}:backend-latest"
        docker pull "$local_tag" 2>/dev/null || true
        docker tag "$local_tag" "$latest_tag" 2>/dev/null || true
    fi

    log_info "镜像拉取完成"
fi

# =============================================================================
# 前置检查
# =============================================================================
log_info "检查环境..."

# 检查 .env 文件
if [ ! -s ".env" ]; then
    if [ -f ".env.docker" ]; then
        log_warn ".env 不存在或为空，从 .env.docker 复制"
        cp .env.docker .env
    else
        log_error ".env 和 .env.docker 都不存在"
        exit 1
    fi
fi

# 检查 langfuse 网络和 ClickHouse
if ! docker network ls | grep -q "langfuse_default"; then
    log_error "langfuse_default 网络不存在，请先启动 Langfuse"
    exit 1
fi

if ! docker ps | grep -q "langfuse-clickhouse-1"; then
    log_error "langfuse-clickhouse-1 容器未运行，请先启动"
    exit 1
fi

log_info "环境检查通过"

# =============================================================================
# 备份当前镜像标签（用于回滚）
# =============================================================================
backup_current_images

# =============================================================================
# 更新容器
# =============================================================================
case $SERVICE in
    backend)
        log_info "更新后端容器（含内嵌 MCP 服务）..."
        $COMPOSE_CMD up -d --force-recreate $BUILD_FLAG backend
        ;;
    frontend)
        log_info "更新前端容器..."
        $COMPOSE_CMD up -d --force-recreate $BUILD_FLAG frontend
        ;;
    worker)
        log_info "更新 Worker 容器..."
        $COMPOSE_CMD up -d --force-recreate $BUILD_FLAG worker
        ;;
    all)
        log_info "更新所有应用容器（backend 含内嵌 MCP, frontend, worker）..."
        $COMPOSE_CMD up -d --force-recreate $BUILD_FLAG backend frontend worker
        ;;
esac

# =============================================================================
# 等待健康检查
# =============================================================================
log_info "等待服务启动..."

# 等待后端健康
if [[ "$SERVICE" == "backend" || "$SERVICE" == "all" ]]; then
    echo -n "等待后端健康检查"
    for i in {1..60}; do
        if $COMPOSE_CMD ps backend | grep -q "healthy"; then
            echo ""
            log_info "后端启动成功（含 MCP 服务）"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! $COMPOSE_CMD ps backend | grep -q "healthy"; then
        echo ""
        log_error "后端启动超时，查看日志:"
        $COMPOSE_CMD logs --tail=20 backend
        exit 1
    fi
fi

# 检查前端
if [[ "$SERVICE" == "frontend" || "$SERVICE" == "all" ]]; then
    sleep 3
    if $COMPOSE_CMD ps frontend | grep -q "Up"; then
        log_info "前端启动成功"
    else
        log_error "前端启动失败"
        $COMPOSE_CMD logs --tail=10 frontend
        exit 1
    fi
fi

# 检查 Worker
if [[ "$SERVICE" == "worker" || "$SERVICE" == "all" ]]; then
    sleep 3
    if $COMPOSE_CMD ps worker | grep -q "Up"; then
        log_info "Worker 启动成功"
    else
        log_error "Worker 启动失败"
        $COMPOSE_CMD logs --tail=10 worker
        exit 1
    fi
fi

# =============================================================================
# 显示状态
# =============================================================================
echo ""
log_info "容器状态:"
$COMPOSE_CMD ps backend frontend worker

echo ""
log_info "ClickHouse 连接:"
$COMPOSE_CMD logs --tail=3 backend | grep -E "(ClickHouse|Connected)" || true

echo ""
log_info "更新完成！访问地址: http://localhost:18080"
log_info "MCP 端点: http://localhost:${MCP_PORT:-8001}/messages"

if [[ -n "$VERSION" ]]; then
    log_info "当前版本: ${VERSION}"
fi
log_info "如需回滚，执行: bash scripts/rollback.sh"
