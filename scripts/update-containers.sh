#!/bin/bash
# =============================================================================
# 容器代码更新脚本
# 适用场景：宿主机已有 langfuse-clickhouse-1 和 Langfuse，只需更新应用容器
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# 参数解析
# =============================================================================
BUILD_FLAG=""
SERVICE="all"  # backend, frontend, all

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
        --no-cache)
            BUILD_FLAG="--build --no-cache"
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --build       重新构建镜像"
            echo "  --no-cache    重新构建镜像（不使用缓存）"
            echo "  --backend     只更新后端"
            echo "  --frontend    只更新前端"
            echo "  -h, --help    显示帮助"
            echo ""
            echo "示例:"
            echo "  $0                    # 快速重启（使用现有镜像）"
            echo "  $0 --build            # 重新构建并更新"
            echo "  $0 --backend --build  # 只重新构建后端"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# 前置检查
# =============================================================================
log_info "检查环境..."

# 检查 .env 文件
if [ ! -f ".env" ]; then
    if [ -f ".env.docker" ]; then
        log_warn ".env 不存在，从 .env.docker 复制"
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
# 更新容器
# =============================================================================
case $SERVICE in
    backend)
        log_info "更新后端容器..."
        docker-compose up -d --force-recreate $BUILD_FLAG backend
        ;;
    frontend)
        log_info "更新前端容器..."
        docker-compose up -d --force-recreate $BUILD_FLAG frontend
        ;;
    all)
        log_info "更新所有应用容器..."
        docker-compose up -d --force-recreate $BUILD_FLAG backend frontend
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
        if docker-compose ps backend | grep -q "healthy"; then
            echo ""
            log_info "后端启动成功"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! docker-compose ps backend | grep -q "healthy"; then
        echo ""
        log_error "后端启动超时，查看日志:"
        docker-compose logs --tail=20 backend
        exit 1
    fi
fi

# 检查前端
if [[ "$SERVICE" == "frontend" || "$SERVICE" == "all" ]]; then
    sleep 3
    if docker-compose ps frontend | grep -q "Up"; then
        log_info "前端启动成功"
    else
        log_error "前端启动失败"
        docker-compose logs --tail=10 frontend
        exit 1
    fi
fi

# =============================================================================
# 显示状态
# =============================================================================
echo ""
log_info "容器状态:"
docker-compose ps backend frontend

echo ""
log_info "ClickHouse 连接:"
docker-compose logs --tail=3 backend | grep -E "(ClickHouse|Connected)" || true

echo ""
log_info "更新完成！访问地址: http://localhost:18080"
