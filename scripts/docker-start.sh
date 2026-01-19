#!/bin/bash
# scripts/docker-start.sh - Docker Compose startup helper
# 
# Usage:
#   ./scripts/docker-start.sh          # Full deployment (default)
#   ./scripts/docker-start.sh --full   # Full deployment with Langfuse
#   ./scripts/docker-start.sh --app    # Application only (use existing infra)
#   ./scripts/docker-start.sh --dev    # Development mode with hot reload
#   ./scripts/docker-start.sh --infra  # Infrastructure only
#   ./scripts/docker-start.sh --down   # Stop all services
#   ./scripts/docker-start.sh --logs   # Show logs
#   ./scripts/docker-start.sh --test   # Test container connectivity

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine docker compose command (v1 vs v2)
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    log_error "Neither docker-compose nor docker compose found!"
    exit 1
fi

# Check if .env exists, if not copy from .env.docker
check_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.docker" ]; then
            log_warn ".env not found, copying from .env.docker"
            cp .env.docker .env
            log_warn "Please edit .env and set your API keys (TUSHARE_TOKEN, OPENAI_API_KEY)"
            log_warn "If you need email whitelist, set AUTH_EMAIL_WHITELIST_ENABLED=true and prepare AUTH_EMAIL_WHITELIST_FILE (recommended: data/email.txt)"
        else
            log_error ".env.docker template not found!"
            exit 1
        fi
    fi
}

usage() {
    echo -e "${BLUE}Stock Platform Docker Deployment${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --full, -f      Complete deployment (infra + langfuse + app) [default]"
    echo "  --app, -a       Application only (connect to existing infra)"
    echo "  --dev, -d       Development mode with hot reload"
    echo "  --infra, -i     Infrastructure only (clickhouse + redis + postgres)"
    echo "  --down          Stop all services"
    echo "  --logs, -l      Show logs (follow mode)"
    echo "  --test, -t      Test container connectivity"
    echo "  --status, -s    Show service status"
    echo "  --help, -h      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --full       # First time setup with everything"
    echo "  $0 --app        # Use existing Langfuse infrastructure"
    echo "  $0 --test       # Verify all services are healthy"
}

load_env() {
    # Load variables from .env so ports match docker-compose mappings
    if [ -f ".env" ]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi

    APP_PORT="${APP_PORT:-18080}"
    LANGFUSE_PORT="${LANGFUSE_PORT:-3000}"
    REDIS_EXPOSE_PORT="${REDIS_EXPOSE_PORT:-16379}"
    CLICKHOUSE_HTTP_EXPOSE_PORT="${CLICKHOUSE_HTTP_EXPOSE_PORT:-18123}"
    CLICKHOUSE_NATIVE_PORT="${CLICKHOUSE_NATIVE_PORT:-19000}"
    POSTGRES_PORT="${POSTGRES_PORT:-15432}"
}

test_services() {
    check_env
    load_env

    log_info "Testing service connectivity..."
    echo ""

    # Unified entrypoint (frontend nginx) - proxies /health and serves SPA
    echo -n "  App entry (APP_PORT=${APP_PORT}): "
    if curl -sf "http://localhost:${APP_PORT}/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi

    echo -n "  Backend (/health via entry): "
    if curl -sf "http://localhost:${APP_PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi

    # Test Redis (container-level ping)
    echo -n "  Redis (exposed ${REDIS_EXPOSE_PORT}): "
    if docker exec stock-redis redis-cli -a "${REDIS_PASSWORD:-stockredis123}" ping 2>/dev/null | grep -q PONG; then
        echo -e "${GREEN}✓ Healthy${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi

    # Test ClickHouse (host exposed HTTP port)
    echo -n "  ClickHouse (http ${CLICKHOUSE_HTTP_EXPOSE_PORT}): "
    if curl -sf "http://localhost:${CLICKHOUSE_HTTP_EXPOSE_PORT}/ping" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi

    # Test Langfuse (if running)
    echo -n "  Langfuse (${LANGFUSE_PORT}): "
    if curl -sf "http://localhost:${LANGFUSE_PORT}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
    else
        echo -e "${YELLOW}○ Not running${NC}"
    fi

    echo ""

    # Show backend health details (via entry)
    if curl -sf "http://localhost:${APP_PORT}/health" > /dev/null 2>&1; then
        log_info "Backend health details:"
        curl -s "http://localhost:${APP_PORT}/health" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${APP_PORT}/health"
        echo ""
    fi
}

show_status() {
    log_info "Service Status:"
    $COMPOSE_CMD -f docker-compose.yml \
                 -f docker-compose.infra.yml \
                 -f docker-compose.langfuse.yml \
                 ps 2>/dev/null || $COMPOSE_CMD ps
}

case "${1:---full}" in
    --full|-f|full)
        check_env
        log_info "Starting complete deployment (infra + langfuse + app)..."
        $COMPOSE_CMD -f docker-compose.yml \
                     -f docker-compose.infra.yml \
                     -f docker-compose.langfuse.yml \
                     up -d --build
        log_info "Deployment complete!"
        echo ""
        load_env
        log_info "Services:"
        echo "  - App Entry:  http://localhost:${APP_PORT}"
        echo "  - API:        http://localhost:${APP_PORT}/api"
        echo "  - Docs:       http://localhost:${APP_PORT}/docs"
        echo "  - Langfuse:   http://localhost:${LANGFUSE_PORT}"
        echo "  - Redis:      localhost:${REDIS_EXPOSE_PORT}"
        echo "  - ClickHouse: localhost:${CLICKHOUSE_HTTP_EXPOSE_PORT} / ${CLICKHOUSE_NATIVE_PORT}"
        echo "  - Postgres:   localhost:${POSTGRES_PORT}"
        echo ""
        log_info "Run '$0 --test' to verify all services"
        ;;
    --app|-a|app)
        check_env
        log_info "Starting application services only..."
        $COMPOSE_CMD up -d --build
        log_info "Application started!"
        echo ""
        load_env
        log_info "Services:"
        echo "  - App Entry: http://localhost:${APP_PORT}"
        echo "  - API:       http://localhost:${APP_PORT}/api"
        echo "  - Docs:      http://localhost:${APP_PORT}/docs"
        ;;
    --dev|-d|dev)
        check_env
        log_info "Starting development mode with hot reload..."
        $COMPOSE_CMD -f docker-compose.yml \
                     -f docker-compose.infra.yml \
                     -f docker-compose.dev.yml \
                     up --build
        ;;
    --infra|-i|infra)
        check_env
        log_info "Starting infrastructure only (clickhouse + redis + postgres)..."
        $COMPOSE_CMD -f docker-compose.infra.yml up -d
        log_info "Infrastructure started!"
        echo ""
        load_env
        log_info "Services:"
        echo "  - Redis:      localhost:${REDIS_EXPOSE_PORT}"
        echo "  - ClickHouse: localhost:${CLICKHOUSE_HTTP_EXPOSE_PORT} / ${CLICKHOUSE_NATIVE_PORT}"
        echo "  - Postgres:   localhost:${POSTGRES_PORT}"
        ;;
    --down|down)
        log_info "Stopping all services..."
        $COMPOSE_CMD -f docker-compose.yml \
                     -f docker-compose.infra.yml \
                     -f docker-compose.langfuse.yml \
                     down
        log_info "All services stopped"
        ;;
    --logs|-l|logs)
        $COMPOSE_CMD -f docker-compose.yml \
                     -f docker-compose.infra.yml \
                     -f docker-compose.langfuse.yml \
                     logs -f
        ;;
    --test|-t|test)
        test_services
        ;;
    --status|-s|status)
        show_status
        ;;
    --help|-h|help)
        usage
        ;;
    *)
        log_error "Unknown option: $1"
        usage
        exit 1
        ;;
esac
